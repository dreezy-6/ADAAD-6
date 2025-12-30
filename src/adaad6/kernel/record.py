from __future__ import annotations

from adaad6.kernel.hashing import attach_hash
from adaad6.kernel.schema import validate_execution_record


def make_refusal_record(bundle_hash: str, refusal_mode: str, failed_gate_id: str | None = None) -> dict:
    record = {
        "type": "ExecutionRecord",
        "version": "1",
        "evidence_bundle_hash": bundle_hash,
        "outcome": "REFUSED",
        "reason": "REFUSAL",
        "refusal_mode": refusal_mode,
    }
    if refusal_mode == "GATE_FAIL":
        record["failed_gate_id"] = failed_gate_id
    validate_execution_record(record)
    return attach_hash(record)


__all__ = ["make_refusal_record"]
