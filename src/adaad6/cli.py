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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adaad6", description="ADAAD-6 deterministic CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("boot", help="Run boot sequence checks")
    sub.add_parser("health", help="Run structural health checks")
    sub.add_parser("doctor", help="Perform combined diagnostics")
    sub.add_parser("version", help="Show ADAAD-6 version information")

    plan_parser = sub.add_parser("plan", help="Generate a plan for a goal")
    plan_parser.add_argument("goal", help="Goal to plan for")

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
            from adaad6.assurance import run_doctor

            report = run_doctor(cfg=cfg)
            _safe_cli_log(cfg, action="doctor", outcome="ok" if report.get("ok") else "error", details={"report": report})
            _emit(report)
            return 0 if report.get("ok") else 1

        if args.command == "plan":
            from adaad6.planning.planner import make_plan

            plan = make_plan(goal=args.goal, cfg=cfg)
            _safe_cli_log(cfg, action="plan", outcome="ok", details={"goal": args.goal, "plan": plan.to_dict()})
            _emit({"ok": True, "plan": plan.to_dict()})
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
