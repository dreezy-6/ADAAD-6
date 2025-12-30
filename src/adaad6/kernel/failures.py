from __future__ import annotations

INTEGRITY_VIOLATION = "CRASH_0x01"
EVIDENCE_MISSING = "CRASH_0x02"
DETERMINISM_BREACH = "CRASH_0x03"
UNLOGGED_EXECUTION = "CRASH_0x04"


class KernelCrash(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


__all__ = [
    "INTEGRITY_VIOLATION",
    "EVIDENCE_MISSING",
    "DETERMINISM_BREACH",
    "UNLOGGED_EXECUTION",
    "KernelCrash",
]
