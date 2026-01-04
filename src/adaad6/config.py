from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

ENV_PREFIX = "ADAAD6_"


class MutationPolicy(str, Enum):
    LOCKED = "locked"
    SANDBOXED = "sandboxed"
    EVOLUTIONARY = "evolutionary"


class ResourceTier(str, Enum):
    MOBILE = "mobile"
    EDGE = "edge"
    SERVER = "server"


@dataclass(frozen=True)
class AdaadConfig:
    version: str = "0.0.0"

    mutation_policy: MutationPolicy = MutationPolicy.LOCKED
    # optional readiness gate signature for EVOLUTIONARY
    readiness_gate_sig: str | None = None

    planner_max_steps: int = 25
    planner_max_seconds: float = 2.0

    resource_tier: ResourceTier = ResourceTier.MOBILE
    resource_scaling: float = 1.0  # derived, deterministic

    log_schema_version: str = "1"

    ledger_enabled: bool = False
    ledger_dir: str = ".adaad/ledger"
    ledger_filename: str = "events.jsonl"
    ledger_schema_version: str = "1"
    ledger_readonly: bool = False

    emergency_halt: bool = False
    agents_enabled: bool = True

    def validate(self) -> None:
        # hard caps
        if not (1 <= self.planner_max_steps <= 10_000):
            raise ValueError("planner_max_steps must be 1..10000")
        if not (0.01 <= self.planner_max_seconds <= 300.0):
            raise ValueError("planner_max_seconds must be 0.01..300")

        if self.mutation_policy == MutationPolicy.EVOLUTIONARY and not (self.readiness_gate_sig or "").strip():
            raise ValueError("EVOLUTIONARY mutation_policy requires readiness_gate_sig")

        if self.ledger_enabled and not (self.ledger_dir or "").strip():
            raise ValueError("ledger_dir must be set when ledger logging is enabled")
        if self.ledger_enabled and not (self.ledger_filename or "").strip():
            raise ValueError("ledger_filename must be set when ledger logging is enabled")

        if self.ledger_enabled:
            # filename is a relative path only
            ledger_file_raw = (self.ledger_filename or "").strip()
            posix = PurePosixPath(ledger_file_raw)
            win = PureWindowsPath(ledger_file_raw)

            if posix.is_absolute() or win.is_absolute() or win.drive:
                raise ValueError("ledger_filename must be a relative path")
            if ledger_file_raw.startswith("~"):
                raise ValueError("ledger_filename must not start with ~")
            if ".." in posix.parts or ".." in win.parts:
                raise ValueError("ledger_filename must not contain parent directory traversal")
            if not (self.ledger_schema_version or "").strip():
                raise ValueError("ledger_schema_version must be set when ledger logging is enabled")

            _enforce_ledger_dir_sandbox(self.ledger_dir)

        if self.emergency_halt:
            # freeze must dominate any other settings
            if self.mutation_policy != MutationPolicy.LOCKED:
                raise ValueError("emergency_halt requires mutation_policy=LOCKED")
            if not self.ledger_readonly:
                raise ValueError("emergency_halt requires ledger_readonly=True")
            if self.agents_enabled:
                raise ValueError("emergency_halt requires agents_enabled=False")


def _get_env(env: Mapping[str, str], key: str) -> str | None:
    return env.get(f"{ENV_PREFIX}{key}")


def _coerce_bool(value: str) -> bool:
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    lowered = value.strip().lower()
    if lowered in truthy:
        return True
    if lowered in falsy:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _coerce_int(value: str, field: str) -> int:
    try:
        return int(value)
    except Exception as exc:
        raise ValueError(f"Invalid integer for {field}: {value}") from exc


def _coerce_float(value: str, field: str) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"Invalid float for {field}: {value}") from exc


def _coerce_enum(value: str, enum_cls, field: str):
    raw = value.strip().lower()
    try:
        return enum_cls(raw)
    except Exception as exc:
        allowed = ", ".join([e.value for e in enum_cls])
        raise ValueError(f"Invalid {field}: {value}. Allowed: {allowed}") from exc


def _canonical_env_payload(env: Mapping[str, str]) -> bytes:
    # include only ADAAD6_ vars, exclude secrets and signature fields
    excluded = {
        f"{ENV_PREFIX}CONFIG_SIG",
        f"{ENV_PREFIX}CONFIG_SIG_ALG",
        f"{ENV_PREFIX}CONFIG_SIG_KEY",
    }
    items = []
    for k, v in env.items():
        if not k.startswith(ENV_PREFIX):
            continue
        if k in excluded:
            continue
        items.append((k, v))
    items.sort(key=lambda kv: kv[0])
    # canonical format: key=value\n, utf-8
    return "".join([f"{k}={v}\n" for k, v in items]).encode("utf-8")


def _verify_env_signature(env: Mapping[str, str]) -> bool:
    sig_hex = _get_env(env, "CONFIG_SIG")
    if not sig_hex:
        return False
    key = _get_env(env, "CONFIG_SIG_KEY")
    if not key:
        return False
    payload = _canonical_env_payload(env)
    mac = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig_hex.strip().lower())


def _resource_scaling_for_tier(tier: ResourceTier) -> float:
    # deterministic constants
    if tier == ResourceTier.MOBILE:
        return 2.5
    if tier == ResourceTier.EDGE:
        return 1.5
    return 1.0  # server


