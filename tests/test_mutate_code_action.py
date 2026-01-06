from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock
from unittest.mock import patch

from adaad6.config import AdaadConfig, MutationPolicy, ResourceTier, compute_readiness_gate_signature
from adaad6.planning.actions import mutate_code
from adaad6.runtime.gates import EvidenceStore


def _lineage():
    store = EvidenceStore()
    lineage_hash = store.add_lineage({"ancestor": "root"})
    return store, lineage_hash


class MutateCodeActionTest(unittest.TestCase):
    def test_locked_policy_skips(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.LOCKED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "x = 1"}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertTrue(checked["skipped"])
        self.assertEqual(checked["reason"], "mutation_policy_locked")
        self.assertFalse(checked["ast_ok"])
        self.assertEqual(checked["score"], 0.0)
        self.assertIsNone(checked["mutation_kind"])
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])
        self.assertIsNone(checked["resource_caps"])

    def test_mobile_tier_skips(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.MOBILE)
        validated = mutate_code.validate({"src": "x = 2"}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertTrue(checked["skipped"])
        self.assertEqual(checked["reason"], "resource_tier=mobile")
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_allowlist_blocks_os_import(self) -> None:
        evidence_store, lineage_hash = _lineage()
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "import os\nx = 1", "evidence_store": evidence_store, "lineage_hash": lineage_hash}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertFalse(checked["allowlist_ok"])
        self.assertEqual(checked["reason"], "import_not_allowed")
        self.assertFalse(checked["sandbox_ok"])
        self.assertFalse(checked["skipped"])
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_successful_sandbox_exec_scores(self) -> None:
        evidence_store, lineage_hash = _lineage()
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate(
            {"src": "total = sum([1, 2, 3])\npass\n", "evidence_store": evidence_store, "lineage_hash": lineage_hash},
            cfg,
        )
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertTrue(checked["sandbox_ok"])
        self.assertTrue(checked["ast_ok"])
        self.assertTrue(checked["allowlist_ok"])
        self.assertAlmostEqual(checked["score"], 1.0)
        self.assertEqual(checked["mutation_kind"], "drop_pass")
        self.assertNotEqual(checked["mutated_src"], validated["src"])
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])
        self.assertIsInstance(checked["resource_caps"], dict)
        self.assertIn("supported", checked["resource_caps"])

    def test_doctor_gate_required_for_autopromote(self) -> None:
        key = "secret"
        evidence_store, _ = _lineage()
        with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": key}, clear=True):
            base_cfg = AdaadConfig(
                mutation_policy=MutationPolicy.EVOLUTIONARY,
                resource_tier=ResourceTier.SERVER,
                readiness_gate_sig="pending",
            )
            sig = compute_readiness_gate_signature(base_cfg, os.environ, key=key)
            cfg = replace(base_cfg, readiness_gate_sig=sig)
            validated = mutate_code.validate({"src": "value = 42", "evidence_store": evidence_store}, cfg)
            result = mutate_code.run(validated)
            checked = mutate_code.postcheck(result, cfg)

        self.assertFalse(checked["skipped"])
        self.assertEqual(checked["reason"], "requires_doctor_gate")
        self.assertFalse(checked["ledger_event"])  # ledger disabled by default
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_doctor_gate_allows_promotion_when_report_passes(self) -> None:
        key = "secret"
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            doctor_dir = home / ".adaad" / "doctor"
            doctor_dir.mkdir(parents=True, exist_ok=True)
            (doctor_dir / "latest.json").write_text('{"status": "PASS"}', encoding="utf-8")

            evidence_store, _ = _lineage()
            with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": key}, clear=True):
                base_cfg = AdaadConfig(
                    home=str(home),
                    mutation_policy=MutationPolicy.EVOLUTIONARY,
                    resource_tier=ResourceTier.SERVER,
                    readiness_gate_sig="pending",
                )
                sig = compute_readiness_gate_signature(base_cfg, os.environ, key=key)
                cfg = replace(base_cfg, readiness_gate_sig=sig)
                validated = mutate_code.validate(
                    {"src": "value = 99\npass\n", "evidence_store": evidence_store},
                    cfg,
                )
                result = mutate_code.run(validated)
                checked = mutate_code.postcheck(result, cfg)

            self.assertIsNone(checked["reason"])
            self.assertTrue(checked["sandbox_ok"])
            self.assertIsNotNone(checked["mutation_kind"])
            self.assertTrue(checked["auto_promote"])
            self.assertTrue(checked["doctor_gate_ok"])

    def test_timeout_kills_worker(self) -> None:
        evidence_store, lineage_hash = _lineage()
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "while True:\n    pass", "evidence_store": evidence_store, "lineage_hash": lineage_hash}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertTrue(checked["timeout"])
        self.assertFalse(checked["sandbox_ok"])
        self.assertFalse(checked["skipped"])
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_start_failure_is_reported(self) -> None:
        evidence_store, lineage_hash = _lineage()
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "x = 1", "evidence_store": evidence_store, "lineage_hash": lineage_hash}, cfg)

        with mock.patch("adaad6.planning.actions.mutate_code.mp.get_context") as get_ctx:
            ctx = mock.Mock()
            parent_conn = mock.Mock()
            child_conn = mock.Mock()
            ctx.Pipe.return_value = (parent_conn, child_conn)
            proc = mock.Mock()
            proc.start.side_effect = RuntimeError("boom")
            ctx.Process.return_value = proc
            get_ctx.return_value = ctx

            result = mutate_code.run(validated)
            checked = mutate_code.postcheck(result, cfg)

        self.assertFalse(checked["sandbox_ok"])
        self.assertFalse(checked["timeout"])
        self.assertEqual(checked["reason"], "sandbox_start_failed")
        self.assertFalse(checked["skipped"])

    def test_cryovant_lineage_required_before_mutation(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "value = 5"}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertTrue(checked["skipped"])
        self.assertEqual(checked["reason"], "cryovant_lineage_missing")

    def test_evolutionary_signature_failure_locks_mutation(self) -> None:
        with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": "secret"}, clear=True):
            cfg = AdaadConfig(
                mutation_policy=MutationPolicy.EVOLUTIONARY,
                resource_tier=ResourceTier.SERVER,
                readiness_gate_sig="invalid",
            )
            validated = mutate_code.validate({"src": "x = 1"}, cfg)

        self.assertEqual(validated["policy"], MutationPolicy.LOCKED)
        self.assertEqual(validated["skip_reason"], "READINESS_GATE_SIGNATURE_INVALID")
        self.assertEqual(validated["cfg"].freeze_reason, "READINESS_GATE_SIGNATURE_INVALID")

    def test_evolutionary_signature_allows_mutation_when_valid(self) -> None:
        key = "secret"
        with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": key}, clear=True):
            base_cfg = AdaadConfig(
                mutation_policy=MutationPolicy.EVOLUTIONARY,
                resource_tier=ResourceTier.SERVER,
                readiness_gate_sig="pending",
            )
            sig = compute_readiness_gate_signature(base_cfg, os.environ, key=key)
            cfg = replace(base_cfg, readiness_gate_sig=sig)
            validated = mutate_code.validate({"src": "value = 5"}, cfg)

        self.assertEqual(validated["policy"], MutationPolicy.EVOLUTIONARY)
        self.assertIsNone(validated["skip_reason"])


if __name__ == "__main__":
    unittest.main()
