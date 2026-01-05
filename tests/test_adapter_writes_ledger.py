import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.adapters.base import AdapterResult, BaseAdapter
from adaad6.assurance.logging import compute_checksum
from adaad6.config import AdaadConfig
from adaad6.provenance.ledger import read_events


class EchoAdapter(BaseAdapter):
    name = "echo"

    def _execute(self, intent: str, inputs: dict, cfg: AdaadConfig) -> dict:
        return {"echo": inputs}


class AdapterLedgerWriteTest(unittest.TestCase):
    def test_adapter_appends_adapter_call_event(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / ".adaad" / "ledger"
            base.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(base), ledger_filename="events.jsonl", home=tmpdir)
            adapter = EchoAdapter()
            ts = "2024-05-05T05:05:05Z"
            intent = "echo"
            inputs = {"message": "hello"}

            result: AdapterResult = adapter.run(
                intent=intent, inputs=inputs, actor="tester", cfg=cfg, now_fn=lambda: ts
            )

            self.assertTrue(result.log["ledger_appended"])
            self.assertIsNone(result.log["ledger_error"])
            self.assertIsNotNone(result.log["ledger_event_hash"])

            events = read_events(cfg)
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event["type"], "adapter_call")
            self.assertEqual(event["ts"], ts)
            self.assertEqual(event["actor"], "tester")

            expected_payload = {k: v for k, v in result.log.items() if not k.startswith("ledger_")}
            self.assertEqual(event["payload"], expected_payload)
            checksum_payload = {k: v for k, v in expected_payload.items() if k != "checksum"}
            self.assertEqual(expected_payload["checksum"], compute_checksum(checksum_payload))
            self.assertEqual(result.log["ledger_event_hash"], event["hash"])


if __name__ == "__main__":
    unittest.main()
