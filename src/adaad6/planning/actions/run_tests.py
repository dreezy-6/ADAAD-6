from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig, ResourceTier
from adaad6.planning.actions._command_utils import coerce_command, coerce_timeout, execute_command


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    command = coerce_command(params.get("command"), default=("pytest",))
    timeout = coerce_timeout(params.get("timeout"), cfg=cfg)
    return {"command": command, "timeout": timeout, "tier": cfg.resource_tier}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    tier: ResourceTier = validated["tier"]
    if tier == ResourceTier.MOBILE:
        return {
            "skipped": True,
            "reason": "resource_tier=mobile",
            "ok": True,
            "timeout": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": None,
        }
    command = validated["command"]
    result = execute_command(command, timeout=validated["timeout"], allowed=("pytest", "python", "python3"))
    timeout = bool(result.get("timeout"))
    rc = result.get("returncode")
    result["skipped"] = False
    result["ok"] = (not timeout) and (rc == 0) and not result.get("error")
    result.setdefault("reason", None)
    return result


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("run_tests result must be a dict")
    if cfg.resource_tier == ResourceTier.MOBILE and not result.get("skipped"):
        raise ValueError("mobile tier must skip tests")
    if "ok" not in result:
        raise ValueError("run_tests must include ok flag")
    if not isinstance(result.get("ok"), bool):
        raise ValueError("run_tests ok must be a boolean")
    if not isinstance(result.get("skipped"), bool):
        raise ValueError("run_tests skipped must be a boolean")
    return result
