from __future__ import annotations

import hashlib
from typing import Any, Iterable

from adaad6.assurance.logging import canonical_json


def compute_event_hash(event_without_hash: dict[str, Any]) -> str:
    serialized = canonical_json(event_without_hash).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def verify_chain(events: Iterable[dict[str, Any]]) -> bool:
    previous_hash: str | None = None

    for index, event in enumerate(events):
        stored_hash = event.get("hash")
        candidate = {**event}
        candidate.pop("hash", None)
        expected_hash = compute_event_hash(candidate)

        if stored_hash != expected_hash:
            return False

        if index == 0:
            if event.get("prev_hash") not in (None, ""):
                return False
        else:
            if event.get("prev_hash") != previous_hash:
                return False

        previous_hash = stored_hash

    return True


__all__ = ["compute_event_hash", "verify_chain"]
