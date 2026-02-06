import json
import unittest
from contextlib import redirect_stdout
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch


class DummyConfig:
    def __init__(self) -> None:
        self.log_schema_version = "1"
        self.log_path = ".adaad/logs/adaad6.jsonl"
        self.home = "."

    def validate(self) -> None:
        pass


class CliTemplatesTest(unittest.TestCase):
    def test_doctor_template_via_template_command(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            with redirect_stdout(out):
                exit_code = main(["template", "doctor_report", "--destination", "custom.txt"])

        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue().splitlines()[0])
        self.assertTrue(payload["ok"])
        self.assertEqual("custom.txt", payload["template"]["meta"]["destination"])

    def test_diff_report_template_via_template_command(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            with redirect_stdout(out):
                exit_code = main(["template", "diff_report", "--base-ref", "origin/main", "--destination", "diff.md"])

        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue().splitlines()[0])
        self.assertTrue(payload["ok"])
        template = payload["template"]
        self.assertEqual("diff_report", template["goal"])
        self.assertEqual("origin/main", template["meta"]["base_ref"])
        self.assertEqual("diff.md", template["meta"]["destination"])

    def test_scaffold_template_via_template_command(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            with redirect_stdout(out):
                exit_code = main(["template", "scaffold", "--destination", "scaffold.md"])

        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue().splitlines()[0])
        self.assertTrue(payload["ok"])
        template = payload["template"]
        self.assertEqual("scaffold_plan", template["goal"])
        self.assertEqual("scaffold.md", template["meta"]["destination"])
        self.assertEqual(["ledger_step_complete"], template["steps"][3]["effects"])

    def test_zenith_template_via_template_command(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            with redirect_stdout(out):
                exit_code = main(
                    [
                        "template",
                        "zenith_ui",
                        "--destination",
                        "zenith.jsx",
                        "--operator-name",
                        "Op",
                        "--org-name",
                        "Org",
                    ]
                )

        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue().splitlines()[0])
        template = payload["template"]
        self.assertEqual("zenith_ui", template["goal"])
        self.assertEqual("Op", template["meta"]["operator_name"])
        self.assertEqual("Org", template["meta"]["org_name"])
        self.assertIn("content", template["steps"][0]["params"])

    def test_zenith_dry_hash_strips_content(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            with redirect_stdout(out):
                exit_code = main(["template", "zenith_ui", "--dry-hash"])

        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue().splitlines()[0])
        template = payload["template"]
        self.assertTrue(template["meta"]["dry_hash_only"])
        self.assertIn("content_hash", template["meta"])
        self.assertNotIn("content", template["steps"][0]["params"])
        self.assertEqual("sha256", template["steps"][0]["params"]["hash_algorithm"])

    def test_zenith_minimal_template_via_template_command(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            with redirect_stdout(out):
                exit_code = main(["template", "zenith_ui_minimal", "--dry-hash"])

        self.assertEqual(0, exit_code)
        payload = json.loads(out.getvalue().splitlines()[0])
        template = payload["template"]
        self.assertEqual("zenith_ui_minimal", template["goal"])
        self.assertTrue(template["meta"]["dry_hash_only"])

    def test_dry_hash_rejected_for_non_zenith_template(self) -> None:
        fake_config = DummyConfig()
        with patch("adaad6.config.load_config", return_value=fake_config):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                with self.assertRaises(SystemExit):
                    main(["template", "doctor_report", "--dry-hash"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
