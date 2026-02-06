from __future__ import annotations

from pathlib import Path
from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    content = params.get("content", "")
    destination = str(params.get("destination", "artifact.txt")).strip() or "artifact.txt"
    destination_path = Path(destination)
    if destination_path.is_absolute():
        raise ValueError("artifact destination must be relative")
    if ".." in destination_path.parts:
        raise ValueError("artifact destination must not contain parent traversal")
    content_type = params.get("content_type", "text/plain")
    return {
        "content": str(content),
        "destination": destination,
        "content_type": str(content_type),
        "_artifact_root": str(Path(getattr(cfg, "home", "."))),
    }


def run(validated: dict[str, Any]) -> dict[str, Any]:
    root = Path(str(validated.get("_artifact_root", ".")))
    destination = root / Path(validated["destination"])
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
    if not isinstance(result.get("content_type"), str):
        raise ValueError("write_artifact result content_type must be a string")
    return result
