from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
import sys
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import quote

from adaad6.assurance.logging import canonical_json, compute_checksum
from adaad6.config import AdaadConfig, MutationPolicy, enforce_readiness_gate
from adaad6.kernel.failures import (
    EVIDENCE_MISSING,
    KernelCrash,
    map_exception,
)
from adaad6.kernel.context import KernelContext
from adaad6.planning.registry import ActionModule
from adaad6.planning.spec import ActionSpec
from adaad6.provenance.ledger import append_event, ensure_ledger
from adaad6.runtime.gates import EvidenceStore, LineageGateResult, cryovant_lineage_gate


ARTIFACT_INLINE_MAX_BYTES = 65_536


@dataclass(frozen=True)
class StageLog:
    stage: str
    status: str
    output: Any | None = None
    code: str | None = None
    detail: str | None = None
    debug_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"stage": self.stage, "status": self.status}
        if self.output is not None:
            data["output"] = self.output
        if self.code is not None:
            data["code"] = self.code
        if self.detail is not None:
            data["detail"] = self.detail
        return data


@dataclass(frozen=True)
class StepLog:
    id: str
    action: str
    status: str
    stages: tuple[StageLog, ...]
    output: Any | None = None
    code: str | None = None
    detail: str | None = None
    debug_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "action": self.action,
            "status": self.status,
            "stages": [stage.to_dict() for stage in self.stages],
        }
        if self.output is not None:
            data["output"] = self.output
        if self.code is not None:
            data["code"] = self.code
        if self.detail is not None:
            data["detail"] = self.detail
        return data


@dataclass(frozen=True)
class ExecutionLog:
    ok: bool
    status: str
    steps: tuple[StepLog, ...]
    context: KernelContext
    crash_code: str | None = None
    crash_detail: str | None = None
    crash_stage: str | None = None
    crash_step: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ok": self.ok,
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
            "run_id": self.context.run_id,
            "config_hash": self.context.config.hash,
            "artifacts": self.context.artifacts.to_dict(),
            "workspace": self.context.workspace.to_dict(),
        }
        if self.crash_code is not None:
            data["crash"] = {
                "code": self.crash_code,
                "detail": self.crash_detail,
                "stage": self.crash_stage,
                "step": self.crash_step,
            }
        return data


def _json_safe_output(output: Any) -> Any:
    try:
        json.dumps(output)
        return output
    except Exception:
        return {"__type__": type(output).__name__, "__repr__": repr(output)}


def _lookup_action(name: str, actions: Mapping[str, ActionModule]) -> ActionModule:
    action = actions.get(name)
    if action is None:
        raise KernelCrash(EVIDENCE_MISSING, f"Unknown action: {name}")
    return action


def _stage(
    stage: str,
    status: str,
    *,
    output: Any | None = None,
    crash: KernelCrash | None = None,
    capture_debug: bool = False,
) -> StageLog:
    if crash:
        return StageLog(
            stage=stage,
            status=status,
            code=crash.code,
            detail=crash.detail,
            debug_detail=crash.debug_detail if capture_debug else None,
        )
    return StageLog(stage=stage, status=status, output=_json_safe_output(output) if output is not None else None)


def _execute_step(
    spec: ActionSpec, *, module: ActionModule, cfg: AdaadConfig, capture_debug: bool = False
) -> StepLog:
    stages: list[StageLog] = []
    try:
        validated = module.validate(spec.params, cfg)
        stages.append(_stage("precheck", "ok", output=validated))
    except Exception as exc:  # pragma: no cover - exercised in executor
        crash = map_exception(exc, include_debug=capture_debug)
        stages.append(_stage("precheck", "crash", crash=crash, capture_debug=capture_debug))
        return StepLog(
            id=spec.id,
            action=spec.action,
            status="crash",
            stages=tuple(stages),
            code=crash.code,
            detail=crash.detail,
            debug_detail=crash.debug_detail if capture_debug else None,
        )

    try:
        result = module.run(validated)
        stages.append(_stage("execute", "ok", output=result))
    except Exception as exc:  # pragma: no cover - exercised in executor
        crash = map_exception(exc, include_debug=capture_debug)
        stages.append(_stage("execute", "crash", crash=crash, capture_debug=capture_debug))
        return StepLog(
            id=spec.id,
            action=spec.action,
            status="crash",
            stages=tuple(stages),
            code=crash.code,
            detail=crash.detail,
            debug_detail=crash.debug_detail if capture_debug else None,
        )

    try:
        checked = module.postcheck(result, cfg)
        stages.append(_stage("postcheck", "ok", output=checked))
    except Exception as exc:  # pragma: no cover - exercised in executor
        crash = map_exception(exc, include_debug=capture_debug)
        stages.append(_stage("postcheck", "crash", crash=crash, capture_debug=capture_debug))
        return StepLog(
            id=spec.id,
            action=spec.action,
            status="crash",
            stages=tuple(stages),
            code=crash.code,
            detail=crash.detail,
            debug_detail=crash.debug_detail if capture_debug else None,
        )

    return StepLog(
        id=spec.id,
        action=spec.action,
        status="ok",
        stages=tuple(stages),
        output=_json_safe_output(checked),
    )


