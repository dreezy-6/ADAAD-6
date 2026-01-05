from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Callable, Iterable

from adaad6.config import AdaadConfig, ResourceTier
from adaad6.planning.spec import ActionSpec, validate_action_spec_list


def _base_actions(goal: str) -> list[ActionSpec]:
    normalized = goal.strip()
    if not normalized:
        return []

    return validate_action_spec_list(
        [
            ActionSpec(
                id="clarify",
                action="clarify_goal",
                params={"goal": normalized},
                preconditions=(),
                effects=("goal_clarity",),
                cost_hint=0.05,
            ),
            ActionSpec(
                id="constraints",
                action="identify_constraints",
                params={"goal": normalized},
                preconditions=("goal_clarity",),
                effects=("constraints_noted",),
                cost_hint=0.25,
            ),
            ActionSpec(
                id="context",
                action="survey_context",
                params={"goal": normalized, "depth": "light"},
                preconditions=("constraints_noted",),
                effects=("context_profiled",),
                cost_hint=1.25,
            ),
            ActionSpec(
                id="options",
                action="propose_actions",
                params={"goal": normalized, "fanout": 3},
                preconditions=("constraints_noted",),
                effects=("options_listed",),
                cost_hint=0.8,
            ),
            ActionSpec(
                id="select",
                action="select_minimum_path",
                params={"goal": normalized, "preference": "credibility_first"},
                preconditions=("options_listed",),
                effects=("plan_candidate",),
                cost_hint=0.35,
            ),
            ActionSpec(
                id="report",
                action="finalize_report",
                params={"goal": normalized},
                preconditions=("plan_candidate",),
                effects=("report_ready",),
                cost_hint=0.15,
            ),
        ]
    )


def _filter_for_tier(actions: Iterable[ActionSpec], *, tier: ResourceTier) -> list[ActionSpec]:
    if tier == ResourceTier.MOBILE:
        cutoff = 1.0
    elif tier == ResourceTier.EDGE:
        cutoff = 2.0
    else:
        cutoff = float("inf")

    def _effective_cost(action: ActionSpec) -> float:
        # Treat missing cost hints as unbounded so they do not bypass tier caps.
        return float("inf") if action.cost_hint is None else action.cost_hint

    return [action for action in actions if _effective_cost(action) <= cutoff]


def _apply_limits(
    actions: Iterable[ActionSpec],
    *,
    cfg: AdaadConfig,
    start: float,
    meta: dict[str, Any],
    now: Callable[[], float] = time.monotonic,
) -> list[ActionSpec]:
    bounded: list[ActionSpec] = []
    for action in actions:
        if now() - start > cfg.planner_max_seconds:
            meta["time_capped"] = True
            break
        if len(bounded) >= cfg.planner_max_steps:
            meta["truncated"] = True
            break
        bounded.append(action)
    return bounded


def _assign_ids(actions: Iterable[ActionSpec]) -> list[ActionSpec]:
    return [replace(action, id=f"act-{i + 1:03d}") for i, action in enumerate(actions)]


def _now() -> float:
    return time.monotonic()


class Plan:
    def __init__(self, goal: str, steps: list[ActionSpec], meta: dict[str, Any]):
        self.goal = goal
        self.steps = steps
        self.meta = meta

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "meta": self.meta,
        }


def make_plan(goal: str, cfg: AdaadConfig) -> Plan:
    cfg.validate()
    start = _now()
    meta: dict[str, Any] = {"truncated": False, "time_capped": False, "tier": cfg.resource_tier.value}

    actions = _base_actions(goal)
    filtered = _filter_for_tier(actions, tier=cfg.resource_tier)
    bounded = _apply_limits(filtered, cfg=cfg, start=start, meta=meta, now=_now)
    numbered = _assign_ids(bounded)

    return Plan(goal=goal, steps=numbered, meta=meta)


PlanStep = ActionSpec  # backward compatibility alias


__all__ = ["Plan", "PlanStep", "make_plan"]
