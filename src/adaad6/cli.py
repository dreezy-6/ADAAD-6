from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _dump(obj: Any) -> str:
    # Late import so `adaad6 --help` does not fail if optional modules are missing.
    from adaad6.assurance.logging import canonical_json

    return canonical_json(obj)


def _emit(obj: Any) -> None:
    sys.stdout.write(_dump(obj) + "\n")
    sys.stdout.flush()


def _emit_stderr(text: str) -> None:
    # Human output should not break machine pipelines.
    sys.stderr.write(text.rstrip("\n") + "\n")
    sys.stderr.flush()


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--inputs must be valid JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("inputs must be a JSON object")
    return parsed


def _safe_cli_log(cfg: Any, *, action: str, outcome: str, details: dict[str, Any]) -> None:
    try:
        from adaad6.assurance.logging import append_jsonl_log_event

        append_jsonl_log_event(cfg=cfg, action=action, outcome=outcome, details=details)
    except Exception:  # pragma: no cover - defensive best-effort logging
        # CLI success/failure must not depend on logging availability.
        pass


def _doctor_human_summary(report: dict[str, Any]) -> str:
    run_id = report.get("run_id") or "unknown"
    status = "PASS" if report.get("ok") else "FAIL"
    lines = [f"Doctor report [{run_id}]: {status}"]
    summary = report.get("checks_summary") or {}
    if not isinstance(summary, dict):
        lines.append("- checks_summary: INVALID")
        return "\n".join(lines)
    for name in sorted(summary):
        check = summary.get(name)
        if not isinstance(check, dict):
            lines.append(f"- {name}: INVALID")
            continue
        if check.get("skipped"):
            check_status = "SKIPPED"
        elif check.get("ok"):
            check_status = "PASS"
        else:
            check_status = "FAIL"
        lines.append(f"- {name}: {check_status}")
    return "\n".join(lines)


class _EchoAdapter:
    name = "cli_echo"

    def run(self, intent: str, inputs: dict[str, Any], actor: str, cfg: Any):
        # Late import to avoid tight coupling between CLI import and adapter internals.
        from adaad6.adapters.base import BaseAdapter

        class _Wrapped(BaseAdapter):
            name = "cli_echo"

            def _execute(self, intent: str, inputs: dict[str, Any], cfg: Any) -> dict[str, Any]:
                return {"intent": intent, "inputs": inputs}

        return _Wrapped().run(intent=intent, inputs=inputs, actor=actor, cfg=cfg)


