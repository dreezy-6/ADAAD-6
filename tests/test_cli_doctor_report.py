import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch


class DummyConfig:
    def __init__(self) -> None:
        self.log_schema_version = "1"
        self.log_path = ".adaad/logs/adaad6.jsonl"
        self.home = "."

    def validate(self) -> None:
        pass


class CliDoctorReportTest(unittest.TestCase):
    def test_doctor_report_flag_emits_human_and_machine_output(self) -> None:
        fake_config = DummyConfig()
        doctor_payload = {
            "ok": True,
            "run_id": "run-123",
            "checks_summary": {
                "config": {"ok": True, "skipped": False},
                "health": {"ok": True, "skipped": False},
            },
        }

        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.run_doctor", return_value=doctor_payload),
        ):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                exit_code = main(["doctor", "run", "--output", "both"])

        self.assertEqual(0, exit_code)
        lines = out.getvalue().splitlines()
        self.assertGreaterEqual(len(lines), 1)
        machine = json.loads(lines[0])
        self.assertTrue(machine["ok"])
        self.assertEqual(doctor_payload, machine["report"])
        self.assertIn("template", machine)
        self.assertIn("human_readable", machine)
        human_lines = err.getvalue().splitlines()
        self.assertTrue(any("Doctor report [run-123]: PASS" in line for line in human_lines))
        self.assertTrue(any(line.strip().startswith("- config: PASS") for line in human_lines))

    def test_doctor_report_path_forwards_to_template(self) -> None:
        fake_config = DummyConfig()
        doctor_payload = {"ok": False, "run_id": "run-456", "checks_summary": {}}

        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.run_doctor", return_value=doctor_payload),
        ):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                exit_code = main(["doctor", "run", "--output", "both", "--report-path", "custom/report.txt"])

        self.assertEqual(1, exit_code)
        machine = json.loads(out.getvalue().splitlines()[0])
        self.assertEqual("custom/report.txt", machine["template"]["meta"]["destination"])

    def test_doctor_template_skips_doctor_run(self) -> None:
        fake_config = DummyConfig()
        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.run_doctor") as doctor_mock,
        ):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                exit_code = main(["doctor", "template", "--report-path", "custom/report.txt"])

        doctor_mock.assert_not_called()
        self.assertEqual(0, exit_code)
        machine = json.loads(out.getvalue().splitlines()[0])
        self.assertTrue(machine["ok"])
        self.assertEqual("custom/report.txt", machine["template"]["meta"]["destination"])
        self.assertEqual("", err.getvalue())

    def test_doctor_template_rejects_run_flags(self) -> None:
        fake_config = DummyConfig()
        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.run_doctor") as doctor_mock,
        ):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                with self.assertRaises(SystemExit) as ctx:
                    main(["doctor", "template", "--output", "both"])

        doctor_mock.assert_not_called()
        self.assertEqual(2, ctx.exception.code)

    def test_doctor_default_run_accepts_flags_without_subcommand(self) -> None:
        fake_config = DummyConfig()
        doctor_payload = {"ok": True, "run_id": "run-789", "checks_summary": {}}

        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.run_doctor", return_value=doctor_payload),
        ):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                exit_code = main(["doctor", "--output", "both"])

        self.assertEqual(0, exit_code)
        machine = json.loads(out.getvalue().splitlines()[0])
        self.assertTrue(machine["ok"])
        self.assertIn("human_readable", machine)

    def test_doctor_template_rejects_parent_output_flag_before_subcommand(self) -> None:
        fake_config = DummyConfig()
        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.run_doctor") as doctor_mock,
        ):
            from adaad6.cli import main

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                with self.assertRaises(SystemExit) as ctx:
                    main(["doctor", "--output", "both", "template"])

        doctor_mock.assert_not_called()
        self.assertEqual(2, ctx.exception.code)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
