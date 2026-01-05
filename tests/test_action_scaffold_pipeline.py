from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from adaad6.config import AdaadConfig, ResourceTier
from adaad6.planning.actions import generate_scaffold, record_ledger, select_template
from adaad6.planning.actions._command_utils import coerce_command, execute_command
from adaad6.planning.actions.run_tests import validate as validate_run_tests


class ScaffoldActionTests(unittest.TestCase):
    def test_select_template_rejects_unavailable(self) -> None:
        validated = select_template.validate({"name": "missing", "available": ["scaffold"]}, AdaadConfig())
        result = select_template.run(validated)
        with self.assertRaisesRegex(ValueError, "failed to select"):
            select_template.postcheck(result, AdaadConfig())

    def test_generate_scaffold_rejects_bytes_components(self) -> None:
        with self.assertRaises(ValueError):
            generate_scaffold.validate({"components": b"core"}, AdaadConfig())

    def test_record_ledger_marks_completion_when_disabled(self) -> None:
        cfg = AdaadConfig(ledger_enabled=False)
        validated = record_ledger.validate({}, cfg)
        result = record_ledger.run(validated)
        self.assertTrue(result["completed"])
        self.assertTrue(result["skipped"])
        self.assertTrue(result["ok"])
        record_ledger.postcheck(result, cfg)

    def test_execute_command_timeout_preserves_schema(self) -> None:
        command = coerce_command(["python", "-c", "import time; time.sleep(0.2)"], default=("python",))
        start = datetime.now()
        result = execute_command(command, timeout=0.01, allowed=("python",))
        elapsed = datetime.now() - start
        self.assertTrue(result["timeout"])
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("returncode", result)
        self.assertLess(elapsed, timedelta(seconds=1))

    def test_execute_command_handles_missing_binary(self) -> None:
        command = coerce_command(["definitely-missing-command"], default=("python",))
        result = execute_command(command, timeout=0.01, allowed=None)
        self.assertFalse(result["timeout"])
        self.assertIsNone(result["returncode"])
        self.assertEqual(result.get("error"), "FileNotFoundError")

    def test_run_tests_rejects_disallowed_command_but_returns_schema(self) -> None:
        cfg = AdaadConfig(resource_tier=ResourceTier.SERVER)
        validated = {"command": ["echo"], "timeout": 1.0, "tier": cfg.resource_tier}
        from adaad6.planning.actions.run_tests import run as run_tests

        result = run_tests(validated)
        self.assertFalse(result["ok"])
        self.assertFalse(result["timeout"])
        self.assertEqual(result.get("returncode"), None)
        self.assertIn("stderr", result)
        self.assertEqual(result.get("error"), "NotPermitted")
        self.assertIn("stdout", result)

    def test_run_tests_default_command_allowed_list(self) -> None:
        cfg = AdaadConfig(resource_tier=ResourceTier.MOBILE)
        validated = validate_run_tests({}, cfg)
        self.assertEqual(["pytest"], validated["command"])
        from adaad6.planning.actions.run_tests import run as run_tests

        result = run_tests(validated)
        self.assertTrue(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertIn("returncode", result)
        self.assertIsNone(result["returncode"])
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("timeout", result)
        self.assertFalse(result["timeout"])
        self.assertIn("error", result)
        self.assertIsNone(result["error"])

    def test_coerce_command_rejects_byte_tokens(self) -> None:
        with self.assertRaises(ValueError):
            coerce_command([b"pytest"], default=("pytest",))

    def test_coerce_command_rejects_empty_sequence(self) -> None:
        with self.assertRaises(ValueError):
            coerce_command([], default=("pytest",))

    def test_execute_command_rejects_empty_command(self) -> None:
        result = execute_command([], timeout=0.01, allowed=None)
        self.assertEqual(result.get("error"), "EmptyCommand")
        self.assertIsNone(result.get("returncode"))
        self.assertFalse(result.get("timeout"))
        self.assertEqual(result.get("stdout"), "")
        self.assertTrue(result.get("stderr"))


if __name__ == "__main__":
    unittest.main()
