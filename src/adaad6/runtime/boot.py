from __future__ import annotations

from dataclasses import asdict
from typing import Any

from adaad6.config import AdaadConfig, MutationPolicy, enforce_readiness_gate, load_config
from adaad6.runtime import health
from adaad6.provenance.ledger import ensure_ledger
from adaad6.runtime.gates import EvidenceStore, LineageGateResult, cryovant_lineage_gate


def boot_sequence(
    cfg: AdaadConfig | None = None,
    *,
    evidence_store: EvidenceStore | None = None,
    lineage_hash: str | None = None,
) -> dict[str, Any]:
    original_cfg = cfg or load_config()
    original_policy = original_cfg.mutation_policy
    config, readiness_sig_ok, readiness_sig_reason = enforce_readiness_gate(original_cfg)

    if config.emergency_halt or not config.agents_enabled:
        frozen_reason = config.freeze_reason or ("EMERGENCY_HALT" if config.emergency_halt else None)
        return {"ok": False, "frozen": True, "frozen_reason": frozen_reason, "config": asdict(config)}

    config.validate()
    structure_checks = health.check_structure_details(cfg=config)
    structure_ok = structure_checks["structure"]
    tree_law_ok = bool(structure_checks.get("tree_law", True))
    ledger_dirs_ok = structure_checks["ledger_dirs"]
    ledger_feed_ok = bool(structure_checks.get("ledger_feed", True))
    telemetry_ok = bool(structure_checks.get("telemetry_ok", True))
    ledger_ok = ledger_dirs_ok and ledger_feed_ok
    ledger_path = None
    ledger_error = structure_checks.get("ledger_feed_error") or structure_checks.get("ledger_dirs_error")
    if config.ledger_enabled and ledger_ok:
        try:
            ledger_path = str(ensure_ledger(config).absolute())
        except Exception as exc:  # pragma: no cover - runtime safety
            ledger_ok = False
            ledger_path = None
            ledger_error = str(exc)
    elif config.ledger_enabled and not ledger_ok:
        ledger_error = ledger_error or "ledger_feed_missing_or_unreadable"
    checks = {
        "structure": structure_ok,
        "tree_law": tree_law_ok,
        "config": True,
        "ledger": ledger_ok,
        "ledger_dirs": ledger_dirs_ok,
        "telemetry": telemetry_ok,
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
        "feed_ok": ledger_feed_ok,
        "feed_path": structure_checks.get("ledger_feed_path"),
    }
    telemetry_status = {
        "ok": telemetry_ok,
        "exports": structure_checks.get("telemetry_exports", []),
    }
    if original_policy == MutationPolicy.EVOLUTIONARY:
        gate = LineageGateResult(
            ok=bool(readiness_sig_ok),
            reason=readiness_sig_reason,
            lineage_hash=config.readiness_gate_sig,
        )
    else:
        gate = cryovant_lineage_gate(
            evidence_store=evidence_store,
            lineage_hash=lineage_hash or config.readiness_gate_sig,
        )
    mutation_enabled = bool(config.mutation_enabled and gate.ok)
    ok = structure_ok and tree_law_ok and checks["config"] and (ledger_ok or not config.ledger_enabled) and telemetry_ok
    return {
        "ok": ok,
        "mutation_enabled": mutation_enabled,
        "limits": limits,
        "checks": checks,
        "ledger": ledger_status,
        "telemetry": telemetry_status,
        "cryovant_gate": {"ok": gate.ok, "reason": gate.reason},
        "build": {"version": config.version},
        "freeze_reason": config.freeze_reason,
    }


__all__ = ["boot_sequence"]
