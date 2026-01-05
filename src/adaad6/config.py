from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Mapping

ENV_PREFIX = "ADAAD6_"
CONFIG_SCHEMA_VERSION = "1"
SIG_ALG = "HMAC-SHA256"


class MutationPolicy(str, Enum):
    LOCKED = "locked"
    SANDBOXED = "sandboxed"
    EVOLUTIONARY = "evolutionary"


class ResourceTier(str, Enum):
    MOBILE = "mobile"
    EDGE = "edge"
    SERVER = "server"


class RunMode(str, Enum):
    DEV = "dev"
    PROD = "prod"


@dataclass(frozen=True)
class AdaadConfig:
    version: str = "0.0.0"

    home: str = "."
    actions_dir: str = ".adaad/actions"

    mutation_policy: MutationPolicy = MutationPolicy.LOCKED
    # optional readiness gate signature for EVOLUTIONARY
    readiness_gate_sig: str | None = None

    planner_max_steps: int = 25
    planner_max_seconds: float = 2.0

    mode: RunMode = RunMode.DEV
    config_schema_version: str = CONFIG_SCHEMA_VERSION

    resource_tier: ResourceTier = ResourceTier.MOBILE
    resource_scaling: float = 1.0  # derived, deterministic

    log_schema_version: str = "1"
    log_path: str = ".adaad/logs/adaad6.jsonl"

    ledger_enabled: bool = False
    ledger_dir: str = ".adaad/ledger"
    ledger_filename: str = "events.jsonl"
    ledger_file: str | None = None
    ledger_schema_version: str = "1"
    ledger_readonly: bool = False

    emergency_halt: bool = False
    agents_enabled: bool = True

    freeze_reason: str | None = None

    @property
    def mutation_enabled(self) -> bool:
        return not self.emergency_halt and self.mutation_policy != MutationPolicy.LOCKED

    def __post_init__(self) -> None:
        # honor legacy ledger_file alias without overriding explicit filename
        default_filename = type(self).ledger_filename
        if self.ledger_file and (self.ledger_filename == default_filename or not self.ledger_filename):
            object.__setattr__(self, "ledger_filename", self.ledger_file)
        if self.ledger_file is None:
            object.__setattr__(self, "ledger_file", self.ledger_filename)
        elif self.ledger_file != self.ledger_filename:
            object.__setattr__(self, "ledger_file", self.ledger_filename)

    def validate(self) -> None:
        if (self.config_schema_version or "").strip() != CONFIG_SCHEMA_VERSION:
            raise ValueError("config_schema_version mismatch")

        if not (self.log_path or "").strip():
            raise ValueError("log_path must be set")

        home = Path(self.home).expanduser().resolve()
        _enforce_log_path_sandbox(self.log_path, home=home)

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

        _enforce_actions_dir_sandbox(self.actions_dir, home=home)

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

            _enforce_ledger_dir_sandbox(self.ledger_dir, home=home)

        if self.emergency_halt:
            # freeze must dominate any other settings
            if self.mutation_policy != MutationPolicy.LOCKED:
                raise ValueError("emergency_halt requires mutation_policy=LOCKED")
            if not self.ledger_readonly:
                raise ValueError("emergency_halt requires ledger_readonly=True")
            if self.agents_enabled:
                raise ValueError("emergency_halt requires agents_enabled=False")


def _get_env(env: Mapping[str, str], key: str) -> str | None:
    return env.get(f"{ENV_PREFIX}{key}") or env.get(key)


def _require_sig_alg(env: Mapping[str, str]) -> bool:
    alg = (_get_env(env, "CONFIG_SIG_ALG") or "").strip()
    if not alg:
        return False
    return alg.upper() == SIG_ALG


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


def _dev_env_key_provider(env: Mapping[str, str]) -> str | None:
    return _get_env(env, "CONFIG_SIG_KEY")


def _canonical_env_payload(env: Mapping[str, str]) -> bytes:
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
    return "".join([f"{k}={v}\n" for k, v in items]).encode("utf-8")


