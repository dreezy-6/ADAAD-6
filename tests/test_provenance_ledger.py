import json
import os
import tempfile
import unittest

from adaad6.config import AdaadConfig
from adaad6.provenance import (
    append_event,
    ensure_ledger,
    ledger_path,
    read_events,
    verify_chain,
)


class ProvenanceLedgerTest(unittest.TestCase):
    def test_ensure_ledger_disabled_raises(self) -> None:
        cfg = AdaadConfig(ledger_enabled=False)
        with self.assertRaises(RuntimeError):
            ensure_ledger(cfg)

    def test_append_and_read_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(
                ledger_enabled=True,
                ledger_dir=tmpdir,
                ledger_file="events.jsonl",
                ledger_schema_version="2",
            )
            ensure_ledger(cfg)

            first = append_event(cfg, "test", {"one": 1}, "2024-01-01T00:00:00Z", "tester")
            second = append_event(cfg, "test", {"two": 2}, "2024-01-01T00:01:00Z", "tester")

            path = ledger_path(cfg)
            self.assertTrue(path.exists())

            events = read_events(cfg)
            self.assertEqual(events, [first, second])
            self.assertIn(events[0].get("prev_hash"), (None, ""))
            self.assertEqual(events[1]["prev_hash"], events[0]["hash"])
            self.assertTrue(verify_chain(events))

            self.assertIn("event_id", events[0])
            self.assertIn("event_id", events[1])
            self.assertEqual(events[0]["schema_version"], cfg.ledger_schema_version)
            self.assertEqual(events[1]["schema_version"], cfg.ledger_schema_version)

    def test_verify_chain_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_file="events.jsonl")

            append_event(cfg, "test", {"value": 1}, "2024-01-01T00:00:00Z", "tester")
            append_event(cfg, "test", {"value": 2}, "2024-01-01T00:01:00Z", "tester")

            path = ledger_path(cfg)
            raw_lines = path.read_text(encoding="utf-8").splitlines()

            tampered = []
            for line in raw_lines:
                payload = json.loads(line)
                if payload["payload"].get("value") == 2:
                    payload["payload"]["value"] = 999
                tampered.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))

            path.write_text(os.linesep.join(tampered) + os.linesep, encoding="utf-8")

            events = read_events(cfg)
            self.assertFalse(verify_chain(events))


if __name__ == "__main__":
    unittest.main()
