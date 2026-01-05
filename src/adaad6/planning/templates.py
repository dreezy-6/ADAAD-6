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


def compose_diff_report_template(base_ref: str = "HEAD", destination: str = "changelog.md") -> Plan:
    steps = validate_action_spec_list(
        [
            ActionSpec(
                id="scan-repo",
                action="scan_repo_tree",
                params={"root": ".", "max_depth": 3},
                preconditions=(),
                effects=("repo_scanned",),
                cost_hint=0.15,
            ),
            ActionSpec(
                id="git-diff-snapshot",
                action="git_diff_snapshot",
                params={"root": ".", "base_ref": base_ref, "target_ref": "WORKTREE", "max_patch_bytes": 65_536},
                preconditions=("repo_scanned",),
                effects=("diff_snapshot",),
                cost_hint=0.45,
            ),
            ActionSpec(
                id="format-changelog",
                action="format_changelog",
                params={
                    "title": "Changelog",
                    "base_ref": base_ref,
                    "target_ref": "WORKTREE",
                    "changes": ["Use git_diff_snapshot.changes"],
                    "stats": ["Use git_diff_snapshot.stats"],
                    "patch": "Use git_diff_snapshot.patch",
                },
                preconditions=("diff_snapshot",),
                effects=("changelog_ready",),
                cost_hint=0.2,
            ),
            ActionSpec(
                id="write-report",
                action="write_report",
                params={"destination": destination, "body": "Use format_changelog.changelog"},
                preconditions=("changelog_ready",),
                effects=("report_written",),
                cost_hint=0.1,
            ),
        ]
    )
    meta = {"template": "diff_report", "destination": destination, "base_ref": base_ref, "ledger": "record execution to ledger"}
    return Plan(goal="diff_report", steps=steps, meta=meta)


__all__ = ["compose_doctor_report_template", "compose_diff_report_template"]