def _artifact_uri(output: Any) -> str:
    serialized = canonical_json(_json_safe_output(output))
    encoded = serialized.encode("utf-8")
    if len(encoded) > ARTIFACT_INLINE_MAX_BYTES:
        digest = hashlib.sha256(encoded).hexdigest()
        truncated_payload = canonical_json({"hash": digest, "truncated": True})
        return f"data:application/json,{quote(truncated_payload, safe='')}"
    return f"data:application/json,{quote(serialized, safe='')}"


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _payload_with_content_hash(payload: dict[str, Any]) -> dict[str, Any]:
    base = dict(payload)
    base_without_hash = {k: v for k, v in base.items() if k != "content_hash"}
    canonical_payload = canonical_json(base_without_hash)
    base["content_hash"] = compute_checksum(canonical_payload)
    return base


def _requires_lineage_gate(plan: Sequence[ActionSpec] | Iterable[ActionSpec]) -> bool:
    mutation_actions = {"mutate_code", "mutate", "evolve", "autopromote", "autonomous_mutation"}
    mutation_effects = {"mutation", "evolution"}
    for spec in plan:
        if spec.action in mutation_actions:
            return True
        effects = tuple(spec.effects or ())
        if mutation_effects.intersection(set(effects)):
            return True
    return False


def _enforce_lineage_gate(
    plan_items: Sequence[ActionSpec] | Iterable[ActionSpec],
    cfg: AdaadConfig,
    *,
    evidence_store: EvidenceStore | None,
    lineage_hash: str | None,
    gate_result: LineageGateResult | None,
) -> None:
    if cfg.mutation_policy == MutationPolicy.EVOLUTIONARY:
        return
    gate_required = cfg.mutation_enabled and _requires_lineage_gate(plan_items)
    if not gate_required:
        return
    expected_lineage = lineage_hash or cfg.readiness_gate_sig
    gate = gate_result or cryovant_lineage_gate(evidence_store=evidence_store, lineage_hash=expected_lineage)
    if gate_result is not None and gate.lineage_hash != expected_lineage:
        raise RuntimeError("Cryovant gate result not bound to requested lineage")
    if gate_result is not None and (evidence_store is None or evidence_store.resolve_lineage(expected_lineage) is None):
        raise RuntimeError("Cryovant gate result lacks evidence backing")
    if not gate.ok:
        raise RuntimeError(f"Cryovant lineage gate failed: {gate.reason}")


def _run_plan(
    plan: Sequence[ActionSpec] | Iterable[ActionSpec],
    *,
    actions: Mapping[str, ActionModule],
    cfg: AdaadConfig,
    context: KernelContext,
    on_step: Callable[[StepLog, KernelContext], None] | None = None,
    on_artifact: Callable[[str, str, ActionSpec, KernelContext], None] | None = None,
    capture_debug: bool = False,
) -> ExecutionLog:
    steps: list[StepLog] = []
    crash_code: str | None = None
    crash_detail: str | None = None
    crash_stage: str | None = None
    crash_step: str | None = None
    halted = False

    for spec in plan:
        if halted:
            step = StepLog(
                id=spec.id,
                action=spec.action,
                status="skipped",
                stages=(StageLog(stage="precheck", status="skipped", detail="halted_after_crash"),),
                detail="skipped_after_crash",
            )
            steps.append(step)
            if on_step:
                on_step(step, context)
            continue

        try:
            module = _lookup_action(spec.action, actions)
        except KernelCrash as crash:
            mapped = map_exception(crash, include_debug=capture_debug)
            stages = (_stage("precheck", "crash", crash=mapped, capture_debug=capture_debug),)
            step = StepLog(
                id=spec.id,
                action=spec.action,
                status="crash",
                stages=stages,
                code=mapped.code,
                detail=mapped.detail,
                debug_detail=mapped.debug_detail if capture_debug else None,
            )
            steps.append(step)
            crash_code = mapped.code
            crash_detail = mapped.detail
            crash_stage = "precheck"
            crash_step = spec.id
            halted = True
            if on_step:
                on_step(step, context)
            continue

        step = _execute_step(spec, module=module, cfg=cfg, capture_debug=capture_debug)
        artifact: tuple[str, str] | None = None
        if step.status == "ok" and step.output is not None:
            artifact_name = f"{spec.id}:{spec.action}:result"
            artifact_uri = _artifact_uri(step.output)
            context = context.register_artifact(artifact_name, artifact_uri)
            artifact = (artifact_name, artifact_uri)
        steps.append(step)
        if on_step:
            on_step(step, context)
        if artifact and on_artifact:
            on_artifact(artifact[0], artifact[1], spec, context)
        if step.status != "ok":
            crash_code = step.code
            crash_detail = step.detail
            crash_stage = next((stage.stage for stage in step.stages if stage.status == "crash"), None)
            crash_step = spec.id
            halted = True

    ok = crash_code is None
    status = "ok" if ok else "crash"
    return ExecutionLog(
        ok=ok,
        status=status,
        steps=tuple(steps),
        context=context,
        crash_code=crash_code,
        crash_detail=crash_detail,
        crash_stage=crash_stage,
        crash_step=crash_step,
    )


