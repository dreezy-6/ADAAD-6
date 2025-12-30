from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig, load_config
from adaad6.runtime import health


def boot_sequence(cfg: AdaadConfig | None = None) -> dict[str, Any]:
    config = cfg or load_config()
    config.validate()
    structure_ok = health.check_structure()
    checks = {
        "structure": structure_ok,
        "config": True,
    }
    limits = {
        "planner_max_steps": config.planner_max_steps,
        "planner_max_seconds": config.planner_max_seconds,
    }
    return {
        "ok": structure_ok and checks["config"],
        "mutation_enabled": config.mutation_enabled,
        "limits": limits,
        "checks": checks,
        "build": {"version": config.version},
    }


__all__ = ["boot_sequence"]
