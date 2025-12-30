from __future__ import annotations

from typing import Any, Callable

from adaad6.kernel.failures import EVIDENCE_MISSING, INTEGRITY_VIOLATION, UNLOGGED_EXECUTION, KernelCrash
from adaad6.kernel.hashing import hash_object
from adaad6.kernel.schema import (
    validate_authority_source,
    validate_capability_token,
    validate_counterfactual_summary,
    validate_evidence_bundle,
    validate_gate_result,
    validate_proposal,
)

Resolver = Callable[[str], dict[str, Any] | None]


def _resolve(resolver: Resolver, expected_hash: str, what: str) -> dict[str, Any]:
    if not expected_hash:
        raise KernelCrash(EVIDENCE_MISSING, f"Missing hash for {what}")
    node = resolver(expected_hash)
    if node is None:
        raise KernelCrash(EVIDENCE_MISSING, f"Missing node for {what}")
    actual_hash = hash_object({k: v for k, v in node.items() if k != "hash"})
    if actual_hash != expected_hash:
        raise KernelCrash(INTEGRITY_VIOLATION, f"Hash mismatch for {what}")
    return node


def _evaluate(bundle: dict[str, Any], resolver: Resolver) -> tuple[bool, str | None]:
    if "hash" not in bundle:
        raise KernelCrash(EVIDENCE_MISSING, "Evidence bundle missing hash")
    bundle_hash = bundle["hash"]
    expected_bundle_hash = hash_object({k: v for k, v in bundle.items() if k != "hash"})
    if bundle_hash != expected_bundle_hash:
        raise KernelCrash(INTEGRITY_VIOLATION, "Evidence bundle hash mismatch")

    validate_evidence_bundle(bundle)

    authority = _resolve(resolver, bundle["authority_hash"], "authority")
    validate_authority_source(authority)
    scope = authority.get("scope") or {}
    authority_denied = scope.get("can_execute") is False

    proposal = _resolve(resolver, bundle["proposal_hash"], "proposal")
    validate_proposal(proposal)

    counterfactual = _resolve(resolver, bundle["counterfactual_hash"], "counterfactual")
    validate_counterfactual_summary(counterfactual)

    gate_hashes = bundle.get("gate_result_hashes", [])
    gate_failed = False
    for gate_hash in gate_hashes:
        gate = _resolve(resolver, gate_hash, "gate")
        validate_gate_result(gate)
        if gate["result"] == "FAIL":
            gate_failed = True

    capability_hashes = bundle.get("capability_hashes", [])
    for cap_hash in capability_hashes:
        token = _resolve(resolver, cap_hash, "capability token")
        validate_capability_token(token)
        if token.get("authority_hash") != bundle["authority_hash"]:
            raise KernelCrash(INTEGRITY_VIOLATION, "Capability token authority mismatch")

    if bundle.get("will_emit_execution_record") is not True:
        raise KernelCrash(UNLOGGED_EXECUTION, "Execution record emission disabled")

    refusal_mode: str | None = None
    if authority_denied:
        refusal_mode = "AUTHORITY_DENIED"
    elif gate_failed:
        refusal_mode = "GATE_FAIL"

    admissible = refusal_mode is None
    return admissible, refusal_mode


def is_admissible(bundle: dict[str, Any], resolver: Resolver) -> bool:
    admissible, _ = _evaluate(bundle, resolver)
    return admissible


def refusal_mode(bundle: dict[str, Any], resolver: Resolver) -> str | None:
    _, mode = _evaluate(bundle, resolver)
    return mode


__all__ = ["is_admissible", "refusal_mode"]
