import unittest

from adaad6.config import AdaadConfig, load_config


class ConfigTest(unittest.TestCase):
    def test_ledger_file_env_aliases(self) -> None:
        cfg = load_config({"ADAAD6_LEDGER_FILENAME": "legacy.jsonl"})
        self.assertEqual(cfg.ledger_file, "legacy.jsonl")

        cfg = load_config(
            {"ADAAD6_LEDGER_FILE": "preferred.jsonl", "ADAAD6_LEDGER_FILENAME": "legacy.jsonl"}
        )
        self.assertEqual(cfg.ledger_file, "preferred.jsonl")

    def test_ledger_schema_version_falls_back_to_log_version(self) -> None:
        cfg = load_config({"ADAAD6_LOG_SCHEMA_VERSION": "7"})
        self.assertEqual(cfg.ledger_schema_version, "7")

    def test_ledger_schema_version_env_override(self) -> None:
        cfg = load_config({"ADAAD6_LEDGER_SCHEMA_VERSION": "9"})
        self.assertEqual(cfg.ledger_schema_version, "9")

    def test_ledger_validation_rejects_blank_paths_and_traversal(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_dir="   ").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_file="   ").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_file="../events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_file="/events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_file="..\\events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_file="C:\\events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_file="~/events.jsonl").validate()

    def test_ledger_validation_requires_schema_version_when_enabled(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_schema_version="").validate()


if __name__ == "__main__":
    unittest.main()
