from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any
from uuid import uuid4

from adaad6.assurance.logging import canonical_json
from adaad6.config import AdaadConfig
from adaad6.provenance.hashchain import compute_event_hash


def ledger_path(cfg: AdaadConfig) -> Path:
    return Path(cfg.ledger_dir) / cfg.ledger_filename


def ensure_ledger(cfg: AdaadConfig) -> Path:
    if not cfg.ledger_enabled:
        raise RuntimeError("Ledger is disabled by configuration")

    path = ledger_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.is_dir():
        raise RuntimeError(f"Ledger path {path} is a directory, expected a file")

    path.touch(exist_ok=True)
    return path


def _read_raw_events(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    events: deque[dict[str, Any]] | list[dict[str, Any]]
    if limit is None:
        events = []
    else:
        events = deque(maxlen=limit)

    with path.open("r", encoding="utf-8") as ledger_file:
        for line in ledger_file:
            stripped = line.strip()
            if not stripped:
                continue
            parsed = json.loads(stripped)
            events.append(parsed)

    return list(events)


def read_events(cfg: AdaadConfig, limit: int | None = None) -> list[dict[str, Any]]:
    if not cfg.ledger_enabled:
        raise RuntimeError("Ledger is disabled by configuration")

    path = ledger_path(cfg)
    return _read_raw_events(path, limit=limit)


def append_event(
    cfg: AdaadConfig, event_type: str, payload: dict[str, Any], ts: str, actor: str
) -> dict[str, Any]:
    path = ensure_ledger(cfg)
    existing = _read_raw_events(path, limit=1)
    prev_hash = existing[0]["hash"] if existing else None

    event_without_hash: dict[str, Any] = {
        "schema_version": cfg.log_schema_version,
        "event_id": str(uuid4()),
        "type": event_type,
        "payload": payload,
        "ts": ts,
        "actor": actor,
        "prev_hash": prev_hash,
    }
    event_hash = compute_event_hash(event_without_hash)
    event = {**event_without_hash, "hash": event_hash}

    with path.open("a", encoding="utf-8") as ledger_file:
        ledger_file.write(canonical_json(event) + "\n")

    return event


__all__ = ["ledger_path", "ensure_ledger", "append_event", "read_events"]