def _add_doctor_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--report",
        action="store_true",
        help="Deprecated. Same as --output both.",
    )
    parser.add_argument(
        "--output",
        choices=("json", "text", "both"),
        default="json",
        help="Output mode: json emits machine output to stdout; text emits human output to stderr; both emits both.",
    )
    parser.add_argument(
        "--no-template",
        action="store_true",
        help="Do not include the planning template in machine output",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adaad6", description="ADAAD-6 deterministic CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_common = argparse.ArgumentParser(add_help=False)
    doctor_common.add_argument(
        "--report-path",
        default="doctor_report.txt",
        help="Path to use in the generated report template destination",
    )

    sub.add_parser("boot", help="Run boot sequence checks")
    sub.add_parser("health", help="Run structural health checks")
    doctor_parser = sub.add_parser("doctor", help="Doctor utilities", parents=[doctor_common])
    _add_doctor_run_args(doctor_parser)
    doctor_sub = doctor_parser.add_subparsers(dest="doctor_command", required=False)

    doctor_run = doctor_sub.add_parser("run", help="Perform combined diagnostics", parents=[doctor_common])
    _add_doctor_run_args(doctor_run)

    doctor_tpl = doctor_sub.add_parser(
        "template", help="Emit the doctor planning template JSON without running doctor", parents=[doctor_common]
    )
    sub.add_parser("version", help="Show ADAAD-6 version information")

    plan_parser = sub.add_parser("plan", help="Generate a plan for a goal")
    plan_parser.add_argument("goal", help="Goal to plan for")

    template_parser = sub.add_parser("template", help="Emit a planning template JSON")
    template_parser.add_argument(
        "name",
        choices=("doctor_report", "diff_report", "scaffold", "zenith_ui"),
        help="Template name to render",
    )
    template_parser.add_argument(
        "--destination",
        default=None,
        help="Optional destination override written into the template metadata",
    )
    template_parser.add_argument(
        "--base-ref",
        default="HEAD",
        help="Base git ref for diff_report templates",
    )
    template_parser.add_argument(
        "--operator-name",
        default=None,
        help="Optional operator name for zenith_ui templates",
    )
    template_parser.add_argument(
        "--org-name",
        default=None,
        help="Optional organization name for zenith_ui templates",
    )

    run_parser = sub.add_parser("run", help="Execute a deterministic adapter call")
    run_parser.add_argument("--intent", default="noop", help="Intent name for the adapter call")
    run_parser.add_argument("--inputs", default="{}", help="JSON object of inputs for the adapter call")
    run_parser.add_argument("--actor", default="cli", help="Actor identifier for audit logs")

    ledger_parser = sub.add_parser("ledger", help="Ledger operations")
    ledger_sub = ledger_parser.add_subparsers(dest="ledger_command", required=True)
    tail_parser = ledger_sub.add_parser("tail", help="Tail ledger events")
    tail_parser.add_argument("--limit", type=int, default=None, help="Maximum number of events to read from the end")
    ledger_sub.add_parser("verify", help="Verify ledger hashchain integrity")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        from adaad6.config import load_config

        cfg = load_config()

        if args.command == "boot":
            from adaad6.runtime.boot import boot_sequence

            result = boot_sequence(cfg=cfg)
            outcome = "ok" if result.get("ok") else "error"
            _safe_cli_log(cfg, action="boot", outcome=outcome, details={"result": result})
            _emit(result)
            return 0 if result.get("ok") else 1

        if args.command == "health":
            from adaad6.runtime.health import check_structure_details

            details = check_structure_details(cfg=cfg)
            structure = details.get("structure") or {}
            ledger_dirs = details.get("ledger_dirs") or {}
            ok = bool(structure.get("ok", structure is True)) and bool(ledger_dirs.get("ok", ledger_dirs is True))
            _safe_cli_log(cfg, action="health", outcome="ok" if ok else "error", details={"details": details})
            _emit({"ok": ok, "details": details})
            return 0 if ok else 1

        if args.command == "doctor":
            # Backward-compatible default to run when no subcommand is provided.
            doctor_cmd = getattr(args, "doctor_command", None) or "run"

            if doctor_cmd == "template":
                if getattr(args, "report", False) or getattr(args, "no_template", False) or getattr(args, "output", "json") != "json":
                    parser.error("doctor template does not accept --output/--report/--no-template")
                from adaad6.planning.templates import compose_doctor_report_template

                template = compose_doctor_report_template(destination=args.report_path).to_dict()
                payload = {"ok": True, "template": template}
                _safe_cli_log(cfg, action="doctor_template", outcome="ok", details={"report": payload})
                _emit(payload)
                return 0
            if doctor_cmd != "run":
                parser.error("unknown doctor subcommand")

            from adaad6.assurance import run_doctor

            report = run_doctor(cfg=cfg)
            outcome = "ok" if report.get("ok") else "error"

            output_mode = getattr(args, "output", "json")
            if getattr(args, "report", False):
                output_mode = "both"

            want_json = output_mode in {"json", "both"}
            want_human = output_mode in {"text", "both"}

            human = _doctor_human_summary(report) if want_human else ""

            template = None
            if want_json and not getattr(args, "no_template", False):
                from adaad6.planning.templates import compose_doctor_report_template

                template = compose_doctor_report_template(destination=args.report_path).to_dict()

            machine_payload: dict[str, Any] = {"ok": bool(report.get("ok")), "report": report}
            if template is not None:
                machine_payload["template"] = template
            if output_mode == "both":
                machine_payload["human_readable"] = human

            _safe_cli_log(cfg, action="doctor", outcome=outcome, details={"report": machine_payload})

            if want_json:
                _emit(machine_payload)
            if want_human:
                _emit_stderr(human)

            return 0 if report.get("ok") else 1

        if args.command == "plan":
            from adaad6.planning.planner import make_plan

            plan = make_plan(goal=args.goal, cfg=cfg)
            _safe_cli_log(cfg, action="plan", outcome="ok", details={"goal": args.goal, "plan": plan.to_dict()})
            _emit({"ok": True, "plan": plan.to_dict()})
            return 0

        if args.command == "template":
            destination = getattr(args, "destination", None)
            if args.name == "doctor_report":
                from adaad6.planning.templates import compose_doctor_report_template

                template = compose_doctor_report_template(destination=destination or "doctor_report.txt").to_dict()
            elif args.name == "diff_report":
                from adaad6.planning.templates import compose_diff_report_template

                template = compose_diff_report_template(
                    base_ref=getattr(args, "base_ref", "HEAD"),
                    destination=destination or "changelog.md",
                ).to_dict()
            elif args.name == "zenith_ui":
                from adaad6.planning.templates import compose_zenith_ui_template

                template = compose_zenith_ui_template(
                    destination=destination or "zenith_app.jsx",
                    operator_name=args.operator_name or "OPERATOR",
                    org_name=args.org_name or "ORGANIZATION",
                ).to_dict()
            else:
                from adaad6.planning.templates import compose_scaffold_template

                template = compose_scaffold_template(destination=destination or "scaffold_report.txt").to_dict()
            _safe_cli_log(cfg, action="template", outcome="ok", details={"name": args.name, "template": template})
            _emit({"ok": True, "template": template})
            return 0

        if args.command == "run":
            inputs = _parse_json_object(args.inputs)
            adapter = _EchoAdapter()
            result = adapter.run(intent=args.intent, inputs=inputs, actor=args.actor, cfg=cfg)
            _safe_cli_log(
                cfg,
                action="run",
                outcome="ok" if result.ok else "error",
                details={"intent": args.intent, "inputs": inputs, "result": result.output, "log": result.log},
            )
            _emit({"ok": result.ok, "output": result.output, "log": result.log})
            return 0 if result.ok else 1

        if args.command == "ledger":
            limit = args.limit if hasattr(args, "limit") and (args.limit is None or args.limit >= 0) else None
            from adaad6.provenance.ledger import read_events

            if not getattr(cfg, "ledger_enabled", False):
                _emit({"ok": False, "error": "ledger disabled"})
                return 2
            try:
                events = read_events(cfg, limit=limit if args.ledger_command == "tail" else None)
            except FileNotFoundError:
                _emit({"ok": False, "error": "ledger not initialized"})
                return 2

            if args.ledger_command == "tail":
                _emit({"ok": True, "count": len(events)})
                for event in events:
                    sys.stdout.write(_dump(event) + "\n")
                return 0
            if args.ledger_command == "verify":
                from adaad6.provenance.hashchain import verify_chain

                valid = verify_chain(events)
                _emit({"ok": valid, "valid": valid, "count": len(events)})
                return 0 if valid else 1

        if args.command == "version":
            try:
                from adaad6.version import __version__ as pkg_version
            except Exception:
                pkg_version = None
            _emit(
                {
                    "ok": True,
                    "package_version": pkg_version,
                    "python": sys.version.split()[0],
                    "config_schema_version": getattr(cfg, "config_schema_version", None),
                }
            )
            return 0

        raise ValueError(f"Unknown command: {args.command}")
    except Exception as exc:  # pragma: no cover - CLI safety net
        _emit({"ok": False, "error": str(exc)})
        return 1


__all__ = ["main"]
