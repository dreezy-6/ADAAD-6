from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig, load_config
from adaad6.runtime import health
from adaad6.provenance.ledger import ensure_ledger


def boot_sequence(cfg: AdaadConfig | None = None) -> dict[str, Any]:
    config = cfg or load_config()
    config.validate()
    structure_ok = health.check_structure()
    ledger_ok = True
    ledger_path = None
    ledger_error = None
    if config.ledger_enabled:
        try:
            ledger_path = str(ensure_ledger(config).absolute())
        except Exception as exc:  # pragma: no cover - runtime safety
            ledger_ok = False
            ledger_path = None
            ledger_error = str(exc)
    checks = {
        "structure": structure_ok,
        "config": True,
        "ledger": ledger_ok,
    }
    limits = {
        "planner_max_steps": config.planner_max_steps,
        "planner_max_seconds": config.planner_max_seconds,
    }
    ledger_status = {
        "enabled": config.ledger_enabled,
        "ok": ledger_ok,
        "path": ledger_path,
        "error": ledger_error,
    }
    return {
        "ok": structure_ok and checks["config"] and (ledger_ok or not config.ledger_enabled),
        "mutation_enabled": config.mutation_enabled,
        "limits": limits,
        "checks": checks,
        "ledger": ledger_status,
        "build": {"version": config.version},
    }


__all__ = ["boot_sequence"]
