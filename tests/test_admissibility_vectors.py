import copy
import unittest

from adaad6.kernel import (
    DETERMINISM_BREACH,
    EVIDENCE_MISSING,
    INTEGRITY_VIOLATION,
    UNLOGGED_EXECUTION,
    KernelCrash,
    VECTOR_DAG0,
    attach_hash,
)
from adaad6.kernel.admissibility import is_admissible, refusal_mode
from adaad6.kernel.record import make_refusal_record


class AdmissibilityVectorsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.vector = VECTOR_DAG0
        self.nodes = dict(self.vector["nodes"])
        self.bundle = copy.deepcopy(self.vector["evidence_bundle"])

    def _resolver(self, nodes):
        return lambda h: nodes.get(h)

    def test_dag0_refusal_is_not_admissible(self) -> None:
        admissible = is_admissible(self.bundle, self._resolver(self.nodes))
        self.assertFalse(admissible)
        mode = refusal_mode(self.bundle, self._resolver(self.nodes))
        self.assertEqual(mode, "AUTHORITY_DENIED")
        refusal = make_refusal_record(
            self.bundle["hash"], refusal_mode=mode, failed_gate_id="success-justification"
        )
        self.assertEqual(refusal["hash"], attach_hash({k: v for k, v in refusal.items() if k != "hash"})["hash"])
        self.assertEqual(refusal["refusal_mode"], "AUTHORITY_DENIED")

    def test_missing_execution_record_flag_crashes(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["will_emit_execution_record"] = False
        bundle = attach_hash({k: v for k, v in bundle.items() if k != "hash"})
        with self.assertRaises(KernelCrash) as ctx:
            is_admissible(bundle, self._resolver(self.nodes))
        self.assertEqual(ctx.exception.code, UNLOGGED_EXECUTION)

    def test_gate_with_invalid_result_crashes(self) -> None:
        nodes = dict(self.nodes)
        bad_gate = copy.deepcopy(self.vector["gate_results"][0])
        bad_gate["result"] = "MAYBE"
        bad_gate = attach_hash({k: v for k, v in bad_gate.items() if k != "hash"})
        nodes[bad_gate["hash"]] = bad_gate
        bundle = copy.deepcopy(self.bundle)
        bundle["gate_result_hashes"] = [bad_gate["hash"]] + bundle["gate_result_hashes"][1:]
        bundle = attach_hash({k: v for k, v in bundle.items() if k != "hash"})
        with self.assertRaises(KernelCrash) as ctx:
            is_admissible(bundle, self._resolver(nodes))
        self.assertEqual(ctx.exception.code, DETERMINISM_BREACH)

    def test_missing_authority_crashes(self) -> None:
        nodes = {k: v for k, v in self.nodes.items() if k != self.vector["authority"]["hash"]}
        with self.assertRaises(KernelCrash) as ctx:
            is_admissible(self.bundle, self._resolver(nodes))
        self.assertEqual(ctx.exception.code, EVIDENCE_MISSING)

    def test_capability_authority_mismatch_crashes(self) -> None:
        nodes = dict(self.nodes)
        bad_capability = copy.deepcopy(self.vector["capability_token"])
        bad_capability["authority_hash"] = "deadbeef" * 8
        bad_capability = attach_hash({k: v for k, v in bad_capability.items() if k != "hash"})
        nodes[bad_capability["hash"]] = bad_capability
        bundle = copy.deepcopy(self.bundle)
        bundle["capability_hashes"] = [bad_capability["hash"]]
        bundle = attach_hash({k: v for k, v in bundle.items() if k != "hash"})
        with self.assertRaises(KernelCrash) as ctx:
            is_admissible(bundle, self._resolver(nodes))
        self.assertEqual(ctx.exception.code, INTEGRITY_VIOLATION)

    def test_authority_denied_even_when_gates_pass(self) -> None:
        nodes = dict(self.nodes)
        # Start from an authority that allows execution
        authority_allow = copy.deepcopy(self.vector["authority"])
        authority_allow["scope"]["can_execute"] = True
        authority_allow = attach_hash({k: v for k, v in authority_allow.items() if k != "hash"})
        nodes[authority_allow["hash"]] = authority_allow

        cap_allow = copy.deepcopy(self.vector["capability_token"])
        cap_allow["authority_hash"] = authority_allow["hash"]
        cap_allow = attach_hash({k: v for k, v in cap_allow.items() if k != "hash"})
        nodes[cap_allow["hash"]] = cap_allow

        # Gates all PASS
        gate_hashes: list[str] = []
        for gate in self.vector["gate_results"]:
            gate_copy = copy.deepcopy(gate)
            gate_copy["result"] = "PASS"
            gate_copy = attach_hash({k: v for k, v in gate_copy.items() if k != "hash"})
            nodes[gate_copy["hash"]] = gate_copy
            gate_hashes.append(gate_copy["hash"])

        bundle = copy.deepcopy(self.bundle)
        bundle["authority_hash"] = authority_allow["hash"]
        bundle["capability_hashes"] = [cap_allow["hash"]]
        bundle["gate_result_hashes"] = gate_hashes
        bundle = attach_hash({k: v for k, v in bundle.items() if k != "hash"})

        # Now replace authority with a denying authority
        authority_deny = copy.deepcopy(authority_allow)
        authority_deny["scope"]["can_execute"] = False
        authority_deny = attach_hash({k: v for k, v in authority_deny.items() if k != "hash"})
        nodes[authority_deny["hash"]] = authority_deny

        cap_deny = copy.deepcopy(cap_allow)
        cap_deny["authority_hash"] = authority_deny["hash"]
        cap_deny = attach_hash({k: v for k, v in cap_deny.items() if k != "hash"})
        nodes[cap_deny["hash"]] = cap_deny

        bundle["authority_hash"] = authority_deny["hash"]
        bundle["capability_hashes"] = [cap_deny["hash"]]
        bundle = attach_hash({k: v for k, v in bundle.items() if k != "hash"})

        admissible = is_admissible(bundle, self._resolver(nodes))
        self.assertFalse(admissible)
        mode = refusal_mode(bundle, self._resolver(nodes))
        self.assertEqual(mode, "AUTHORITY_DENIED")


if __name__ == "__main__":
    unittest.main()
