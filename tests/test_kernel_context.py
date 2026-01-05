import os
import json
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.kernel.context import ArtifactRegistry, ConfigSnapshot, KernelContext, WorkspacePaths
from adaad6.kernel.hashing import hash_object


class KernelContextTest(unittest.TestCase):
    def test_workspace_paths_resolve_under_home(self) -> None:
        with TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            cfg = AdaadConfig(
                home=str(home),
                ledger_enabled=True,
                ledger_dir=".adaad/ledger",
                ledger_filename="events.jsonl",
            )
            workspace = WorkspacePaths.from_config(cfg)

        self.assertEqual(workspace.home, str(home.resolve()))
        self.assertTrue(workspace.actions_dir.startswith(workspace.home))
        self.assertTrue(workspace.log_path.startswith(workspace.home))
        self.assertTrue(workspace.ledger_path.startswith(workspace.home))

    def test_workspace_paths_reject_outside_home(self) -> None:
        with TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            outside = str(home.parent / "outside.log")
            cfg = AdaadConfig(home=str(home), log_path=outside)
            with self.assertRaises(ValueError):
                WorkspacePaths.from_config(cfg)

    def test_workspace_paths_reject_symlink_traversal(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("os.symlink not available on this platform")

        with TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            outside = home.parent / "outside_target"
            outside.mkdir(exist_ok=True)

            link = home / ".adaad"
            try:
                os.symlink(str(outside), str(link), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation not permitted")

            cfg = AdaadConfig(
                home=str(home),
                ledger_enabled=True,
                ledger_dir=".adaad/ledger",
                ledger_filename="events.jsonl",
            )

            with self.assertRaises(ValueError):
                WorkspacePaths.from_config(cfg)

    def test_config_snapshot_hash_uses_hashing(self) -> None:
        cfg = AdaadConfig(version="9.9.9", home="/tmp")
        snapshot = ConfigSnapshot.from_config(cfg)
        self.assertEqual(snapshot.hash, hash_object(asdict(cfg)))

    def test_artifact_registry_is_immutable(self) -> None:
        registry = ArtifactRegistry()
        updated = registry.register("plan", "/tmp/plan.json")

        self.assertEqual({}, registry.to_dict())
        self.assertEqual({"plan": "/tmp/plan.json"}, updated.to_dict())
        with self.assertRaises(ValueError):
            updated.register("plan", "/tmp/plan.json")

    def test_kernel_context_serializes_for_ledger_logging(self) -> None:
        cfg = AdaadConfig()
        ctx = KernelContext.build(cfg, run_id="run-1").register_artifact("log", "/tmp/log.jsonl")

        serialized = ctx.to_dict()
        self.assertEqual(serialized["run_id"], "run-1")
        self.assertEqual(serialized["artifacts"], {"log": "/tmp/log.jsonl"})
        self.assertIsNone(serialized["workspace"]["ledger_path"])
        json.dumps(serialized)


if __name__ == "__main__":
    unittest.main()
