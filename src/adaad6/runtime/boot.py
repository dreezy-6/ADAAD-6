from __future__ import annotations

from dataclasses import asdict
from typing import Any

from adaad6.config import AdaadConfig, load_config
from adaad6.runtime import health
from adaad6.provenance.ledger import ensure_ledger


def boot_sequence(cfg: AdaadConfig | None = None) -> dict[str, Any]:
    config = cfg or load_config()

    if config.emergency_halt or not config.agents_enabled:
        frozen_reason = config.freeze_reason or ("EMERGENCY_HALT" if config.emergency_halt else None)
        return {"ok": False, "frozen": True, "frozen_reason": frozen_reason, "config": asdict(config)}

    config.validate()
    structure_checks = health.check_structure_details(cfg=config)
    structure_ok = structure_checks["structure"]
    tree_law_ok = bool(structure_checks.get("tree_law", True))
    ledger_dirs_ok = structure_checks["ledger_dirs"]
    ledger_ok = ledger_dirs_ok
    ledger_path = None
    ledger_error = structure_checks.get("ledger_dirs_error")
    if config.ledger_enabled and ledger_dirs_ok:
        try:
            ledger_path = str(ensure_ledger(config).absolute())
        except Exception as exc:  # pragma: no cover - runtime safety
            ledger_ok = False
            ledger_path = None
            ledger_error = str(exc)
    elif config.ledger_enabled and not ledger_dirs_ok:
        ledger_ok = False
    checks = {
        "structure": structure_ok,
        "tree_law": tree_law_ok,
        "config": True,
        "ledger": ledger_ok,
        "ledger_dirs": ledger_dirs_ok,
    }
    limits = {
        "planner_max_steps": config.planner_max_steps,
        "planner_max_seconds": config.planner_max_seconds,
    }
    ledger_status = {
        "enabled": config.ledger_enabled,
        "ok": ledger_ok,
        "dirs_ok": ledger_dirs_ok,
        "path": ledger_path,
        "error": ledger_error,
    }
    ok = structure_ok and tree_law_ok and checks["config"] and (ledger_ok or not config.ledger_enabled)
    return {
        "ok": ok,
        "mutation_enabled": config.mutation_enabled,
        "limits": limits,
        "checks": checks,
        "ledger": ledger_status,
        "build": {"version": config.version},
    }


__all__ = ["boot_sequence"]
