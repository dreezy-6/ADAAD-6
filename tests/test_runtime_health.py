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

    def test_ledger_feed_missing_is_ok_but_unreadable_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir) / "ledger"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(ledger_enabled=True, ledger_dir=str(ledger_dir), home=tmpdir)

            details = check_structure_details(cfg=cfg)

            self.assertTrue(details["ledger_dirs"])
            self.assertTrue(details["ledger_feed"])
            self.assertEqual(details["ledger_feed_path"], str(ledger_dir / cfg.ledger_filename))

            ledger_file = ledger_dir / cfg.ledger_filename
            ledger_file.write_text("", encoding="utf-8")

            from adaad6.runtime import health
            from adaad6.provenance.ledger import ledger_path as cfg_ledger_path

            original_probe = health._probe_feed
            expected_path = cfg_ledger_path(cfg).resolve(strict=False)

            def fake_probe(path: Path) -> tuple[bool, str | None]:
                if path.resolve(strict=False) == expected_path:
                    return False, "unreadable:nope"
                return original_probe(path)

            with patch("adaad6.runtime.health._probe_feed", side_effect=fake_probe):
                unreadable = check_structure_details(cfg=cfg)

            self.assertFalse(unreadable["ledger_feed"])
            self.assertIn("unreadable", unreadable["ledger_feed_error"] or "")

    def test_telemetry_exports_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(home=tmpdir, ledger_enabled=False, telemetry_exports=("telemetry/metrics.jsonl",))

            details = check_structure_details(cfg=cfg)

            self.assertFalse(details["telemetry_ok"])
            self.assertEqual(len(details["telemetry_exports"]), 1)
            self.assertFalse(details["telemetry_exports"][0]["ok"])

            telemetry_path = Path(tmpdir) / "telemetry" / "metrics.jsonl"
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            telemetry_path.write_text("{}", encoding="utf-8")

            recovered = check_structure_details(cfg=cfg)

            self.assertTrue(recovered["telemetry_ok"])
            self.assertTrue(recovered["telemetry_exports"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
