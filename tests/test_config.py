import unittest

from adaad6.config import AdaadConfig, load_config


class ConfigTest(unittest.TestCase):
    def test_ledger_file_env_aliases(self) -> None:
        cfg = load_config({"ADAAD6_LEDGER_FILENAME": "legacy.jsonl"})
        self.assertEqual(cfg.ledger_filename, "legacy.jsonl")

        cfg = load_config(
            {"ADAAD6_LEDGER_FILE": "preferred.jsonl", "ADAAD6_LEDGER_FILENAME": "legacy.jsonl"}
        )
        self.assertEqual(cfg.ledger_filename, "preferred.jsonl")

    def test_ledger_schema_version_falls_back_to_log_version(self) -> None:
        cfg = load_config({"ADAAD6_LOG_SCHEMA_VERSION": "7"})
        self.assertEqual(cfg.ledger_schema_version, "7")

    def test_ledger_schema_version_env_override(self) -> None:
        cfg = load_config({"ADAAD6_LEDGER_SCHEMA_VERSION": "9"})
        self.assertEqual(cfg.ledger_schema_version, "9")

    def test_ledger_file_attribute_alias(self) -> None:
        cfg = AdaadConfig(ledger_enabled=True, ledger_dir=".adaad/ledger", ledger_file="events.jsonl")
        self.assertEqual(cfg.ledger_file, "events.jsonl")
        self.assertEqual(cfg.ledger_filename, "events.jsonl")

    def test_legacy_does_not_override_explicit_filename(self) -> None:
        cfg = AdaadConfig(ledger_enabled=True, ledger_dir=".adaad/ledger", ledger_filename="new.jsonl", ledger_file="old.jsonl")
        self.assertEqual(cfg.ledger_filename, "new.jsonl")
        self.assertEqual(cfg.ledger_file, "new.jsonl")

    def test_ledger_validation_rejects_blank_paths_and_traversal(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_dir="   ").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_filename="   ").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_filename="../events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_filename="/events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_filename="..\\events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_filename="C:\\events.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_filename="~/events.jsonl").validate()

    def test_ledger_validation_requires_schema_version_when_enabled(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(ledger_enabled=True, ledger_schema_version="").validate()

    def test_log_path_env_override(self) -> None:
        cfg = load_config({"ADAAD6_LOG_PATH": "custom/logs.jsonl"})
        self.assertEqual(cfg.log_path, "custom/logs.jsonl")

    def test_log_path_required(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(log_path="   ").validate()

    def test_log_path_must_be_relative_and_sandboxed(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(log_path="/tmp/out.jsonl").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(home="/home/user", log_path="../evil").validate()

    def test_actions_dir_env_override(self) -> None:
        cfg = load_config({"ADAAD6_ACTIONS_DIR": "custom/actions"})
        self.assertEqual(cfg.actions_dir, "custom/actions")

    def test_actions_dir_env_fallback(self) -> None:
        cfg = load_config({"ACTIONS_DIR": "fallback/actions"})
        self.assertEqual(cfg.actions_dir, "fallback/actions")

    def test_actions_dir_required_and_sandboxed(self) -> None:
        with self.assertRaises(ValueError):
            AdaadConfig(actions_dir="   ").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(actions_dir="/tmp/actions").validate()
        with self.assertRaises(ValueError):
            AdaadConfig(home="/home/user", actions_dir="../evil").validate()


if __name__ == "__main__":
    unittest.main()
