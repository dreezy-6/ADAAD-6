"""Common failure codes used during orchestration and runtime operations."""

from __future__ import annotations

from enum import Enum


class OrchestrationFailure(str, Enum):
    """Enumerated failure reasons for orchestrating ADAAD-6 runtime flows."""

    BOOT_FAILED = "BOOT_FAILED"
    EMERGENCY_HALT = "EMERGENCY_HALT"
    AGENTS_DISABLED = "AGENTS_DISABLED"
    READINESS_FREEZE = "READINESS_FREEZE"
    MUTATION_POLICY_BLOCKED = "MUTATION_POLICY_BLOCKED"
    LINEAGE_GATE_REJECTED = "LINEAGE_GATE_REJECTED"
    PLAN_INVALID = "PLAN_INVALID"
    EXECUTION_FAILED = "EXECUTION_FAILED"


__all__ = ["OrchestrationFailure"]
