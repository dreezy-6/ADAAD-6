from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from adaad6.config import AdaadConfig


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_checksum(payload: dict[str, Any]) -> str:
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class LogEvent:
    schema_version: str
    ts: str
    actor: str
    intent: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    checksum: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ts": self.ts,
            "actor": self.actor,
            "intent": self.intent,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "checksum": self.checksum,
        }


def build_log_event(
    schema_version: str,
    ts: str,
    actor: str,
    intent: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    checksum_fn: Callable[[dict[str, Any]], str] | None = None,
) -> LogEvent:
    payload = {
        "schema_version": schema_version,
        "ts": ts,
        "actor": actor,
        "intent": intent,
        "inputs": inputs,
        "outputs": outputs,
    }
    checksum_function = checksum_fn or compute_checksum
    checksum = checksum_function(payload)
    return LogEvent(
        schema_version=schema_version,
        ts=ts,
        actor=actor,
        intent=intent,
        inputs=inputs,
        outputs=outputs,
        checksum=checksum,
    )


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def log_path(cfg: AdaadConfig) -> Path:
    target = Path(cfg.log_path)
    if not target.is_absolute():
        home = Path(cfg.home).expanduser().resolve()
        target = home / target
    try:
        return target.resolve(strict=False)
    except TypeError:  # pragma: no cover - legacy compatibility
        return Path(os.path.abspath(str(target)))


def append_jsonl_log_event(
    *,
    cfg: AdaadConfig,
    action: str,
    outcome: str,
    details: dict[str, Any] | None = None,
    ts: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    event_without_checksum = {
        "schema_version": cfg.log_schema_version,
        "ts": ts or _utc_now_iso_z(),
        "action": action,
        "outcome": outcome,
        "details": details or {},
    }
    event = dict(event_without_checksum, checksum=compute_checksum(event_without_checksum))
    serialized = canonical_json(event)
    target = path or log_path(cfg)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.is_dir():
        raise RuntimeError(f"Log path {target} is a directory, expected a file")
    with target.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")
    return event


__all__ = [
    "LogEvent",
    "canonical_json",
    "compute_checksum",
    "build_log_event",
    "append_jsonl_log_event",
    "log_path",
]