def _enforce_ledger_dir_sandbox(ledger_dir: str) -> None:
    base = Path(".adaad").resolve()
    target = Path(ledger_dir)

    # resolve without requiring existence
    try:
        target_resolved = target.resolve(strict=False)
    except TypeError:
        # python < 3.9 fallback
        target_resolved = Path(os.path.abspath(str(target)))

    if base not in target_resolved.parents and target_resolved != base:
        raise ValueError("ledger_dir must resolve under .adaad/ (sandbox violation)")

    # symlink detection on existing path segments
    probe = Path(target_resolved.root) if target_resolved.is_absolute() else Path(".").resolve()
    for part in target_resolved.parts:
        # skip root markers
        if part in ("/", "\\"):
            continue
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("ledger_dir must not traverse symlinks (sandbox violation)")


def load_config(env: Mapping[str, str] | None = None) -> AdaadConfig:
    source: Mapping[str, str] = env or os.environ

    emergency_halt_raw = _get_env(source, "EMERGENCY_HALT")
    emergency_halt = _coerce_bool(emergency_halt_raw) if emergency_halt_raw else False

    # signature gate
    sig_required_raw = _get_env(source, "CONFIG_SIG_REQUIRED")
    sig_required = _coerce_bool(sig_required_raw) if sig_required_raw else True
    sig_ok = _verify_env_signature(source) if sig_required else True

    # if signature fails, freeze
    if sig_required and not sig_ok:
        cfg = AdaadConfig(
            version=_get_env(source, "VERSION") or AdaadConfig.version,
            mutation_policy=MutationPolicy.LOCKED,
            planner_max_steps=1,
            planner_max_seconds=0.01,
            log_schema_version=_get_env(source, "LOG_SCHEMA_VERSION") or AdaadConfig.log_schema_version,
            ledger_enabled=True,
            ledger_dir=_get_env(source, "LEDGER_DIR") or AdaadConfig.ledger_dir,
            ledger_filename=_get_env(source, "LEDGER_FILENAME") or AdaadConfig.ledger_filename,
            ledger_schema_version=_get_env(source, "LEDGER_SCHEMA_VERSION")
            or (_get_env(source, "LOG_SCHEMA_VERSION") or AdaadConfig.log_schema_version),
            ledger_readonly=True,
            emergency_halt=True,
            agents_enabled=False,
            resource_tier=_coerce_enum(_get_env(source, "RESOURCE_TIER") or "mobile", ResourceTier, "resource_tier"),
            resource_scaling=_resource_scaling_for_tier(
                _coerce_enum(_get_env(source, "RESOURCE_TIER") or "mobile", ResourceTier, "resource_tier")
            ),
        )
        cfg.validate()
        return cfg

    # normal load
    version = _get_env(source, "VERSION") or AdaadConfig.version

    mutation_policy = _coerce_enum(
        _get_env(source, "MUTATION_POLICY") or MutationPolicy.LOCKED.value,
        MutationPolicy,
        "mutation_policy",
    )
    readiness_gate_sig = _get_env(source, "READINESS_GATE_SIG")

    steps_raw = _get_env(source, "PLANNER_MAX_STEPS")
    planner_max_steps = _coerce_int(steps_raw, "planner_max_steps") if steps_raw else AdaadConfig.planner_max_steps

    seconds_raw = _get_env(source, "PLANNER_MAX_SECONDS")
    planner_max_seconds = (
        _coerce_float(seconds_raw, "planner_max_seconds") if seconds_raw else AdaadConfig.planner_max_seconds
    )

    log_schema_version = _get_env(source, "LOG_SCHEMA_VERSION") or AdaadConfig.log_schema_version

    ledger_enabled_raw = _get_env(source, "LEDGER_ENABLED")
    ledger_enabled = _coerce_bool(ledger_enabled_raw) if ledger_enabled_raw else AdaadConfig.ledger_enabled

    ledger_dir = _get_env(source, "LEDGER_DIR") or AdaadConfig.ledger_dir
    ledger_filename = (_get_env(source, "LEDGER_FILE") or _get_env(source, "LEDGER_FILENAME") or AdaadConfig.ledger_filename)

    ledger_schema_version = _get_env(source, "LEDGER_SCHEMA_VERSION") or log_schema_version

    ledger_readonly_raw = _get_env(source, "LEDGER_READONLY")
    ledger_readonly = _coerce_bool(ledger_readonly_raw) if ledger_readonly_raw else False

    agents_enabled_raw = _get_env(source, "AGENTS_ENABLED")
    agents_enabled = _coerce_bool(agents_enabled_raw) if agents_enabled_raw else True

    tier = _coerce_enum(_get_env(source, "RESOURCE_TIER") or ResourceTier.MOBILE.value, ResourceTier, "resource_tier")
    scaling = _resource_scaling_for_tier(tier)

    # apply scaling deterministically
    scaled_seconds = min(300.0, max(0.01, planner_max_seconds * scaling))

    # emergency halt dominates, even when signature OK
    if emergency_halt:
        mutation_policy = MutationPolicy.LOCKED
        readiness_gate_sig = None
        agents_enabled = False
        ledger_readonly = True
        planner_max_steps = 1
        scaled_seconds = 0.01

    cfg = AdaadConfig(
        version=version,
        mutation_policy=mutation_policy,
        readiness_gate_sig=readiness_gate_sig,
        planner_max_steps=planner_max_steps,
        planner_max_seconds=scaled_seconds,
        resource_tier=tier,
        resource_scaling=scaling,
        log_schema_version=log_schema_version,
        ledger_enabled=ledger_enabled or emergency_halt,
        ledger_dir=ledger_dir,
        ledger_filename=ledger_filename,
        ledger_schema_version=ledger_schema_version,
        ledger_readonly=ledger_readonly,
        emergency_halt=emergency_halt,
        agents_enabled=agents_enabled,
    )
    cfg.validate()
    return cfg


__all__ = ["AdaadConfig", "MutationPolicy", "ResourceTier", "load_config"]