import json
import unittest
from contextlib import redirect_stdout
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
