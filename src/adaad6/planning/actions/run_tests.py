from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence
from typing import Any

from adaad6.config import AdaadConfig, ResourceTier


def _coerce_command(raw: Any) -> str | list[str]:
    if raw is None:
        return "pytest"
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raise ValueError("command must not be bytes")
    if isinstance(raw, Sequence):
        return [str(item) for item in raw]
    raise ValueError("command must be a string or a sequence of strings")


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    command = _coerce_command(params.get("command"))
    timeout_raw = params.get("timeout")
    if timeout_raw is None:
        timeout = max(1.0, float(cfg.planner_max_seconds))
    else:
        timeout = float(timeout_raw)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    tier = cfg.resource_tier
    return {"command": command, "timeout": timeout, "tier": tier}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    tier: ResourceTier = validated["tier"]
    if tier == ResourceTier.MOBILE:
        return {"skipped": True, "reason": "resource_tier=mobile"}
    command = validated["command"]
    if isinstance(command, str):
        argv = shlex.split(command)
    else:
        argv = list(command)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=validated["timeout"])
        return {
            "skipped": False,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"skipped": False, "timeout": True}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("run_tests result must be a dict")
    if cfg.resource_tier == ResourceTier.MOBILE and not result.get("skipped"):
        raise ValueError("mobile tier must skip tests")
    return result
