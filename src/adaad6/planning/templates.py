from __future__ import annotations

from adaad6.planning.planner import Plan
from adaad6.planning.spec import ActionSpec, validate_action_spec_list


def compose_doctor_report_template(destination: str = "doctor_report.txt") -> Plan:
    steps = validate_action_spec_list(
        [
            ActionSpec(
                id="doctor-gate",
                action="doctor_gate",
                params={"require_pass": True},
                preconditions=(),
                effects=("doctor_passed",),
                cost_hint=0.35,
            ),
            ActionSpec(
                id="summarize-results",
                action="summarize_results",
                params={"title": "Doctor results summary", "results": ["Use doctor_gate.report to summarize checks"]},
                preconditions=("doctor_passed",),
                effects=("summary_ready",),
                cost_hint=0.15,
            ),
            ActionSpec(
                id="write-report",
                action="write_report",
                params={"destination": destination, "body": "Write the doctor summary for audit logs"},
                preconditions=("summary_ready",),
                effects=("report_written",),
                cost_hint=0.05,
            ),
        ]
    )
    meta = {"template": "doctor_report", "destination": destination}
    return Plan(goal="doctor_report", steps=steps, meta=meta)


__all__ = ["compose_doctor_report_template"]
