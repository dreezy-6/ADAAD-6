from __future__ import annotations

import hashlib
from typing import Any, Iterable

from adaad6.assurance.logging import canonical_json


def compute_event_hash(event_without_hash: dict[str, Any]) -> str:
    encoded = canonical_json(event_without_hash).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_chain(events: Iterable[dict[str, Any]]) -> bool:
    prev_hash: str | None = None
    for event in events:
        expected_prev = prev_hash
        current = dict(event)
        current_hash = current.pop("hash", None)
        if current_hash is None:
            return False
        if current.get("prev_hash") != expected_prev:
            return False
        if compute_event_hash(current) != current_hash:
            return False
        prev_hash = current_hash
    return True


__all__ = ["compute_event_hash", "verify_chain"]
