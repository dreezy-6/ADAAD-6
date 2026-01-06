from __future__ import annotations

import ast
import builtins
import copy
import json
import multiprocessing as mp
try:  # pragma: no cover - platform dependent
    import resource
except ImportError:  # pragma: no cover - platform dependent
    resource = None
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from adaad6.config import AdaadConfig, MutationPolicy, ResourceTier
from adaad6.provenance.ledger import append_event, ensure_ledger
from adaad6.runtime.gates import EvidenceStore, cryovant_lineage_gate


_ALLOWED_IMPORTS: tuple[str, ...] = (
    "math",
    "json",
    "re",
    "statistics",
    "decimal",
    "fractions",
    "typing",
    "itertools",
    "functools",
    "operator",
)

_SAFE_BUILTINS: Mapping[str, Any] = MappingProxyType(
    {
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "sorted": sorted,
        "map": map,
        "filter": filter,
        "any": any,
        "all": all,
        "zip": zip,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "getattr": getattr,
        "setattr": setattr,
        "hasattr": hasattr,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "NotImplementedError": NotImplementedError,
        "print": print,
    }
)


@dataclass(frozen=True)
class MutationReport:
    mutated_src: str
    score: float
    ast_ok: bool
    sandbox_ok: bool
    timeout: bool
    allowlist_ok: bool
    skipped: bool
    reason: str | None = None
    ledger_event: Mapping[str, Any] | None = None
    mutation_kind: str | None = None
    auto_promote: bool = False
    doctor_gate_ok: bool = False
    resource_caps: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutated_src": self.mutated_src,
            "score": self.score,
            "ast_ok": self.ast_ok,
            "sandbox_ok": self.sandbox_ok,
            "timeout": self.timeout,
            "allowlist_ok": self.allowlist_ok,
            "skipped": self.skipped,
            "reason": self.reason,
            "ledger_event": dict(self.ledger_event) if self.ledger_event else None,
            "mutation_kind": self.mutation_kind,
            "auto_promote": self.auto_promote,
            "doctor_gate_ok": self.doctor_gate_ok,
            "resource_caps": dict(self.resource_caps) if isinstance(self.resource_caps, Mapping) else None,
        }


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coerce_source(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ValueError("src must be a string")
    trimmed = raw.strip("\n")
    if not trimmed.strip():
        raise ValueError("src must not be empty")
    return trimmed + "\n"


def _coerce_timeout(raw: Any, *, cfg: AdaadConfig) -> float:
    if raw is None:
        return min(1.0, float(cfg.planner_max_seconds))
    try:
        timeout = float(raw)
    except Exception as exc:
        raise ValueError("timeout must be numeric") from exc
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    # Do not allow excessive runtimes in the sandbox.
    return min(timeout, max(0.01, float(cfg.planner_max_seconds)))


def _iter_imports(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


def _restricted_builtins() -> Mapping[str, Any]:
    safe = dict(_SAFE_BUILTINS)
    safe["__import__"] = _restricted_import
    return {"__builtins__": safe}


def _apply_resource_caps(caps: dict[str, Any]) -> dict[str, Any]:
    applied: dict[str, Any] = {"supported": resource is not None}
    if resource is None:
        return applied
    try:
        if "cpu_seconds" in caps and hasattr(resource, "RLIMIT_CPU"):
            cpu_seconds = int(caps["cpu_seconds"])
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            applied["cpu_seconds"] = cpu_seconds
        if "memory_bytes" in caps and hasattr(resource, "RLIMIT_AS"):
            mem_bytes = int(caps["memory_bytes"])
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            applied["memory_bytes"] = mem_bytes
    except Exception as exc:
        applied["error"] = str(exc)
    return applied


def _safe_send(conn: Any, payload: dict[str, Any]) -> None:
    try:
        conn.send(payload)
    except Exception:
        pass


def _sandbox_worker(code: str, conn: Any, caps: dict[str, Any]) -> None:
    try:
        applied = _apply_resource_caps(caps)
        exec(compile(code, "<mutation>", "exec"), _restricted_builtins(), {})
        _safe_send(conn, {"ok": True, "resource_caps": applied})
    except Exception as exc:  # pragma: no cover - execution path
        _safe_send(conn, {"ok": False, "error": repr(exc)})
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _restricted_import(
    name: str,
    globals_: Mapping[str, Any] | None = None,
    locals_: Mapping[str, Any] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
):
    root = name.split(".")[0]
    if root not in _ALLOWED_IMPORTS:
        raise ImportError(f"import not allowed: {root}")
    return builtins.__import__(name, globals_, locals_, fromlist, level)


def _execute_in_sandbox(code: str, *, timeout: float) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    caps = {"cpu_seconds": int(max(1, timeout)), "memory_bytes": 128 * 1024 * 1024}
    proc = ctx.Process(target=_sandbox_worker, args=(code, child_conn, caps))
    try:
        proc.start()
    except Exception as exc:
        try:
            child_conn.close()
        except Exception:
            pass
        try:
            parent_conn.close()
        except Exception:
            pass
        return {"ok": False, "error": f"start_failed:{exc!r}", "exitcode": None}
    finally:
        try:
            child_conn.close()
        except Exception:
            pass
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        try:
            parent_conn.close()
        except Exception:
            pass
        return {"ok": False, "timeout": True, "exitcode": proc.exitcode}
    try:
        if parent_conn.poll(0):
            try:
                result = parent_conn.recv()
            except Exception:
                return {"ok": False, "error": "no_result", "exitcode": proc.exitcode}
        else:
            return {"ok": False, "error": "no_result_no_message", "exitcode": proc.exitcode}
        if isinstance(result, dict) and "exitcode" not in result:
            result["exitcode"] = proc.exitcode
        return result
    finally:
        try:
            parent_conn.close()
        except Exception:
            pass


def _record_ledger(cfg: AdaadConfig, payload: dict[str, Any]) -> Mapping[str, Any] | None:
    if not cfg.ledger_enabled or cfg.ledger_readonly:
        return None
    try:
        ensure_ledger(cfg)
        event = append_event(
            cfg=cfg,
            event_type="mutation_attempt",
            payload=payload,
            ts=_utc_now_iso_z(),
            actor="mutate_code",
        )
        return {"event_id": event.get("event_id"), "hash": event.get("hash")}
    except Exception as exc:  # pragma: no cover - defensive logging
        return {"error": str(exc)}


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    src = _coerce_source(params.get("src", ""))
    timeout = _coerce_timeout(params.get("timeout"), cfg=cfg)
    evidence_store: EvidenceStore | None = params.get("evidence_store")
    lineage_hash = params.get("lineage_hash") or cfg.readiness_gate_sig
    skip_reason: str | None = None
    if cfg.mutation_policy == MutationPolicy.LOCKED:
        skip_reason = "mutation_policy_locked"
    elif cfg.resource_tier == ResourceTier.MOBILE:
        skip_reason = "resource_tier=mobile"
    gate = cryovant_lineage_gate(evidence_store=evidence_store, lineage_hash=lineage_hash)
    if skip_reason is None and not gate.ok:
        skip_reason = gate.reason or "cryovant_lineage_blocked"
    return {
        "src": src,
        "timeout": timeout,
        "policy": cfg.mutation_policy,
        "resource_tier": cfg.resource_tier,
        "skip_reason": skip_reason,
        "cfg": cfg,
        "lineage_hash": lineage_hash,
    }


class _PassStrippingMutator(ast.NodeTransformer):
    mutation_kind = "drop_pass"

    def visit_Module(self, node: ast.Module) -> ast.AST:  # noqa: N802
        mutated_body = []
        for child in node.body:
            if isinstance(child, ast.Pass):
                continue
            mutated_body.append(self.visit(child))
        node.body = mutated_body
        return node


def _mutate_source(tree: ast.Module) -> tuple[str, str | None]:
    mutator = _PassStrippingMutator()
    original_dump = ast.dump(tree, include_attributes=False)
    mutated = mutator.visit(ast.fix_missing_locations(copy.deepcopy(tree)))
    if mutated is None:
        mutated = ast.Module(body=[], type_ignores=[])
    mutated_src = ast.unparse(mutated).strip() + "\n"
    mutation_kind = (
        mutator.mutation_kind
        if original_dump != ast.dump(mutated, include_attributes=False)
        else None
    )
    return mutated_src, mutation_kind


def _doctor_gate(cfg: AdaadConfig) -> tuple[bool, str | None]:
    home = Path(cfg.home).expanduser() if getattr(cfg, "home", None) else Path.home()
    report_path = home / ".adaad" / "doctor" / "latest.json"
    try:
        if not report_path.exists():
            return False, "doctor_report_missing"
        data = json.loads(report_path.read_text(encoding="utf-8"))
        status = str(data.get("status", "")).lower()
        if status != "pass":
            return False, "doctor_report_not_pass"
        return True, None
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"doctor_report_invalid:{exc}"


def run(validated: dict[str, Any]) -> dict[str, Any]:
    skip_reason = validated.get("skip_reason")
    if skip_reason:
        return MutationReport(
            mutated_src=validated["src"],
            score=0.0,
            ast_ok=False,
            sandbox_ok=False,
            timeout=False,
            allowlist_ok=False,
            skipped=True,
            reason=skip_reason,
            mutation_kind=None,
            auto_promote=False,
            doctor_gate_ok=False,
            resource_caps=None,
        ).to_dict()

    src = validated["src"]
    timeout = float(validated["timeout"])
    cfg: AdaadConfig = validated["cfg"]

    original_tree = ast.parse(src)
    mutated_src, mutation_kind = _mutate_source(original_tree)
    verified_tree = ast.parse(mutated_src)

    # Enforce import allowlist.
    imported = _iter_imports(verified_tree)
    allowlist_ok = all(module in _ALLOWED_IMPORTS for module in imported)
    if not allowlist_ok:
        return MutationReport(
            mutated_src=mutated_src,
            score=0.0,
            ast_ok=True,
            sandbox_ok=False,
            timeout=False,
            allowlist_ok=False,
            skipped=False,
            reason="import_not_allowed",
            mutation_kind=mutation_kind,
            auto_promote=False,
            doctor_gate_ok=False,
            resource_caps=None,
        ).to_dict()

    sandbox_result = _execute_in_sandbox(mutated_src, timeout=timeout)
    sandbox_ok = bool(sandbox_result.get("ok"))
    error_detail = sandbox_result.get("error") if isinstance(sandbox_result, dict) else None
    timed_out = bool(sandbox_result.get("timeout")) or error_detail in ("no_result", "no_result_no_message")
    resource_caps = sandbox_result.get("resource_caps") if isinstance(sandbox_result, dict) else None
    score = 1.0 if sandbox_ok else 0.0

    doctor_gate_ok, doctor_reason = _doctor_gate(cfg)
    can_promote = (
        sandbox_ok
        and allowlist_ok
        and cfg.mutation_policy == MutationPolicy.EVOLUTIONARY
        and cfg.resource_tier == ResourceTier.SERVER
    )
    auto_promote = can_promote and doctor_gate_ok
    gate_reason: str | None = "requires_doctor_gate" if can_promote and not doctor_gate_ok else None
    if isinstance(error_detail, str) and error_detail.startswith("start_failed:") and gate_reason is None:
        gate_reason = "sandbox_start_failed"
    if timed_out and gate_reason is None:
        gate_reason = "timeout"
    if not sandbox_ok and error_detail and gate_reason is None:
        gate_reason = "sandbox_error"

    ledger_payload = {
        "policy": cfg.mutation_policy.value,
        "resource_tier": cfg.resource_tier.value,
        "ast_ok": True,
        "allowlist_ok": allowlist_ok,
        "sandbox_ok": sandbox_ok,
        "timeout": timed_out,
        "score": score,
        "auto_promote": auto_promote,
        "doctor_gate": doctor_gate_ok,
        "doctor_reason": doctor_reason,
        "mutation_kind": mutation_kind,
        "resource_caps": resource_caps,
        "sandbox_error": error_detail,
        "exitcode": sandbox_result.get("exitcode"),
    }
    ledger_event = _record_ledger(cfg, ledger_payload)

    return MutationReport(
        mutated_src=mutated_src,
        score=score,
        ast_ok=True,
        sandbox_ok=sandbox_ok,
        timeout=timed_out,
        allowlist_ok=allowlist_ok,
        skipped=False,
        reason=gate_reason,
        ledger_event=ledger_event,
        mutation_kind=mutation_kind,
        auto_promote=auto_promote,
        doctor_gate_ok=doctor_gate_ok,
        resource_caps=resource_caps if isinstance(resource_caps, dict) else None,
    ).to_dict()


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("mutate_code result must be a dict")
    required = {"mutated_src", "score", "ast_ok", "sandbox_ok", "timeout", "allowlist_ok", "skipped"}
    missing = [field for field in required if field not in result]
    if missing:
        raise ValueError(f"mutate_code result missing fields: {', '.join(sorted(missing))}")
    if cfg.resource_tier == ResourceTier.MOBILE and not result.get("skipped"):
        raise ValueError("mobile tier must skip mutation")
    if cfg.mutation_policy == MutationPolicy.LOCKED and not result.get("skipped"):
        raise ValueError("mutation_policy locked must skip mutation")
    return result


__all__ = ["validate", "run", "postcheck"]
