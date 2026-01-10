from __future__ import annotations

from pathlib import Path
from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    content = params.get("content", "")
    destination = params.get("destination", "artifact.txt")
    content_type = params.get("content_type", "text/plain")
    return {"content": str(content), "destination": str(destination), "content_type": str(content_type)}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    destination = Path(validated["destination"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = validated["content"].encode("utf-8")
    destination.write_bytes(data)
    return {"destination": str(destination), "bytes": len(data), "content_type": validated["content_type"]}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("write_artifact result must be a dict")
    destination = Path(str(result.get("destination", "")))
    if not destination.is_file():
        raise ValueError("write_artifact result destination missing")
    expected_bytes = result.get("bytes")
    if isinstance(expected_bytes, int) and destination.stat().st_size != expected_bytes:
        raise ValueError("write_artifact result byte count mismatch")
    return result
