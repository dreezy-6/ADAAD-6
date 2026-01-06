import os
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch

from adaad6.config import AdaadConfig, MutationPolicy, compute_readiness_gate_signature
from adaad6.runtime import health
from adaad6.runtime.gates import EvidenceStore
from adaad6.runtime.boot import boot_sequence


class BootSequenceTest(unittest.TestCase):
    def test_boot_defaults(self) -> None:
        result = boot_sequence(cfg=AdaadConfig())

        self.assertIn("ok", result)
        self.assertIn("mutation_enabled", result)
        self.assertIn("limits", result)
        self.assertIn("checks", result)
        self.assertIn("build", result)
        self.assertIn("ledger", result)

        self.assertFalse(result["mutation_enabled"])
        self.assertEqual(result["limits"]["planner_max_steps"], 25)
        self.assertEqual(result["limits"]["planner_max_seconds"], 2.0)
        self.assertTrue(result["ledger"]["enabled"] is False)
        self.assertTrue(result["ledger"]["ok"])
        self.assertTrue(result["ledger"]["dirs_ok"])
        self.assertIsNone(result["ledger"]["path"])
        self.assertIsNone(result["ledger"]["error"])
        self.assertTrue(result["ledger"]["feed_ok"])
        self.assertIsNone(result["ledger"]["feed_path"])
        self.assertIn("ledger", result["checks"])
        self.assertTrue(result["checks"]["ledger"])
        self.assertIn("ledger_dirs", result["checks"])
        self.assertTrue(result["checks"]["ledger_dirs"])
        self.assertIn("telemetry", result["checks"])
        self.assertTrue(result["checks"]["telemetry"])

    def test_boot_ledger_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_base = Path(tmpdir) / ".adaad" / "ledger"
            ledger_base.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_base), ledger_filename="events.jsonl", home=tmpdir)

            result = boot_sequence(cfg=cfg)

            self.assertTrue(result["ledger"]["enabled"])
            self.assertTrue(result["ledger"]["ok"])
            self.assertTrue(result["ledger"]["dirs_ok"])
            self.assertEqual(Path(result["ledger"]["path"]).name, cfg.ledger_filename)
            self.assertTrue(Path(result["ledger"]["path"]).exists())
            self.assertTrue(result["ledger"]["feed_ok"])
            self.assertTrue(result["ok"])
            self.assertIsNone(result["ledger"]["error"])
            self.assertIn("ledger", result["checks"])
            self.assertTrue(result["checks"]["ledger"])
            self.assertIn("ledger_dirs", result["checks"])
            self.assertTrue(result["checks"]["ledger_dirs"])
            self.assertIn("telemetry", result["checks"])
            self.assertTrue(result["checks"]["telemetry"])

    def test_boot_ledger_failure_sets_ok_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file_dir = Path(tmpdir) / ".adaad" / "ledger" / "events.jsonl"
            ledger_file_dir.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_file_dir.parent), ledger_filename="events.jsonl", home=tmpdir)

            result = boot_sequence(cfg=cfg)

            self.assertTrue(result["ledger"]["enabled"])
            self.assertFalse(result["ledger"]["ok"])
            self.assertFalse(result["ledger"]["dirs_ok"])
            self.assertIsNone(result["ledger"]["path"])
            self.assertIsNotNone(result["ledger"]["error"])
            self.assertFalse(result["ledger"]["feed_ok"])
            self.assertFalse(result["ok"])
            self.assertIn("ledger", result["checks"])
            self.assertFalse(result["checks"]["ledger"])
            self.assertIn("ledger_dirs", result["checks"])
            self.assertFalse(result["checks"]["ledger_dirs"])
            self.assertIn("telemetry", result["checks"])

    def test_mutation_stays_disabled_without_cryovant_lineage(self) -> None:
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, readiness_gate_sig="fake-lineage")

        result = boot_sequence(cfg=cfg)

        self.assertFalse(result["cryovant_gate"]["ok"])
        self.assertFalse(result["mutation_enabled"])
        self.assertEqual("cryovant_evidence_store_missing", result["cryovant_gate"]["reason"])

    def test_mutation_enables_with_valid_cryovant_lineage(self) -> None:
        evidence_store = EvidenceStore()
        lineage_hash = evidence_store.add_lineage({"ancestor": "root", "stage": "alpha"})
        cfg = AdaadConfig(mutation_policy=MutationPolicy.SANDBOXED, readiness_gate_sig=lineage_hash)

        result = boot_sequence(cfg=cfg, evidence_store=evidence_store)

        self.assertTrue(result["cryovant_gate"]["ok"])
        self.assertTrue(result["mutation_enabled"])

    def test_evolutionary_freezes_when_signature_missing(self) -> None:
        with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": "secret"}, clear=True):
            cfg = AdaadConfig(mutation_policy=MutationPolicy.EVOLUTIONARY, readiness_gate_sig=None)

            result = boot_sequence(cfg=cfg)

        self.assertFalse(result["mutation_enabled"])
        self.assertEqual(result["freeze_reason"], "READINESS_GATE_SIGNATURE_MISSING")
        self.assertEqual(result["cryovant_gate"]["reason"], "READINESS_GATE_SIGNATURE_MISSING")

    def test_evolutionary_freezes_when_signature_invalid(self) -> None:
        with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": "secret"}, clear=True):
            cfg = AdaadConfig(mutation_policy=MutationPolicy.EVOLUTIONARY, readiness_gate_sig="invalid")

            result = boot_sequence(cfg=cfg)

        self.assertFalse(result["mutation_enabled"])
        self.assertEqual(result["freeze_reason"], "READINESS_GATE_SIGNATURE_INVALID")
        self.assertEqual(result["cryovant_gate"]["reason"], "READINESS_GATE_SIGNATURE_INVALID")

    def test_evolutionary_enables_when_signature_matches(self) -> None:
        key = "secret"
        with patch.dict("os.environ", {"ADAAD6_CONFIG_SIG_KEY": key}, clear=True):
            base_cfg = AdaadConfig(mutation_policy=MutationPolicy.EVOLUTIONARY, readiness_gate_sig="pending")
            sig = compute_readiness_gate_signature(base_cfg, os.environ, key=key)
            cfg = replace(base_cfg, readiness_gate_sig=sig)

            result = boot_sequence(cfg=cfg)

        self.assertTrue(result["cryovant_gate"]["ok"])
        self.assertTrue(result["mutation_enabled"])

    def test_boot_fails_when_telemetry_export_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(
                home=tmpdir,
                telemetry_exports=("telemetry/metrics.jsonl",),
                ledger_enabled=False,
            )

            result = boot_sequence(cfg=cfg)

            self.assertFalse(result["ok"])
            self.assertFalse(result["checks"]["telemetry"])
            self.assertFalse(result["telemetry"]["ok"])
            self.assertEqual(len(result["telemetry"]["exports"]), 1)
            self.assertFalse(result["telemetry"]["exports"][0]["ok"])

            telemetry_path = Path(tmpdir) / "telemetry" / "metrics.jsonl"
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            telemetry_path.write_text("{}", encoding="utf-8")

            recovered = boot_sequence(cfg=cfg)

            self.assertTrue(recovered["ok"])
            self.assertTrue(recovered["checks"]["telemetry"])
            self.assertTrue(recovered["telemetry"]["ok"])

    def test_boot_fails_when_ledger_feed_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / ".adaad" / "ledger"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir), ledger_filename="events.jsonl", home=tmpdir)
            from adaad6.provenance.ledger import ledger_path as cfg_ledger_path

            ledger_path = cfg_ledger_path(cfg).resolve(strict=False)
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("", encoding="utf-8")

            original_probe = health._probe_feed

            def fake_probe(path: Path) -> tuple[bool, str | None]:
                if path.resolve(strict=False) == ledger_path:
                    return False, "unreadable:nope"
                return original_probe(path)

            with patch("adaad6.runtime.health._probe_feed", side_effect=fake_probe):
                result = boot_sequence(cfg=cfg)

            self.assertFalse(result["ok"])
            self.assertFalse(result["ledger"]["feed_ok"])
            self.assertFalse(result["checks"]["ledger"])

            recovered = boot_sequence(cfg=cfg)

            self.assertTrue(recovered["ok"])
            self.assertTrue(recovered["ledger"]["ok"])
            self.assertTrue(recovered["ledger"]["feed_ok"])


if __name__ == "__main__":
    unittest.main()
