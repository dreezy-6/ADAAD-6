from __future__ import annotations

import json
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
        raise RuntimeError("Ledger is disabled")
    if not (cfg.ledger_dir or "").strip() or not (cfg.ledger_filename or "").strip():
        raise ValueError("Ledger directory and file must be set when ledger is enabled")
    path = ledger_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_dir():
        raise RuntimeError(f"Ledger path {path} is a directory, expected a file")
    path.touch(exist_ok=True)
    return path


def _last_hash(path: Path) -> str | None:
    last_line = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        return None
    last_event = json.loads(last_line)
    return last_event.get("hash")


def append_event(cfg: AdaadConfig, event_type: str, payload: dict[str, Any], ts: str, actor: str) -> dict[str, Any]:
    if cfg.ledger_readonly:
        raise RuntimeError("LEDGER_READONLY")

    path = ensure_ledger(cfg)
    prev_hash = _last_hash(path)
    event_without_hash = {
        "schema_version": cfg.ledger_schema_version,
        "event_id": str(uuid4()),
        "ts": ts,
        "actor": actor,
        "type": event_type,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    event_hash = compute_event_hash(event_without_hash)
    event = dict(event_without_hash, hash=event_hash)
    serialized = canonical_json(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")
    return event


def read_events(cfg: AdaadConfig, limit: int | None = None) -> list[dict[str, Any]]:
    if not cfg.ledger_enabled:
        raise RuntimeError("Ledger is disabled")
    path = ensure_ledger(cfg)
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            events.append(json.loads(line))
    if limit is None:
        return events
    return events[-limit:]


__all__ = ["append_event", "ensure_ledger", "ledger_path", "read_events"]