def _verify_env_signature(
    env: Mapping[str, str],
    *,
    mode: RunMode,
    key_provider: Callable[[Mapping[str, str]], str | None],
) -> bool:
    if not _require_sig_alg(env):
        return False
    if (_get_env(env, "CONFIG_SCHEMA_VERSION") or "").strip() != CONFIG_SCHEMA_VERSION:
        return False

    sig_hex = _get_env(env, "CONFIG_SIG")
    if not sig_hex:
        return False

    if mode == RunMode.PROD and _get_env(env, "CONFIG_SIG_KEY"):
        return False

    key = key_provider(env)
    if not key:
        return False

    payload = _canonical_env_payload(env)
    mac = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig_hex.strip().lower())


def _resolve_home(env: Mapping[str, str]) -> Path:
    raw = _get_env(env, "HOME")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return Path(".").resolve()


def _resource_scaling_for_tier(tier: ResourceTier) -> float:
    # deterministic constants
    if tier == ResourceTier.MOBILE:
        return 2.5
    if tier == ResourceTier.EDGE:
        return 1.5
    return 1.0  # server


def _enforce_ledger_dir_sandbox(ledger_dir: str, *, home: Path) -> None:
    try:
        base = (home / ".adaad").resolve(strict=False)
    except TypeError:
        # python < 3.9 fallback
        base = Path(os.path.abspath(str(home / ".adaad")))
    target = Path(ledger_dir)
    if not target.is_absolute():
        target = home / target

    # resolve without requiring existence
    try:
        target_resolved = target.resolve(strict=False)
    except TypeError:
        target_resolved = Path(os.path.abspath(str(target)))

    if base not in target_resolved.parents and target_resolved != base:
        raise ValueError("ledger_dir must resolve under .adaad/ (sandbox violation)")

    try:
        rel = target_resolved.relative_to(base)
    except Exception as exc:
        raise ValueError("ledger_dir sandbox violation") from exc

    probe = base
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("ledger_dir must not traverse symlinks (sandbox violation)")


def _enforce_log_path_sandbox(log_path: str, *, home: Path) -> None:
    raw = (log_path or "").strip()
    posix = PurePosixPath(raw)
    win = PureWindowsPath(raw)

    if posix.is_absolute() or win.is_absolute() or win.drive:
        raise ValueError("log_path must be a relative path")
    if raw.startswith("~"):
        raise ValueError("log_path must not start with ~")
    if ".." in posix.parts or ".." in win.parts:
        raise ValueError("log_path must not contain parent directory traversal")

    target = home / raw
    try:
        resolved = target.resolve(strict=False)
    except TypeError:
        resolved = Path(os.path.abspath(str(target)))

    try:
        rel = resolved.relative_to(home)
    except Exception as exc:
        raise ValueError("log_path must resolve under home/") from exc

    probe = home
    for part in rel.parts[:-1]:  # directories only, ignore filename
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("log_path must not traverse symlinks")


def _enforce_actions_dir_sandbox(actions_dir: str, *, home: Path) -> None:
    raw = (actions_dir or "").strip()
    if not raw:
        raise ValueError("actions_dir must be set")

    posix = PurePosixPath(raw)
    win = PureWindowsPath(raw)

    if posix.is_absolute() or win.is_absolute() or win.drive:
        raise ValueError("actions_dir must be a relative path")
    if raw.startswith("~"):
        raise ValueError("actions_dir must not start with ~")
    if ".." in posix.parts or ".." in win.parts:
        raise ValueError("actions_dir must not contain parent directory traversal")

    target = home / raw
    try:
        resolved = target.resolve(strict=False)
    except TypeError:
        resolved = Path(os.path.abspath(str(target)))

    try:
        rel = resolved.relative_to(home)
    except Exception as exc:
        raise ValueError("actions_dir must resolve under home/") from exc

    probe = home
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("actions_dir must not traverse symlinks")


