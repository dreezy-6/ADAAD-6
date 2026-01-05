from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    focus = params.get("focus", "default")
    return {"focus": str(focus)}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    focus = validated["focus"]
    return {"focus": focus, "risks": []}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("scan_risks result must be a dict")
    if "risks" not in result:
        raise ValueError("scan_risks result missing risks")
    return result
