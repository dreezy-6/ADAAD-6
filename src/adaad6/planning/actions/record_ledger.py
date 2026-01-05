from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from adaad6.config import AdaadConfig
from adaad6.provenance.ledger import append_event, ensure_ledger


def _coerce_payload(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("payload must be a mapping")
    return dict(raw)


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    event_type = str(params.get("event_type", "scaffold_plan") or "scaffold_plan")
    payload = _coerce_payload(params.get("payload"))
    actor = str(params.get("actor", "planner"))
    return {"event_type": event_type, "payload": payload, "actor": actor, "cfg": cfg}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    cfg: AdaadConfig = validated["cfg"]
    if not cfg.ledger_enabled:
        return {"skipped": True, "reason": "ledger_disabled", "event": None, "completed": True, "ok": True}
    if cfg.ledger_readonly:
        return {"skipped": True, "reason": "ledger_readonly", "event": None, "completed": True, "ok": True}

    ensure_ledger(cfg)
    ts = datetime.now(timezone.utc).isoformat()
    event = append_event(
        cfg,
        event_type=validated["event_type"],
        payload=validated["payload"],
        ts=ts,
        actor=validated["actor"],
    )
    return {"skipped": False, "event": event, "timestamp": ts, "completed": True, "ok": True}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("record_ledger result must be a dict")
    if cfg.ledger_enabled and not result.get("skipped", False) and "event" not in result:
        raise ValueError("record_ledger must include event when ledger is enabled")
    if result.get("completed") is not True:
        raise ValueError("record_ledger must mark completion")
    if result.get("ok") is not True:
        raise ValueError("record_ledger must set ok=True on success or skip")
    return result