def load_config(
    env: Mapping[str, str] | None = None,
    *,
    key_provider: Callable[[Mapping[str, str]], str | None] = _dev_env_key_provider,
) -> AdaadConfig:
    source: Mapping[str, str] = env or os.environ

    mode = _coerce_enum(_get_env(source, "MODE") or RunMode.DEV.value, RunMode, "mode")
    cfg_schema_raw = (_get_env(source, "CONFIG_SCHEMA_VERSION") or "").strip()
    schema_mismatch = bool(cfg_schema_raw and cfg_schema_raw != CONFIG_SCHEMA_VERSION)
    cfg_schema = CONFIG_SCHEMA_VERSION
    home = _resolve_home(source)
    log_path = _get_env(source, "LOG_PATH") or AdaadConfig.log_path
    actions_dir = _get_env(source, "ACTIONS_DIR") or AdaadConfig.actions_dir

    sig_required_raw = _get_env(source, "CONFIG_SIG_REQUIRED")
    sig_required = _coerce_bool(sig_required_raw) if sig_required_raw else True

    # prod safety: default provider is dev-only. force explicit secure provider in prod.
    if mode == RunMode.PROD and key_provider is _dev_env_key_provider:
        sig_required = True

    emergency_halt_raw = _get_env(source, "EMERGENCY_HALT")
    emergency_halt = _coerce_bool(emergency_halt_raw) if emergency_halt_raw else False

    # signature gate
    sig_ok = _verify_env_signature(source, mode=mode, key_provider=key_provider) if sig_required else True
    must_freeze = schema_mismatch or (sig_required and not sig_ok)

    # if signature fails, freeze
    if must_freeze:
        if schema_mismatch:
            reason = "CONFIG_SCHEMA_VERSION_MISMATCH"
        elif mode == RunMode.PROD and key_provider is _dev_env_key_provider:
            reason = "CONFIG_SIG_KEY_PROVIDER_REQUIRED"
        else:
            try_key = key_provider(source)
            if not try_key:
                reason = "CONFIG_SIG_KEY_UNAVAILABLE"
            else:
                reason = "CONFIG_SIG_INVALID"
        cfg = AdaadConfig(
            version=_get_env(source, "VERSION") or AdaadConfig.version,
            mode=mode,
            config_schema_version=CONFIG_SCHEMA_VERSION,
            home=str(home),
            mutation_policy=MutationPolicy.LOCKED,
            planner_max_steps=1,
            planner_max_seconds=0.01,
            log_schema_version=_get_env(source, "LOG_SCHEMA_VERSION") or AdaadConfig.log_schema_version,
            log_path=log_path,
            actions_dir=actions_dir,
            ledger_enabled=True,
            ledger_dir=_get_env(source, "LEDGER_DIR") or AdaadConfig.ledger_dir,
            ledger_filename=_get_env(source, "LEDGER_FILE") or _get_env(source, "LEDGER_FILENAME") or AdaadConfig.ledger_filename,
            ledger_schema_version=_get_env(source, "LEDGER_SCHEMA_VERSION")
            or (_get_env(source, "LOG_SCHEMA_VERSION") or AdaadConfig.log_schema_version),
            ledger_readonly=True,
            emergency_halt=True,
            agents_enabled=False,
            freeze_reason=reason,
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
        mode=mode,
        config_schema_version=cfg_schema,
        home=str(home),
        mutation_policy=mutation_policy,
        readiness_gate_sig=readiness_gate_sig,
        planner_max_steps=planner_max_steps,
        planner_max_seconds=scaled_seconds,
        resource_tier=tier,
        resource_scaling=scaling,
        log_schema_version=log_schema_version,
        actions_dir=actions_dir,
        log_path=log_path,
        ledger_enabled=ledger_enabled or emergency_halt,
        ledger_dir=ledger_dir,
        ledger_filename=ledger_filename,
        ledger_schema_version=ledger_schema_version,
        ledger_readonly=ledger_readonly,
        emergency_halt=emergency_halt,
        agents_enabled=agents_enabled,
        freeze_reason="EMERGENCY_HALT" if emergency_halt else None,
    )
    cfg.validate()
    return cfg


__all__ = ["AdaadConfig", "MutationPolicy", "ResourceTier", "RunMode", "load_config"]