def execute_plan(
    plan: Sequence[ActionSpec] | Iterable[ActionSpec],
    *,
    actions: Mapping[str, ActionModule],
    cfg: AdaadConfig,
    ctx: KernelContext | None = None,
    capture_debug: bool = False,
    evidence_store: EvidenceStore | None = None,
    lineage_hash: str | None = None,
    gate_result: LineageGateResult | None = None,
) -> ExecutionLog:
    cfg.validate()
    original_policy = cfg.mutation_policy
    cfg, readiness_ok, readiness_reason = enforce_readiness_gate(cfg)
    if original_policy == MutationPolicy.EVOLUTIONARY and not readiness_ok:
        raise RuntimeError(f"Readiness gate failed: {readiness_reason}")
    cfg.validate()
    plan_items = tuple(plan)
    _enforce_lineage_gate(plan_items, cfg, evidence_store=evidence_store, lineage_hash=lineage_hash, gate_result=gate_result)
    context = ctx or KernelContext.build(cfg)
    return _run_plan(plan_items, actions=actions, cfg=cfg, context=context, capture_debug=capture_debug)


def execute_and_record(
    plan: Sequence[ActionSpec] | Iterable[ActionSpec],
    *,
    actions: Mapping[str, ActionModule],
    cfg: AdaadConfig,
    ctx: KernelContext | None = None,
    actor: str = "executor",
    ledger_required: bool = False,
    capture_debug: bool = False,
    evidence_store: EvidenceStore | None = None,
    lineage_hash: str | None = None,
    gate_result: LineageGateResult | None = None,
) -> ExecutionLog:
    cfg.validate()
    original_policy = cfg.mutation_policy
    cfg, readiness_ok, readiness_reason = enforce_readiness_gate(cfg)
    if original_policy == MutationPolicy.EVOLUTIONARY and not readiness_ok:
        raise RuntimeError(f"Readiness gate failed: {readiness_reason}")
    cfg.validate()
    plan_items = tuple(plan)
    _enforce_lineage_gate(plan_items, cfg, evidence_store=evidence_store, lineage_hash=lineage_hash, gate_result=gate_result)
    context = ctx or KernelContext.build(cfg)
    if ledger_required and not cfg.ledger_enabled:
        raise RuntimeError("ledger_required=True but ledger is disabled")
    if not cfg.ledger_enabled:
        return _run_plan(plan_items, actions=actions, cfg=cfg, context=context, capture_debug=capture_debug)

    if cfg.ledger_readonly:
        raise RuntimeError("ledger is read-only")
    ensure_ledger(cfg)

    log: ExecutionLog | None = None
    last_artifact_hash: str | None = None
    start_payload = {
        "run_id": context.run_id,
        "config_hash": context.config.hash,
        "plan": [spec.to_dict() for spec in plan_items],
    }

    def _append_hashed_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return append_event(cfg, event_type, _payload_with_content_hash(payload), _utc_now_iso_z(), actor)

    try:
        _append_hashed_event("execution_run_start", start_payload)

        def _on_step(step: StepLog, ctx: KernelContext) -> None:
            _append_hashed_event(
                "execution_step",
                {"run_id": ctx.run_id, "action_id": step.id, "step": step.to_dict()},
            )

        def _on_artifact(name: str, uri: str, spec: ActionSpec, ctx: KernelContext) -> None:
            nonlocal last_artifact_hash
            event = _append_hashed_event(
                "execution_artifact",
                {
                    "run_id": ctx.run_id,
                    "action_id": spec.id,
                    "artifact": {"name": name, "uri": uri},
                    "parent_hash": last_artifact_hash,
                },
            )
            last_artifact_hash = event["payload"]["content_hash"]

        log = _run_plan(
            plan_items,
            actions=actions,
            cfg=cfg,
            context=context,
            on_step=_on_step,
            on_artifact=_on_artifact,
            capture_debug=capture_debug,
        )
        return log
    finally:
        end_context = log.context if log else context
        payload = {"run_id": end_context.run_id, "log": log.to_dict() if log else {"ok": False, "status": "crash"}}
        pending_exc = sys.exc_info()[1]
        try:
            _append_hashed_event("execution_run_end", payload)
        except Exception:
            if pending_exc is None:
                raise


__all__ = [
    "ExecutionLog",
    "StageLog",
    "StepLog",
    "execute_plan",
    "execute_and_record",
]
