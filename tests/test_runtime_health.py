import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adaad6.config import AdaadConfig
from adaad6.runtime.health import check_structure, check_structure_details


class RuntimeHealthTest(unittest.TestCase):
    def test_ledger_dirs_ok_when_disabled(self) -> None:
        result = check_structure_details(cfg=AdaadConfig(ledger_enabled=False))

        self.assertTrue(result["ledger_dirs"])
        self.assertTrue(result["tree_law"])
        self.assertTrue(check_structure(cfg=AdaadConfig(ledger_enabled=False)))

    def test_ledger_dirs_missing_but_creatable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger"
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir))

            result = check_structure_details(cfg=cfg)

            self.assertTrue(result["ledger_dirs"])
            self.assertIsNone(result["ledger_dirs_error"])
            self.assertTrue(result["tree_law"])
            self.assertFalse(ledger_dir.exists())

    def test_ledger_dirs_fail_when_path_is_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger_file"
            ledger_dir.write_text("not a directory", encoding="utf-8")
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir))

            result = check_structure_details(cfg=cfg)

            self.assertFalse(result["ledger_dirs"])
            self.assertIsNotNone(result["ledger_dirs_error"])
            self.assertTrue(result["tree_law"])

    def test_ledger_file_path_points_to_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            ledger_file_dir = ledger_dir / "events.jsonl"
            ledger_file_dir.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir), ledger_filename="events.jsonl")

            result = check_structure_details(cfg=cfg)

            self.assertFalse(result["ledger_dirs"])
            self.assertIsNotNone(result["ledger_dirs_error"])
            self.assertTrue(result["tree_law"])

    def test_ledger_file_parent_needs_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger"
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir), ledger_filename="nested/events.jsonl")

            result = check_structure_details(cfg=cfg)

            self.assertTrue(result["ledger_dirs"])
            self.assertIsNone(result["ledger_dirs_error"])
            self.assertTrue(result["tree_law"])

    def test_ledger_file_parent_exists_as_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            bad_parent = ledger_dir / "nested"
            bad_parent.write_text("not a dir", encoding="utf-8")
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir), ledger_filename="nested/events.jsonl")

            result = check_structure_details(cfg=cfg)

            self.assertFalse(result["ledger_dirs"])
            self.assertIsNotNone(result["ledger_dirs_error"])
            self.assertTrue(result["tree_law"])

    def test_tree_law_detects_unexpected_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_root = Path(tmpdir) / "adaad6"
            pkg_root.mkdir()

            required_dirs = ["runtime", "planning", "adapters", "assurance", "kernel", "provenance"]
            for d in required_dirs:
                (pkg_root / d).mkdir(parents=True, exist_ok=True)

            required_files = ["__init__.py", "config.py", "cli.py", "__main__.py"]
            for f in required_files:
                (pkg_root / f).write_text("", encoding="utf-8")

            rogue = pkg_root / "rogue_node"
            rogue.mkdir(exist_ok=True)

            with patch("adaad6.runtime.health._package_root", return_value=pkg_root):
                result = check_structure_details(cfg=AdaadConfig(ledger_enabled=False))
                self.assertFalse(result["tree_law"])
                self.assertIn("rogue_node", result["tree_law_error"] or "")

    def test_tree_law_detects_rogue_root_py_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_root = Path(tmpdir) / "adaad6"
            pkg_root.mkdir()

            required_dirs = ["runtime", "planning", "adapters", "assurance", "kernel", "provenance"]
            for d in required_dirs:
                (pkg_root / d).mkdir(parents=True, exist_ok=True)

            required_files = ["__init__.py", "config.py", "cli.py", "__main__.py"]
            for f in required_files:
                (pkg_root / f).write_text("", encoding="utf-8")

            rogue = pkg_root / "backdoor.py"
            rogue.write_text("# rogue", encoding="utf-8")

            with patch("adaad6.runtime.health._package_root", return_value=pkg_root):
                result = check_structure_details(cfg=AdaadConfig(ledger_enabled=False))
                self.assertFalse(result["tree_law"])
                self.assertIn("backdoor.py", result["tree_law_error"] or "")

    def test_tree_law_detects_private_root_py_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_root = Path(tmpdir) / "adaad6"
            pkg_root.mkdir()

            required_dirs = ["runtime", "planning", "adapters", "assurance", "kernel", "provenance"]
            for d in required_dirs:
                (pkg_root / d).mkdir(parents=True, exist_ok=True)

            required_files = ["__init__.py", "config.py", "cli.py", "__main__.py"]
            for f in required_files:
                (pkg_root / f).write_text("", encoding="utf-8")

            rogue = pkg_root / "_backdoor.py"
            rogue.write_text("# rogue", encoding="utf-8")

            with patch("adaad6.runtime.health._package_root", return_value=pkg_root):
                result = check_structure_details(cfg=AdaadConfig(ledger_enabled=False))
                self.assertFalse(result["tree_law"])
                self.assertIn("_backdoor.py", result["tree_law_error"] or "")


if __name__ == "__main__":
    unittest.main()
