from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    body = params.get("body", "")
    destination = params.get("destination", "report.txt")
    return {"body": str(body), "destination": str(destination)}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    return {"destination": validated["destination"], "bytes": len(validated["body"].encode("utf-8"))}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("write_report result must be a dict")
    return result
