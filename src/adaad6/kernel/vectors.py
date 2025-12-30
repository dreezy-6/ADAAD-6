from __future__ import annotations

from adaad6.kernel.hashing import attach_hash
from adaad6.kernel.record import make_refusal_record


def _build_vector() -> dict:
    authority = attach_hash(
        {
            "type": "AuthoritySource",
            "version": "1",
            "authority_domain": "local_operator",
            "mandate": "Refusal-only dry run",
            "scope": {
                "can_execute": False,
                "can_issue_capabilities": False,
            },
        }
    )

    proposal = attach_hash(
        {
            "type": "Proposal",
            "version": "1",
            "proposal_kind": "adapter_call",
            "adapter": "echo",
            "intent": "refusal_demo",
            "inputs": {"message": "refuse"},
            "requested_effects": ["log_refusal"],
            "counterfactual_budget": 3,
        }
    )

    gate_results = [
        attach_hash(
            {
                "type": "GateResult",
                "version": "1",
                "gate_id": "success-justification",
                "result": "PASS",
                "deterministic": True,
                "detail": "Success justification satisfied",
            }
        ),
        attach_hash(
            {
                "type": "GateResult",
                "version": "1",
                "gate_id": "capability-alignment",
                "result": "PASS",
                "deterministic": True,
                "detail": "Capabilities confined",
            }
        ),
        attach_hash(
            {
                "type": "GateResult",
                "version": "1",
                "gate_id": "determinism-check",
                "result": "PASS",
                "deterministic": True,
                "detail": "Inputs deterministic",
            }
        ),
    ]

    capability_token = attach_hash(
        {
            "type": "CapabilityToken",
            "version": "1",
            "authority_hash": authority["hash"],
            "scopes": ["call_adapter:echo"],
            "decay_only": True,
            "limits": {
                "expires_at": "2026-01-01T00:00:00Z",
                "max_calls": 1,
            },
        }
    )

    counterfactual = attach_hash(
        {
            "type": "CounterfactualSummary",
            "version": "1",
            "budget": 3,
            "rejected": [
                {"alt": "do_nothing", "reason": "fails_success_necessity"},
                {"alt": "delegate", "reason": "off-policy"},
            ],
            "unlisted_commitment": "no-other-branches",
        }
    )

    evidence_bundle = attach_hash(
        {
            "type": "EvidenceBundle",
            "version": "1",
            "authority_hash": authority["hash"],
            "proposal_hash": proposal["hash"],
            "gate_result_hashes": [g["hash"] for g in gate_results],
            "capability_hashes": [capability_token["hash"]],
            "counterfactual_hash": counterfactual["hash"],
            "will_emit_execution_record": True,
        }
    )

    refusal_record = make_refusal_record(
        bundle_hash=evidence_bundle["hash"],
        refusal_mode="AUTHORITY_DENIED",
        failed_gate_id="success-justification",
    )

    nodes = {
        authority["hash"]: authority,
        proposal["hash"]: proposal,
        gate_results[0]["hash"]: gate_results[0],
        gate_results[1]["hash"]: gate_results[1],
        gate_results[2]["hash"]: gate_results[2],
        capability_token["hash"]: capability_token,
        counterfactual["hash"]: counterfactual,
        evidence_bundle["hash"]: evidence_bundle,
        refusal_record["hash"]: refusal_record,
    }

    return {
        "authority": authority,
        "proposal": proposal,
        "gate_results": gate_results,
        "capability_token": capability_token,
        "counterfactual": counterfactual,
        "evidence_bundle": evidence_bundle,
        "refusal_record": refusal_record,
        "nodes": nodes,
    }


VECTOR_DAG0 = _build_vector()

__all__ = ["VECTOR_DAG0"]
