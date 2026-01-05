import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.assurance.logging import append_jsonl_log_event, canonical_json, log_path
from adaad6.config import AdaadConfig


class AssuranceLoggingTest(unittest.TestCase):
    def test_append_jsonl_log_event_writes_canonical_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(home=tmpdir, log_path="logs/events.jsonl", log_schema_version="2")
            ts = "2024-01-01T00:00:00Z"
            event = append_jsonl_log_event(
                cfg=cfg,
                action="boot",
                outcome="ok",
                details={"b": 2, "a": 1},
                ts=ts,
            )

            target = Path(log_path(cfg))
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8").strip()
            self.assertEqual(content, canonical_json(event))

            loaded = json.loads(content)
            self.assertEqual(loaded["schema_version"], "2")
            self.assertEqual(loaded["ts"], ts)
            self.assertEqual(loaded["action"], "boot")
            self.assertEqual(loaded["outcome"], "ok")
            self.assertEqual(loaded["details"], {"a": 1, "b": 2})
            self.assertIn("checksum", loaded)

    def test_log_path_resolves_under_home_and_appends_lines(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(home=tmpdir, log_path="nested/logs/events.jsonl")
            path = log_path(cfg)
            self.assertTrue(str(path).startswith(str(Path(tmpdir))))

            append_jsonl_log_event(cfg=cfg, action="plan", outcome="ok", details={"x": 1}, ts="2024-01-01T00:00:00Z")
            append_jsonl_log_event(cfg=cfg, action="plan", outcome="ok", details={"x": 2}, ts="2024-01-01T00:00:01Z")

            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            for line in lines:
                loaded = json.loads(line)
                self.assertEqual(loaded["schema_version"], cfg.log_schema_version)
                self.assertIn("checksum", loaded)


if __name__ == "__main__":
    unittest.main()
