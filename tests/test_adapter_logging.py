import unittest
from tempfile import TemporaryDirectory

from adaad6.adapters.base import AdapterResult, BaseAdapter, idempotency_key
from adaad6.config import AdaadConfig
from adaad6.provenance.ledger import read_events


class EchoAdapter(BaseAdapter):
    name = "echo"

    def _execute(self, intent: str, inputs: dict, cfg: AdaadConfig) -> dict:
        return {"echo": inputs}


class AdapterLoggingTest(unittest.TestCase):
    def test_logging_and_idempotency(self) -> None:
        cfg = AdaadConfig()
        adapter = EchoAdapter()
        now = lambda: "2024-01-01T00:00:00Z"
        intent = "echo"
        inputs = {"message": "hello"}

        result: AdapterResult = adapter.run(intent=intent, inputs=inputs, actor="tester", cfg=cfg, now_fn=now)
        repeat: AdapterResult = adapter.run(intent=intent, inputs=inputs, actor="tester", cfg=cfg, now_fn=now)

        for item in (result, repeat):
            self.assertTrue(item.ok)
            self.assertIn("schema_version", item.log)
            self.assertEqual(item.log["ts"], "2024-01-01T00:00:00Z")
            self.assertEqual(item.log["actor"], "tester")
            self.assertEqual(item.log["intent"], intent)
            self.assertEqual(item.log["inputs"], inputs)
            self.assertEqual(item.log["outputs"], {"echo": inputs})
            self.assertIn("checksum", item.log)

        self.assertEqual(result.log["checksum"], repeat.log["checksum"])
        key_first = idempotency_key(intent, inputs)
        key_second = idempotency_key(intent, inputs)
        self.assertEqual(key_first, key_second)


class AdapterLedgerTest(unittest.TestCase):
    def test_adapter_appends_to_ledger_when_enabled(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=tmpdir)
            adapter = EchoAdapter()
            now = lambda: "2024-01-01T00:00:00Z"
            intent = "echo"
            inputs = {"message": "hello"}

            result: AdapterResult = adapter.run(
                intent=intent, inputs=inputs, actor="tester", cfg=cfg, now_fn=now
            )

            self.assertTrue(result.log["ledger_appended"])
            self.assertIsNone(result.log["ledger_error"])
            self.assertIsNotNone(result.log["ledger_event_hash"])

            events = read_events(cfg)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["type"], "adapter_call")
            expected_payload = {k: v for k, v in result.log.items() if not k.startswith("ledger_")}
            self.assertEqual(events[0]["payload"], expected_payload)


if __name__ == "__main__":
    unittest.main()
