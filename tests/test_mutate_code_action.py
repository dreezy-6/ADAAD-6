from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adaad6.config import AdaadConfig, MutationPolicy, ResourceTier
from adaad6.planning.actions import mutate_code


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
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "import os\nx = 1"}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertFalse(checked["allowlist_ok"])
        self.assertEqual(checked["reason"], "import_not_allowed")
        self.assertFalse(checked["sandbox_ok"])
        self.assertFalse(checked["skipped"])
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_successful_sandbox_exec_scores(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "total = sum([1, 2, 3])\npass\n"}, cfg)
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
        cfg = AdaadConfig(mutation_policy=MutationPolicy.EVOLUTIONARY, resource_tier=ResourceTier.SERVER, readiness_gate_sig=None)
        validated = mutate_code.validate({"src": "value = 42"}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertFalse(checked["skipped"])
        self.assertEqual(checked["reason"], "requires_doctor_gate")
        self.assertFalse(checked["ledger_event"])  # ledger disabled by default
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_doctor_gate_allows_promotion_when_report_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            doctor_dir = home / ".adaad" / "doctor"
            doctor_dir.mkdir(parents=True, exist_ok=True)
            (doctor_dir / "latest.json").write_text('{"status": "PASS"}', encoding="utf-8")

            cfg = AdaadConfig(home=str(home), mutation_policy=MutationPolicy.EVOLUTIONARY, resource_tier=ResourceTier.SERVER)
            validated = mutate_code.validate({"src": "value = 99\npass\n"}, cfg)
            result = mutate_code.run(validated)
            checked = mutate_code.postcheck(result, cfg)

            self.assertIsNone(checked["reason"])
            self.assertTrue(checked["sandbox_ok"])
            self.assertIsNotNone(checked["mutation_kind"])
            self.assertTrue(checked["auto_promote"])
            self.assertTrue(checked["doctor_gate_ok"])

    def test_timeout_kills_worker(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "while True:\n    pass"}, cfg)
        result = mutate_code.run(validated)
        checked = mutate_code.postcheck(result, cfg)

        self.assertTrue(checked["timeout"])
        self.assertFalse(checked["sandbox_ok"])
        self.assertFalse(checked["skipped"])
        self.assertFalse(checked["auto_promote"])
        self.assertFalse(checked["doctor_gate_ok"])

    def test_start_failure_is_reported(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, resource_tier=ResourceTier.SERVER)
        validated = mutate_code.validate({"src": "x = 1"}, cfg)

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


if __name__ == "__main__":
    unittest.main()
