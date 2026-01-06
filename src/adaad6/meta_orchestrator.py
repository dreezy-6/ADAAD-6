from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Mapping

from adaad6.assurance.logging import canonical_json, compute_checksum
from adaad6.config import AdaadConfig, enforce_readiness_gate
from adaad6.planning.actions import builtin_action_names
from adaad6.provenance.ledger import append_event
from adaad6.runtime.failure import OrchestrationFailure

if TYPE_CHECKING:
    from adaad6.kernel.context import KernelContext
    from adaad6.planning.planner import Plan
    from adaad6.planning.registry import ActionModule
    from adaad6.runtime.executor import ExecutionLog
    from adaad6.runtime.gates import EvidenceStore, LineageGateResult


PlanFactory = Callable[[str, AdaadConfig], "Plan"]
ActionBuilder = Callable[[AdaadConfig], Mapping[str, "ActionModule"]]


@dataclass(frozen=True)
class OrchestratorResult:
    ok: bool
    config: AdaadConfig
    plan: "Plan | None"
    execution: "ExecutionLog | None"
    boot: Mapping[str, Any]
    lineage_gate: "LineageGateResult | None"
    failure_reason: OrchestrationFailure | None = None

    def __post_init__(self) -> None:
        if self.ok and self.failure_reason is not None:
            raise ValueError("failure_reason must be None when ok=True")
        if not self.ok and self.failure_reason is None:
            raise ValueError("failure_reason must be set when ok=False")


@dataclass(frozen=True)
class ArchetypePolicy:
    name: str
    action_filter: Callable[[dict[str, "ActionModule"], AdaadConfig], dict[str, "ActionModule"]]
    require_ledger: bool = False
    on_start: Callable[[AdaadConfig, str, "Plan"], None] | None = None
    on_complete: Callable[[AdaadConfig, str, "ExecutionLog | None"], None] | None = None


_ARCHETYPES: dict[str, ArchetypePolicy] = {}
_MUTATION_ACTIONS = {"mutate_code", "generate_patch"}
_ALLOWED_MONETIZER_PREFIXES = (
    "adaad6.planning.actions.",
    "adaad6.adapters.monetizer.",
    "adaad6.adapters.monetizer_adapter",
)


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def register_archetype(name: str, policy: ArchetypePolicy) -> ArchetypePolicy:
    key = name.strip().lower()
    if not key:
        raise ValueError("archetype name must be set")
    if not isinstance(policy, ArchetypePolicy):
        raise TypeError("policy must be an ArchetypePolicy")
    if policy.name.strip().lower() != key:
        raise ValueError("policy.name must match registration name")
    existing = _ARCHETYPES.get(key)
    if existing:
        if existing != policy:
            raise ValueError(f"Archetype '{key}' already registered")
        return existing
    _ARCHETYPES[key] = policy
    return policy


def get_archetype(name: str | None) -> ArchetypePolicy | None:
    if not name:
        return None
    return _ARCHETYPES.get(name.strip().lower())


def _hashed_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(payload)
    base["payload_hash"] = compute_checksum(canonical_json(payload))
    return base


def _is_revenue_safe_action(module: "ActionModule") -> bool:
    provenance = getattr(module.module, "__name__", "")
    return provenance.startswith(_ALLOWED_MONETIZER_PREFIXES)


def _monetizer_action_filter(actions: dict[str, "ActionModule"], cfg: AdaadConfig) -> dict[str, "ActionModule"]:
    del cfg  # unused in current policy for now
    unsafe = {"mutate_code", "generate_patch"}
    safe_names = {name for name in builtin_action_names() if name not in unsafe}
    return {name: module for name, module in actions.items() if name in safe_names and _is_revenue_safe_action(module)}


def _monetizer_start(cfg: AdaadConfig, goal: str, plan: "Plan") -> None:
    if not cfg.ledger_enabled:
        return
    payload = {"archetype": "monetizer", "stage": "start", "goal": goal, "plan": [step.to_dict() for step in plan.steps]}
    append_event(cfg, "monetizer_run_start", _hashed_payload(payload), _utc_now_iso_z(), actor="monetizer")


def _monetizer_complete(cfg: AdaadConfig, goal: str, log: "ExecutionLog | None") -> None:
    if not cfg.ledger_enabled:
        return
    payload = {
        "archetype": "monetizer",
        "stage": "complete",
        "goal": goal,
        "ok": log.ok if log else False,
        "run_id": log.context.run_id if log else None,
    }
    append_event(cfg, "monetizer_run_complete", _hashed_payload(payload), _utc_now_iso_z(), actor="monetizer")


