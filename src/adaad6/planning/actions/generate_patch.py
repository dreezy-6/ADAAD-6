from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    diff = params.get("diff", "")
    return {"diff": str(diff)}


def run(validated: dict[str, Any]) -> dict[str, str]:
    return {"patch": validated["diff"]}


def postcheck(result: dict[str, str], cfg: AdaadConfig) -> dict[str, str]:
    if not isinstance(result, dict):
        raise ValueError("generate_patch result must be a dict")
    return result
