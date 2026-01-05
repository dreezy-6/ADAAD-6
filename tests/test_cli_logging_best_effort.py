import unittest
from unittest.mock import patch


class DummyConfig:
    def __init__(self) -> None:
        self.log_schema_version = "1"
        self.log_path = ".adaad/logs/adaad6.jsonl"
        self.home = "."

    def validate(self) -> None:
        pass


class CliLoggingBestEffortTest(unittest.TestCase):
    def test_logging_failures_do_not_crash_health(self) -> None:
        fake_config = DummyConfig()
        with (
            patch("adaad6.config.load_config", return_value=fake_config),
            patch("adaad6.assurance.logging.append_jsonl_log_event", side_effect=RuntimeError("boom")),
            patch("adaad6.runtime.health.check_structure_details") as check_structure_details,
        ):
            check_structure_details.return_value = {"structure": {"ok": True}, "ledger_dirs": {"ok": True}}

            from adaad6.cli import main

            exit_code = main(["health"])
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
