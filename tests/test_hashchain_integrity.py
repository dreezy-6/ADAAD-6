import copy
import unittest
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.provenance import append_event, read_events, verify_chain


class HashchainIntegrityTest(unittest.TestCase):
    def test_verify_chain_detects_tampering(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_filename="events.jsonl")
            append_event(cfg, "alpha", {"value": 1}, "2024-01-01T00:00:00Z", "tester")
            append_event(cfg, "beta", {"value": 2}, "2024-01-01T00:01:00Z", "tester")

            events = read_events(cfg)
            self.assertTrue(verify_chain(events))
            tampered = copy.deepcopy(events)
            tampered[1]["payload"]["value"] = 999

            self.assertFalse(verify_chain(tampered))

    def test_verify_chain_detects_breaks(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir, ledger_filename="events.jsonl")
            append_event(cfg, "alpha", {"value": 1}, "2024-01-01T00:00:00Z", "tester")
            append_event(cfg, "beta", {"value": 2}, "2024-01-01T00:01:00Z", "tester")

            events = read_events(cfg)
            self.assertTrue(verify_chain(events))
            broken = [events[1], events[0]]

            self.assertFalse(verify_chain(broken))


if __name__ == "__main__":
    unittest.main()