_MONETIZER_ARCHETYPE = ArchetypePolicy(
    name="monetizer",
    action_filter=_monetizer_action_filter,
    require_ledger=True,
    on_start=_monetizer_start,
    on_complete=_monetizer_complete,
)

@lru_cache(maxsize=1)
def register_builtin_archetypes() -> None:
    register_archetype("monetizer", _MONETIZER_ARCHETYPE)


class MetaOrchestrator:
    def __init__(self, archetype: str | None = None) -> None:
        self.archetype = archetype.strip().lower() if archetype else None

    def run(
        self,
        goal: str,
        cfg: AdaadConfig,
        *,
        evidence_store: "EvidenceStore | None" = None,
        lineage_hash: str | None = None,
        context: "KernelContext | None" = None,
        plan_factory: PlanFactory | None = None,
        action_builder: ActionBuilder | None = None,
    ) -> OrchestratorResult:
        from adaad6.kernel.context import KernelContext
        from adaad6.planning.planner import make_plan
        from adaad6.planning.registry import discover_actions
        from adaad6.runtime.boot import boot_sequence
        from adaad6.runtime.executor import execute_and_record
        from adaad6.runtime.gates import cryovant_lineage_gate

        register_builtin_archetypes()
        cfg_enforced, _, _ = enforce_readiness_gate(cfg)
        boot = boot_sequence(cfg=cfg_enforced, evidence_store=evidence_store, lineage_hash=lineage_hash)

        if cfg_enforced.emergency_halt or not cfg_enforced.agents_enabled or boot.get("frozen"):
            failure = (
                OrchestrationFailure.EMERGENCY_HALT
                if cfg_enforced.emergency_halt
                else OrchestrationFailure.AGENTS_DISABLED
                if not cfg_enforced.agents_enabled
                else OrchestrationFailure.BOOT_FAILED
            )
            return OrchestratorResult(
                ok=False,
                config=cfg_enforced,
                plan=None,
                execution=None,
                boot=boot,
                lineage_gate=None,
                failure_reason=failure,
            )
        if not boot.get("ok", False):
            return OrchestratorResult(
                ok=False,
                config=cfg_enforced,
                plan=None,
                execution=None,
                boot=boot,
                lineage_gate=None,
                failure_reason=OrchestrationFailure.BOOT_FAILED,
            )

        actions_fn = action_builder or (lambda config: discover_actions(cfg=config))
        actions = dict(actions_fn(cfg_enforced))

        policy = get_archetype(self.archetype)
        if policy:
            if policy.require_ledger and not cfg_enforced.ledger_enabled:
                raise RuntimeError(f"{policy.name} archetype requires ledger_enabled=True")
            actions = policy.action_filter(actions, cfg_enforced)

        plan_fn = plan_factory or make_plan
        plan = plan_fn(goal, cfg_enforced)

        gate_result = None
        mutation_actions_present = any(step.action in _MUTATION_ACTIONS for step in plan.steps)
        if mutation_actions_present:
            gate_result = cryovant_lineage_gate(
                evidence_store=evidence_store,
                lineage_hash=lineage_hash or cfg_enforced.readiness_gate_sig,
            )
            if not cfg_enforced.mutation_enabled:
                return OrchestratorResult(
                    ok=False,
                    config=cfg_enforced,
                    plan=plan,
                    execution=None,
                    boot=boot,
                    lineage_gate=gate_result,
                    failure_reason=OrchestrationFailure.MUTATION_POLICY_BLOCKED,
                )
            if not gate_result.ok:
                return OrchestratorResult(
                    ok=False,
                    config=cfg_enforced,
                    plan=plan,
                    execution=None,
                    boot=boot,
                    lineage_gate=gate_result,
                    failure_reason=OrchestrationFailure.LINEAGE_GATE_REJECTED,
                )

        ctx = context or KernelContext.build(cfg_enforced)
        if policy and policy.on_start:
            policy.on_start(cfg_enforced, goal, plan)

        execution = execute_and_record(
            plan.steps,
            actions=actions,
            cfg=cfg_enforced,
            ctx=ctx,
            evidence_store=evidence_store,
            lineage_hash=lineage_hash,
            gate_result=gate_result,
        )

        if policy and policy.on_complete:
            policy.on_complete(cfg_enforced, goal, execution)

        failure_reason = None if execution.ok else OrchestrationFailure.EXECUTION_FAILED

        return OrchestratorResult(
            ok=execution.ok,
            config=cfg_enforced,
            plan=plan,
            execution=execution,
            boot=boot,
            lineage_gate=gate_result,
            failure_reason=failure_reason,
        )


__all__ = [
    "ArchetypePolicy",
    "MetaOrchestrator",
    "OrchestratorResult",
    "get_archetype",
    "register_archetype",
]
