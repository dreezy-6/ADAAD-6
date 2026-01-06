from __future__ import annotations

import types

import pytest

from adaad6 import MetaOrchestrator
from adaad6.assurance.logging import canonical_json
from adaad6.config import AdaadConfig, MutationPolicy
from adaad6.planning.planner import Plan
from adaad6.planning.spec import ActionSpec
from adaad6.planning.registry import ActionModule
from adaad6.provenance.ledger import read_events


def _action_module(name: str, result: object | None = None) -> ActionModule:
    module = types.SimpleNamespace(__name__="adaad6.planning.actions.test")

    def validate(params: dict[str, object], cfg: AdaadConfig) -> dict[str, object]:
        assert cfg
        return dict(params)

    def run(validated: dict[str, object]) -> dict[str, object]:
        return validated or (result or {})

    def postcheck(res: dict[str, object], cfg: AdaadConfig) -> dict[str, object]:
        assert cfg
        return res

    return ActionModule(name=name, module=module, validate=validate, run=run, postcheck=postcheck)


def _simple_plan(goal: str, action: str) -> Plan:
    steps = [
        ActionSpec(
            id="act-001",
            action=action,
            params={"goal": goal},
            preconditions=(),
            effects=(),
            cost_hint=0.1,
        )
    ]
    return Plan(goal=goal, steps=steps, meta={"source": "test"})


def test_readiness_gate_freezes_mutation(tmp_path) -> None:
    cfg = AdaadConfig(
        home=str(tmp_path),
        mutation_policy=MutationPolicy.EVOLUTIONARY,
        readiness_gate_sig="deadbeef",
    )
    orch = MetaOrchestrator()

    plan_factory = lambda goal, _: _simple_plan(goal, "safe_action")
    actions = lambda _: {"safe_action": _action_module("safe_action", {"ok": True})}

    result = orch.run("stability", cfg, plan_factory=plan_factory, action_builder=actions)

    assert result.config.mutation_policy == MutationPolicy.LOCKED
    assert result.config.freeze_reason is not None
    assert result.plan is not None and result.execution is not None
    assert result.execution.ok


def test_lineage_gate_rejects_when_evidence_missing(tmp_path) -> None:
    cfg = AdaadConfig(home=str(tmp_path), mutation_policy=MutationPolicy.SANDBOXED)
    orch = MetaOrchestrator()

    plan_factory = lambda goal, _: _simple_plan(goal, "mutate_code")
    actions = lambda _: {"mutate_code": _action_module("mutate_code", {"ok": True})}

    result = orch.run(
        "mutate safely",
        cfg,
        evidence_store=None,
        lineage_hash="abc123",
        plan_factory=plan_factory,
        action_builder=actions,
    )

    assert result.plan is not None
    assert result.execution is None
    assert result.ok is False
    assert result.lineage_gate is not None and result.lineage_gate.ok is False


def test_mutation_action_rejected_when_mutation_disabled(tmp_path) -> None:
    cfg = AdaadConfig(home=str(tmp_path), mutation_policy=MutationPolicy.LOCKED)
    orch = MetaOrchestrator()

    plan_factory = lambda goal, _: _simple_plan(goal, "mutate_code")
    actions = lambda _: {"mutate_code": _action_module("mutate_code", {"ok": True})}

    result = orch.run("mutate anyway", cfg, plan_factory=plan_factory, action_builder=actions)

    assert result.execution is None
    assert result.ok is False
    assert result.lineage_gate is not None


def test_monetizer_ledger_events_are_chained(tmp_path) -> None:
    cfg = AdaadConfig(
        home=str(tmp_path),
        ledger_enabled=True,
        ledger_dir=".adaad/ledger",
        ledger_filename="events.jsonl",
    )
    orch = MetaOrchestrator(archetype="monetizer")

    plan_factory = lambda goal, _: _simple_plan(goal, "select_template")
    actions = lambda _: {"select_template": _action_module("select_template", {"ok": True})}

    result = orch.run("grow revenue", cfg, plan_factory=plan_factory, action_builder=actions)
    assert result.execution is not None and result.execution.ok

    events = read_events(cfg)
    assert any(event["type"] == "monetizer_run_start" for event in events)
    assert any(event["type"] == "monetizer_run_complete" for event in events)

    for prev, current in zip(events, events[1:]):
        assert current["prev_hash"] == prev["hash"]

    monetizer_events = [event for event in events if event["type"].startswith("monetizer_run_")]
    assert all("payload_hash" in event["payload"] for event in monetizer_events)


def test_plan_ordering_is_deterministic(tmp_path) -> None:
    cfg = AdaadConfig(home=str(tmp_path))
    orch = MetaOrchestrator()

    plan_factory = lambda goal, _: _simple_plan(goal, "deterministic_action")
    actions = lambda _: {"deterministic_action": _action_module("deterministic_action", {"ok": True})}

    first = orch.run("consistent", cfg, plan_factory=plan_factory, action_builder=actions)
    second = orch.run("consistent", cfg, plan_factory=plan_factory, action_builder=actions)

    assert first.plan is not None and second.plan is not None
    serialized_first = canonical_json([step.to_dict() for step in first.plan.steps])
    serialized_second = canonical_json([step.to_dict() for step in second.plan.steps])
    assert serialized_first == serialized_second
    assert first.execution is not None and second.execution is not None
    assert first.execution.ok and second.execution.ok


def test_gate_failure_prevents_execution(tmp_path) -> None:
    cfg = AdaadConfig(home=str(tmp_path), mutation_policy=MutationPolicy.SANDBOXED)
    orch = MetaOrchestrator()

    call_count = {"run": 0}

    def counted_action(name: str) -> ActionModule:
        def validate(params: dict[str, object], cfg: AdaadConfig) -> dict[str, object]:
            return dict(params)

        def run(validated: dict[str, object]) -> dict[str, object]:
            call_count["run"] += 1
            return validated

        def postcheck(res: dict[str, object], cfg: AdaadConfig) -> dict[str, object]:
            return res

        return ActionModule(name=name, module=types.SimpleNamespace(), validate=validate, run=run, postcheck=postcheck)

    plan_factory = lambda goal, _: _simple_plan(goal, "mutate_code")
    actions = lambda _: {"mutate_code": counted_action("mutate_code")}

    result = orch.run(
        "fail gate",
        cfg,
        evidence_store=None,
        lineage_hash="abc123",
        plan_factory=plan_factory,
        action_builder=actions,
    )

    assert result.execution is None
    assert result.ok is False
    assert call_count["run"] == 0
