import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from adaad6.config import AdaadConfig
from adaad6.provenance.ledger import append_event


class CliLedgerCommandsTest(unittest.TestCase):
    def _run_cli(self, args: list[str], cfg: AdaadConfig) -> tuple[int, list[str]]:
        buffer = StringIO()
        with patch("adaad6.config.load_config", return_value=cfg):
            from adaad6.cli import main

            with redirect_stdout(buffer):
                exit_code = main(args)
        return exit_code, buffer.getvalue().splitlines()

    def test_ledger_tail_streams_events(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_filename="events.jsonl")
            first = append_event(cfg, "alpha", {"value": 1}, "2024-01-01T00:00:00Z", "tester")
            second = append_event(cfg, "beta", {"value": 2}, "2024-01-01T00:01:00Z", "tester")

            exit_code, lines = self._run_cli(["ledger", "tail"], cfg)

            self.assertEqual(exit_code, 0)
            self.assertGreaterEqual(len(lines), 3)
            summary = json.loads(lines[0])
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["count"], 2)
            events = [json.loads(line) for line in lines[1:]]
            self.assertEqual(events, [first, second])

    def test_ledger_verify_checks_chain(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_filename="events.jsonl")
            append_event(cfg, "alpha", {"value": 1}, "2024-01-01T00:00:00Z", "tester")
            append_event(cfg, "beta", {"value": 2}, "2024-01-01T00:01:00Z", "tester")

            exit_code, lines = self._run_cli(["ledger", "verify"], cfg)

            self.assertEqual(exit_code, 0)
            self.assertGreaterEqual(len(lines), 1)
            summary = json.loads(lines[0])
            self.assertTrue(summary["ok"])
            self.assertTrue(summary["valid"])
            self.assertEqual(summary["count"], 2)


if __name__ == "__main__":
    unittest.main()
