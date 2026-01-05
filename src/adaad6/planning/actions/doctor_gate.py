from __future__ import annotations

from typing import Any

from adaad6.assurance import run_doctor
from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    require_pass = params.get("require_pass", True)
    if not isinstance(require_pass, bool):
        raise ValueError("require_pass must be a boolean")
    return {"require_pass": require_pass, "cfg": cfg}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    cfg: AdaadConfig = validated["cfg"]
    require_pass: bool = validated["require_pass"]

    report = run_doctor(cfg=cfg)
    ok = bool(report.get("ok"))
    passed = ok or not require_pass
    return {
        "ok": passed,
        "doctor_ok": ok,
        "report": report,
        "reason": None if passed else "doctor_failed",
    }


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("doctor_gate result must be a dict")
    if "report" not in result:
        raise ValueError("doctor_gate result missing report")
    report = result["report"]
    if not isinstance(report, dict):
        raise ValueError("doctor_gate report must be a dict")
    if result.get("ok") is False and result.get("reason") is None:
        raise ValueError("doctor_gate failure must include reason")
    return result
