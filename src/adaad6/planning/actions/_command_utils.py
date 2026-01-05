from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Any

from adaad6.config import AdaadConfig


def coerce_command(raw: Any, *, default: Sequence[str]) -> list[str]:
    if raw is None:
        return list(default)
    if isinstance(raw, (bytes, bytearray)):
        raise ValueError("command must not be bytes")
    if isinstance(raw, str):
        tokens = raw.split()
        if len(tokens) != 1:
            raise ValueError("command must be provided as a sequence, not a shell string")
        return tokens
    if isinstance(raw, Sequence):
        out: list[str] = []
        for item in raw:
            if isinstance(item, (bytes, bytearray)):
                raise ValueError("command tokens must not be bytes")
            out.append(str(item))
        if not out:
            raise ValueError("command must not be empty")
        return out
    raise ValueError("command must be a string or a sequence of strings")


def coerce_timeout(raw: Any, *, cfg: AdaadConfig) -> float:
    if raw is None:
        return max(1.0, float(cfg.planner_max_seconds))
    timeout = float(raw)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    return timeout


def execute_command(command: list[str], *, timeout: float, allowed: Sequence[str] | None = None) -> dict[str, Any]:
    argv = list(command)
    if not argv:
        return {
            "timeout": False,
            "returncode": None,
            "stdout": "",
            "stderr": "empty command",
            "error": "EmptyCommand",
        }
    if allowed is not None and argv:
        if argv[0] not in allowed:
            return {
                "timeout": False,
                "returncode": None,
                "stdout": "",
                "stderr": f"command '{argv[0]}' not permitted",
                "error": "NotPermitted",
            }
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {
            "timeout": False,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "error": None,
        }
    except (FileNotFoundError, OSError) as exc:
        return {
            "timeout": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "error": type(exc).__name__,
        }
    except subprocess.TimeoutExpired:
        return {"timeout": True, "returncode": None, "stdout": "", "stderr": "", "error": None}
