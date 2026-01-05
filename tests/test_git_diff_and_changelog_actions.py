from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.planning.actions import format_changelog, git_diff_snapshot


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, env=_git_env(), capture_output=True, text=True)


class GitDiffSnapshotActionTest(unittest.TestCase):
    def test_git_diff_snapshot_reports_changes(self) -> None:
        with TemporaryDirectory() as td:
            repo = Path(td)
            _git(repo, "init")
            path = repo / "README.md"
            path.write_text("alpha\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "init")
            path.write_text("alpha\nbeta\n", encoding="utf-8")

            cfg = AdaadConfig(home=td)
            validated = git_diff_snapshot.validate({"root": repo, "base_ref": "HEAD"}, cfg)
            result = git_diff_snapshot.run(validated)
            checked = git_diff_snapshot.postcheck(result, cfg)

            self.assertEqual("HEAD", checked["base_ref"])
            self.assertEqual("WORKTREE", checked["target_ref"])
            self.assertTrue(any(change["path"] == "README.md" for change in checked["changes"]))
            self.assertIn("+beta", checked["patch"])

    def test_git_diff_snapshot_truncates_patch_when_requested(self) -> None:
        with TemporaryDirectory() as td:
            repo = Path(td)
            _git(repo, "init")
            path = repo / "file.txt"
            path.write_text("a\n", encoding="utf-8")
            _git(repo, "add", "file.txt")
            _git(repo, "commit", "-m", "init")
            path.write_text("a\n" + ("b" * 2000) + "\n", encoding="utf-8")

            cfg = AdaadConfig(home=td)
            validated = git_diff_snapshot.validate({"root": repo, "max_patch_bytes": 100}, cfg)
            result = git_diff_snapshot.run(validated)
            checked = git_diff_snapshot.postcheck(result, cfg)

            self.assertTrue(checked["patch_truncated"])
            self.assertLessEqual(len(checked["patch"].encode("utf-8")), 100)

    def test_git_diff_snapshot_allows_relative_root_from_cwd(self) -> None:
        with TemporaryDirectory() as td_repo, TemporaryDirectory() as td_home:
            repo = Path(td_repo)
            _git(repo, "init")
            cfg = AdaadConfig(home=td_repo)
            cwd = Path.cwd()
            try:
                os.chdir(repo)
                validated = git_diff_snapshot.validate({"root": "."}, cfg)
            finally:
                os.chdir(cwd)
            self.assertEqual(repo.resolve(), validated["root"])

    def test_git_diff_snapshot_rejects_symlink_root(self) -> None:
        with TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            link = Path(td) / "link"
            link.symlink_to(repo)
            cfg = AdaadConfig(home=td)
            with self.assertRaisesRegex(ValueError, "symlink"):
                git_diff_snapshot.validate({"root": link}, cfg)

    def test_git_diff_snapshot_rejects_root_outside_home(self) -> None:
        with TemporaryDirectory() as td_repo, TemporaryDirectory() as td_home:
            repo = Path(td_repo)
            repo.mkdir(parents=True, exist_ok=True)
            cfg = AdaadConfig(home=td_home)
            with self.assertRaisesRegex(ValueError, "cfg.home"):
                git_diff_snapshot.validate({"root": repo}, cfg)


class FormatChangelogActionTest(unittest.TestCase):
    def test_format_changelog_compiles_sections(self) -> None:
        cfg = AdaadConfig()
        validated = format_changelog.validate(
            {
                "title": "Release notes",
                "base_ref": "abc123",
                "target_ref": "worktree",
                "changes": [{"status": "M", "path": "README.md"}],
                "stats": [{"path": "README.md", "additions": 3, "deletions": 1}],
                "patch": "--- a/README.md\n+++ b/README.md\n+beta\n",
            },
            cfg,
        )
        result = format_changelog.run(validated)
        checked = format_changelog.postcheck(result, cfg)
        changelog = checked["changelog"]

        self.assertIn("# Release notes", changelog)
        self.assertIn("Base: abc123", changelog)
        self.assertIn("Target: worktree", changelog)
        self.assertIn("M README.md", changelog)
        self.assertIn("+3", changelog)
        self.assertIn("-1", changelog)
        self.assertIn("```diff", changelog)

    def test_format_changelog_rejects_empty_status_or_path(self) -> None:
        cfg = AdaadConfig()
        with self.assertRaisesRegex(ValueError, "status must be non-empty"):
            format_changelog.validate({"changes": [{"status": "", "path": "README.md"}]}, cfg)
        with self.assertRaisesRegex(ValueError, "path must be non-empty"):
            format_changelog.validate({"changes": [{"status": "M", "path": ""}]}, cfg)

    def test_format_changelog_truncates_patch(self) -> None:
        cfg = AdaadConfig()
        validated = format_changelog.validate(
            {
                "patch": "a" * 50,
                "max_patch_bytes": 10,
            },
            cfg,
        )
        result = format_changelog.run(validated)
        changelog = result["changelog"]
        self.assertIn("truncated to 10 bytes", changelog)

    def test_format_changelog_rejects_empty_stat_path(self) -> None:
        cfg = AdaadConfig()
        with self.assertRaisesRegex(ValueError, "path must be non-empty"):
            format_changelog.validate({"stats": [{"path": ""}]}, cfg)

    def test_format_changelog_rejects_negative_stats(self) -> None:
        cfg = AdaadConfig()
        with self.assertRaisesRegex(ValueError, "additions must be non-negative"):
            format_changelog.validate({"stats": [{"path": "file", "additions": -1}]}, cfg)
        with self.assertRaisesRegex(ValueError, "deletions must be non-negative"):
            format_changelog.validate({"stats": [{"path": "file", "deletions": -2}]}, cfg)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
