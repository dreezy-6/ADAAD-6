import unittest
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.provenance import append_event, ledger_path, read_events, verify_chain


class LedgerAppendOnlyTest(unittest.TestCase):
    def test_append_events_and_verify_chain(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_filename="events.jsonl")

            first = append_event(cfg, "alpha", {"value": 1}, "2024-01-01T00:00:00Z", "tester")
            second = append_event(cfg, "beta", {"value": 2}, "2024-01-01T00:01:00Z", "tester")

            ledger_file = ledger_path(cfg)
            lines = ledger_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

            events = read_events(cfg)
            self.assertEqual(events, [first, second])
            self.assertIn(events[0].get("prev_hash"), (None, ""))
            self.assertEqual(events[1]["prev_hash"], first["hash"])
            self.assertTrue(verify_chain(events))


if __name__ == "__main__":
    unittest.main()
