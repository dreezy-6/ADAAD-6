from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, List

from adaad6.config import AdaadConfig


@dataclass(frozen=True)
class PlanStep:
    id: str
    action: str
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "action": self.action, "params": self.params}


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: List[PlanStep]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "meta": self.meta,
        }


def _generate_steps(goal: str) -> list[PlanStep]:
    normalized = goal.strip()
    if not normalized:
        return []
    steps: list[PlanStep] = [
        PlanStep(id="step-1", action="clarify_goal", params={"goal": normalized}),
        PlanStep(id="step-2", action="propose_actions", params={"goal": normalized}),
        PlanStep(id="step-3", action="report", params={"goal": normalized}),
    ]
    return steps


def make_plan(goal: str, cfg: AdaadConfig) -> Plan:
    cfg.validate()
    start = time.monotonic()
    meta: dict[str, Any] = {"truncated": False, "time_capped": False}

    raw = _generate_steps(goal)
    steps: list[PlanStep] = []
    for step in raw:
        if len(steps) >= cfg.planner_max_steps:
            meta["truncated"] = True
            break
        if (time.monotonic() - start) > cfg.planner_max_seconds:
            meta["time_capped"] = True
            break
        steps.append(step)

    plan = Plan(goal=goal, steps=steps, meta=meta)
    return plan


__all__ = ["PlanStep", "Plan", "make_plan"]
