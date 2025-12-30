from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: str | bytes) -> str:
    data = value if isinstance(value, (bytes, bytearray)) else value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_object(obj: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(obj))


def attach_hash(obj: dict[str, Any]) -> dict[str, Any]:
    base = dict(obj)
    base.pop("hash", None)
    return {**base, "hash": hash_object(base)}


__all__ = ["canonical_json", "sha256_hex", "hash_object", "attach_hash"]
