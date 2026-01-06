from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from adaad6.config import AdaadConfig, ResourceTier, load_config
from adaad6.provenance.ledger import append_event, ensure_ledger
from adaad6.runtime.health import check_structure_details

FORBIDDEN_MODULES = {"socket"}


def _check_config(config: AdaadConfig) -> dict[str, Any]:
    try:
        config.validate()
        return {"ok": True, "schema_version": config.config_schema_version}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_structure(config: AdaadConfig, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    details = details or check_structure_details(cfg=config)
    details_sorted = dict(sorted(details.items()))
    ok = (
        bool(details.get("structure"))
        and bool(details.get("ledger_dirs"))
        and bool(details.get("ledger_feed", True))
        and bool(details.get("telemetry_ok", True))
    )
    return {"ok": ok, "details": details_sorted}


def _check_ledger(config: AdaadConfig, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    if not config.ledger_enabled:
        return {"ok": True, "skipped": True}
    if details:
        if not details.get("ledger_dirs", True):
            return {"ok": False, "error": details.get("ledger_dirs_error"), "path": details.get("ledger_feed_path")}
        if not details.get("ledger_feed", True):
            return {"ok": False, "error": details.get("ledger_feed_error"), "path": details.get("ledger_feed_path")}
    try:
        path = ensure_ledger(config)
        return {"ok": True, "path": str(path)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _tail_lines(raw: str | None, *, limit: int = 10) -> list[str]:
    if not raw:
        return []
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_pytest_check(config: AdaadConfig) -> dict[str, Any]:
    if config.resource_tier == ResourceTier.MOBILE:
        return {"ok": True, "skipped": True, "reason": "resource_tier=mobile"}

    if importlib.util.find_spec("pytest") is None:
        return {"ok": True, "skipped": True, "reason": "pytest not installed"}

    cmd = [sys.executable, "-m", "pytest"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "command": cmd}

    stdout_tail = _tail_lines(result.stdout)
    stderr_tail = _tail_lines(result.stderr)
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "command": cmd,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def _iter_imports(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module.split(".")[0]


def _scan_forbidden_modules(root: Path, forbidden: set[str]) -> tuple[list[dict[str, str]], list[str], list[dict[str, str]]]:
    hits: list[dict[str, str]] = []
    scanned: list[str] = []
    errors: list[dict[str, str]] = []
    doctor_path = Path(__file__).resolve()
    for path in sorted(root.rglob("*.py"), key=lambda p: p.as_posix()):
        if path.resolve() == doctor_path:
            continue
        scanned.append(path.relative_to(root).as_posix())
        try:
            source = path.read_text(encoding="utf-8")
        except Exception as exc:
            errors.append({"path": str(path.relative_to(root)), "error": str(exc)})
            continue
        try:
            tree = ast.parse(source)
        except Exception as exc:
            errors.append({"path": str(path.relative_to(root)), "error": str(exc)})
            matched = sorted(
                {module for module in forbidden if f"import {module}" in source or f"from {module}" in source}
            )
            for module in matched or ["unknown"]:
                hits.append({"path": str(path.relative_to(root)), "module": module})
            continue
        modules = set(module for module in _iter_imports(tree) if module in forbidden)
        for module in sorted(modules):
            hits.append({"path": str(path.relative_to(root)), "module": module})
    return hits, scanned, errors


def _check_static_scan(config: AdaadConfig, *, root: Path | None = None) -> dict[str, Any]:
    scan_root = root or Path(__file__).resolve().parent.parent
    root_value = str(scan_root)
    forbidden, scanned, errors = _scan_forbidden_modules(scan_root, FORBIDDEN_MODULES)
    return {
        "ok": not forbidden,
        "tier": config.resource_tier.value,
        "forbidden": forbidden,
        "root": root_value,
        "scanned": scanned,
        "errors": errors,
    }


def run_doctor(cfg: AdaadConfig | None = None, *, scan_root: Path | None = None) -> dict[str, Any]:
    config = cfg or load_config()
    run_id = uuid4().hex

    health_details = check_structure_details(cfg=config)
    checks = {
        "config": _check_config(config),
        "health": _check_structure(config, details=health_details),
        "ledger": _check_ledger(config, details=health_details),
        "pytest": _run_pytest_check(config),
        "static_scan": _check_static_scan(config, root=scan_root),
    }

    ordered_checks = dict(sorted(checks.items()))
    ok = all(check.get("ok", False) for check in ordered_checks.values())
    checks_summary = {
        name: {"ok": bool(check.get("ok", False)), "skipped": bool(check.get("skipped", False))}
        for name, check in ordered_checks.items()
    }

    ledger_appended = False
    ledger_error: str | None = None
    ledger_event: dict[str, Any] | None = None
    if config.ledger_enabled and ordered_checks.get("ledger", {}).get("ok"):
        try:
            event = append_event(
                cfg=config,
                event_type="doctor",
                payload={
                    "action": "doctor",
                    "schema_version": config.log_schema_version,
                    "overall_ok": ok,
                    "run_id": run_id,
                    "resource_tier": config.resource_tier.value,
                    "checks_summary": checks_summary,
                },
                ts=_utc_now_iso_z(),
                actor="doctor",
            )
            ledger_appended = True
            ledger_event = {"event_id": event.get("event_id"), "hash": event.get("hash")}
        except Exception as exc:
            ledger_appended = False
            ledger_error = str(exc)
            ok = False

    return {
        "schema_version": config.log_schema_version,
        "ok": ok,
        "run_id": run_id,
        "checks": ordered_checks,
        "checks_summary": checks_summary,
        "ledger_event": {"appended": ledger_appended, "error": ledger_error, "event": ledger_event},
    }


__all__ = ["run_doctor"]
