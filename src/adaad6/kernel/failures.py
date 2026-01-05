from __future__ import annotations

import traceback
from typing import Optional

INTEGRITY_VIOLATION = "CRASH_0x01"
EVIDENCE_MISSING = "CRASH_0x02"
DETERMINISM_BREACH = "CRASH_0x03"
UNLOGGED_EXECUTION = "CRASH_0x04"


class KernelCrash(Exception):
    def __init__(self, code: str, detail: str, *, debug_detail: Optional[str] = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.debug_detail = debug_detail


def _exc_detail(exc: Exception) -> str:
    detail = str(exc)
    return detail if detail.strip() else exc.__class__.__name__


def _debug_traceback(exc: Exception) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def map_exception(exc: Exception, *, include_debug: bool = False) -> KernelCrash:
    """
    Map a Python exception to a deterministic KernelCrash code.

    When include_debug is True, a captured traceback is stored on the crash
    for internal inspection without leaking stack frames into serialized output.
    """
    if isinstance(exc, KernelCrash):
        if include_debug and exc.debug_detail is None:
            return KernelCrash(exc.code, exc.detail, debug_detail=_debug_traceback(exc))
        return exc

    detail = _exc_detail(exc)
    debug_detail = _debug_traceback(exc) if include_debug else None

    if isinstance(exc, (ValueError, TypeError, PermissionError)):
        return KernelCrash(INTEGRITY_VIOLATION, detail, debug_detail=debug_detail)
    if isinstance(exc, (KeyError, FileNotFoundError)):
        return KernelCrash(EVIDENCE_MISSING, detail, debug_detail=debug_detail)
    if isinstance(exc, TimeoutError):
        return KernelCrash(DETERMINISM_BREACH, detail, debug_detail=debug_detail)
    return KernelCrash(DETERMINISM_BREACH, detail, debug_detail=debug_detail)


__all__ = [
    "INTEGRITY_VIOLATION",
    "EVIDENCE_MISSING",
    "DETERMINISM_BREACH",
    "UNLOGGED_EXECUTION",
    "KernelCrash",
    "map_exception",
]
