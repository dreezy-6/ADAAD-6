from __future__ import annotations

from typing import Any

from adaad6.kernel.failures import DETERMINISM_BREACH, EVIDENCE_MISSING, INTEGRITY_VIOLATION, KernelCrash


def _require_fields(obj: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        if field not in obj:
            raise KernelCrash(EVIDENCE_MISSING, f"Missing required field: {field}")


def _ensure_type(value: Any, expected_type: type, field: str, code: str = INTEGRITY_VIOLATION) -> None:
    if not isinstance(value, expected_type):
        raise KernelCrash(code, f"{field} must be {expected_type.__name__}")


def validate_authority_source(obj: dict[str, Any]) -> None:
    _require_fields(obj, ["type", "version", "authority_domain", "scope", "mandate"])
    if obj.get("type") != "AuthoritySource":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid authority source type")
    # authority_domain is the liability domain identifier
    if not obj.get("authority_domain"):
        raise KernelCrash(INTEGRITY_VIOLATION, "authority_domain must be set")
    if not obj.get("mandate"):
        raise KernelCrash(INTEGRITY_VIOLATION, "mandate must be set")
    scope = obj.get("scope")
    _ensure_type(scope, dict, "scope")
    if "can_execute" not in scope or "can_issue_capabilities" not in scope:
        raise KernelCrash(EVIDENCE_MISSING, "scope missing required flags")
    _ensure_type(scope.get("can_execute"), bool, "scope.can_execute")
    _ensure_type(scope.get("can_issue_capabilities"), bool, "scope.can_issue_capabilities")


def validate_proposal(obj: dict[str, Any]) -> None:
    _require_fields(obj, ["type", "version", "proposal_kind"])
    if obj.get("type") != "Proposal":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid proposal type")
    proposal_kind = obj.get("proposal_kind")
    if proposal_kind == "adapter_call":
        required = ["adapter", "intent", "inputs", "requested_effects", "counterfactual_budget"]
        _require_fields(obj, required)


def validate_gate_result(obj: dict[str, Any]) -> None:
    _require_fields(obj, ["type", "version", "gate_id", "result", "deterministic"])
    if obj.get("type") != "GateResult":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid gate result type")
    result = obj.get("result")
    if result not in ("PASS", "FAIL"):
        raise KernelCrash(DETERMINISM_BREACH, "Gate result must be PASS or FAIL")
    if obj.get("deterministic") is not True:
        raise KernelCrash(DETERMINISM_BREACH, "Gate must be deterministic")


def validate_capability_token(obj: dict[str, Any]) -> None:
    _require_fields(obj, ["type", "version", "authority_hash", "decay_only", "limits", "scopes"])
    if obj.get("type") != "CapabilityToken":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid capability token type")
    _ensure_type(obj.get("authority_hash"), str, "authority_hash")
    _ensure_type(obj.get("decay_only"), bool, "decay_only")
    if obj.get("decay_only") is not True:
        raise KernelCrash(INTEGRITY_VIOLATION, "decay_only must be True")
    _ensure_type(obj.get("limits"), dict, "limits")
    limits = obj.get("limits") or {}
    if "expires_at" not in limits or "max_calls" not in limits:
        raise KernelCrash(EVIDENCE_MISSING, "limits missing required fields")
    _ensure_type(limits["expires_at"], str, "limits.expires_at")
    _ensure_type(limits["max_calls"], int, "limits.max_calls")
    if limits["max_calls"] < 1:
        raise KernelCrash(INTEGRITY_VIOLATION, "limits.max_calls must be >= 1")
    _ensure_type(obj.get("scopes"), list, "scopes")
    if not obj["scopes"]:
        raise KernelCrash(INTEGRITY_VIOLATION, "scopes must be non-empty")
    for scope in obj["scopes"]:
        _ensure_type(scope, str, "scopes[]")


def validate_counterfactual_summary(obj: dict[str, Any]) -> None:
    _require_fields(obj, ["type", "version", "budget", "rejected", "unlisted_commitment"])
    if obj.get("type") != "CounterfactualSummary":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid counterfactual summary type")
    _ensure_type(obj.get("budget"), int, "budget")
    if obj["budget"] < 0:
        raise KernelCrash(INTEGRITY_VIOLATION, "budget must be non-negative")
    _ensure_type(obj.get("rejected"), list, "rejected")
    if len(obj["rejected"]) > obj["budget"]:
        raise KernelCrash(INTEGRITY_VIOLATION, "rejected count exceeds budget")
    for item in obj["rejected"]:
        _ensure_type(item, dict, "rejected[]")
        _require_fields(item, ["alt", "reason"])
        _ensure_type(item.get("alt"), str, "rejected[].alt")
        _ensure_type(item.get("reason"), str, "rejected[].reason")
    _ensure_type(obj.get("unlisted_commitment"), str, "unlisted_commitment")


def validate_evidence_bundle(obj: dict[str, Any]) -> None:
    required = [
        "type",
        "version",
        "authority_hash",
        "proposal_hash",
        "gate_result_hashes",
        "capability_hashes",
        "counterfactual_hash",
        "will_emit_execution_record",
    ]
    _require_fields(obj, required)
    if obj.get("type") != "EvidenceBundle":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid evidence bundle type")
    _ensure_type(obj.get("gate_result_hashes"), list, "gate_result_hashes")
    _ensure_type(obj.get("capability_hashes"), list, "capability_hashes")
    if not isinstance(obj.get("will_emit_execution_record"), bool):
        raise KernelCrash(INTEGRITY_VIOLATION, "will_emit_execution_record must be boolean")


def validate_execution_record(obj: dict[str, Any]) -> None:
    _require_fields(
        obj,
        ["type", "version", "evidence_bundle_hash", "outcome", "reason", "refusal_mode"],
    )
    if obj.get("type") != "ExecutionRecord":
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid execution record type")
    refusal_mode = obj.get("refusal_mode")
    if refusal_mode not in ("AUTHORITY_DENIED", "GATE_FAIL"):
        raise KernelCrash(INTEGRITY_VIOLATION, "Invalid refusal_mode")
    if refusal_mode == "GATE_FAIL":
        _require_fields(obj, ["failed_gate_id"])
        if not obj.get("failed_gate_id"):
            raise KernelCrash(INTEGRITY_VIOLATION, "failed_gate_id required for GATE_FAIL")
    else:
        # AUTHORITY_DENIED may omit failed_gate_id or provide empty
        pass


__all__ = [
    "validate_authority_source",
    "validate_proposal",
    "validate_gate_result",
    "validate_capability_token",
    "validate_counterfactual_summary",
    "validate_evidence_bundle",
    "validate_execution_record",
]
