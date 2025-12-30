import tempfile
import unittest
from pathlib import Path

from adaad6.config import AdaadConfig
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
        self.assertIsNone(result["ledger"]["path"])
        self.assertIsNone(result["ledger"]["error"])
        self.assertIn("ledger", result["checks"])
        self.assertTrue(result["checks"]["ledger"])

    def test_boot_ledger_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_file="events.jsonl")

            result = boot_sequence(cfg=cfg)

            self.assertTrue(result["ledger"]["enabled"])
            self.assertTrue(result["ledger"]["ok"])
            self.assertEqual(Path(result["ledger"]["path"]).name, cfg.ledger_file)
            self.assertTrue(Path(result["ledger"]["path"]).exists())
            self.assertTrue(result["ok"])
            self.assertIsNone(result["ledger"]["error"])
            self.assertIn("ledger", result["checks"])
            self.assertTrue(result["checks"]["ledger"])

    def test_boot_ledger_failure_sets_ok_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file_dir = Path(tmpdir) / "events.jsonl"
            ledger_file_dir.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_file="events.jsonl")

            result = boot_sequence(cfg=cfg)

            self.assertTrue(result["ledger"]["enabled"])
            self.assertFalse(result["ledger"]["ok"])
            self.assertIsNone(result["ledger"]["path"])
            self.assertIsNotNone(result["ledger"]["error"])
            self.assertFalse(result["ok"])
            self.assertIn("ledger", result["checks"])
            self.assertFalse(result["checks"]["ledger"])


if __name__ == "__main__":
    unittest.main()
