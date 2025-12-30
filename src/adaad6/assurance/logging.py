from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable


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


__all__ = [
    "LogEvent",
    "canonical_json",
    "compute_checksum",
    "build_log_event",
]
