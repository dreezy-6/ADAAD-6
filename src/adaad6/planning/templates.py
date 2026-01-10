from __future__ import annotations

from importlib import resources

from adaad6.planning.planner import Plan
from adaad6.planning.spec import ActionSpec, validate_action_spec_list

_OPERATOR_PLACEHOLDER = "__OPERATOR_NAME__"
_ORG_PLACEHOLDER = "__ORG_NAME__"


def _load_zenith_ui_source(operator_name: str, org_name: str) -> str:
    source = (
        resources.files("adaad6.planning.assets")
        .joinpath("zenith_app.jsx")
        .read_text(encoding="utf-8")
    )
    return source.replace(_OPERATOR_PLACEHOLDER, operator_name).replace(_ORG_PLACEHOLDER, org_name)


def compose_scaffold_template(destination: str = "scaffold_report.txt") -> Plan:
    steps = validate_action_spec_list(
        [
            ActionSpec(
                id="select-template",
                action="select_template",
                params={"name": "scaffold", "available": ["scaffold", "compliance-report"]},
                preconditions=(),
                effects=("template_selected",),
                cost_hint=0.05,
            ),
            ActionSpec(
                id="generate-scaffold",
                action="generate_scaffold",
                params={"template": "scaffold", "components": ["core", "assurance", "runtime"]},
                preconditions=("template_selected",),
                effects=("scaffold_ready",),
                cost_hint=1.2,
            ),
            ActionSpec(
                id="verify-scaffold",
                action="run_tests",
                params={"command": ["pytest", "-q"], "timeout": 120},
                preconditions=("scaffold_ready",),
                effects=("verification_complete",),
                cost_hint=1.1,
            ),
            ActionSpec(
                id="record-ledger",
                action="record_ledger",
                params={"event_type": "scaffold_plan", "payload": {"summary": "Scaffold template actions executed"}},
                preconditions=("verification_complete",),
                effects=("ledger_step_complete",),
                cost_hint=0.2,
            ),
            ActionSpec(
                id="summarize-scaffold",
                action="summarize_results",
                params={
                    "title": "Scaffold planning summary",
                    "results": [
                        "Template: Use select_template.selected",
                        "Generation: Use generate_scaffold.scaffold or generate_scaffold.limitations",
                        "Verification: Use run_tests.returncode or run_tests.reason",
                        "Ledger: Use record_ledger.event or record_ledger.reason (skips still mark completion)",
                        "Mobile fallback: skip heavy steps and note limitations in summary",
                    ],
                },
                preconditions=("ledger_step_complete",),
                effects=("summary_ready",),
                cost_hint=0.1,
            ),
            ActionSpec(
                id="write-scaffold-report",
                action="write_report",
                params={"destination": destination, "body": "Use summarize_results.summary"},
                preconditions=("summary_ready",),
                effects=("report_written",),
                cost_hint=0.05,
            ),
        ]
    )
    meta = {
        "template": "scaffold",
        "destination": destination,
        "tier_fallback": "mobile tier skips scaffold generation and verification; summary notes limitations",
        "actions": "template selection, scaffold generation, verification, ledger record",
    }
    return Plan(goal="scaffold_plan", steps=steps, meta=meta)


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


def compose_zenith_ui_template(
    destination: str = "zenith_app.jsx",
    operator_name: str = "OPERATOR",
    org_name: str = "ORGANIZATION",
) -> Plan:
    content = _load_zenith_ui_source(operator_name=operator_name, org_name=org_name)
    steps = validate_action_spec_list(
        [
            ActionSpec(
                id="write-zenith-ui",
                action="write_artifact",
                params={"destination": destination, "content": content, "content_type": "text/javascript"},
                preconditions=(),
                effects=("artifact_written",),
                cost_hint=0.1,
            )
        ]
    )
    meta = {
        "template": "zenith_ui",
        "destination": destination,
        "description": "Emit the Zenith React UI component source.",
        "ledger": "record execution to ledger",
        "operator_name": operator_name,
        "org_name": org_name,
    }
    return Plan(goal="zenith_ui", steps=steps, meta=meta)


__all__ = [
    "compose_scaffold_template",
    "compose_doctor_report_template",
    "compose_diff_report_template",
    "compose_zenith_ui_template",
]
