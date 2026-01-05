from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.planning.registry import discover_actions


def _write_action(path: Path, *, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


def _make_cfg(home: Path, actions_dir: str = "actions") -> AdaadConfig:
    return AdaadConfig(home=str(home), actions_dir=actions_dir)


class PlanningRegistryTest(unittest.TestCase):
    def test_discover_actions_sorted_and_valid(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            actions_dir = root / "actions"
            actions_dir.mkdir()
            _write_action(
                actions_dir / "b_action.py",
                body="""
                def validate(params, cfg):
                    return params

                def run(validated):
                    return validated

                def postcheck(result, cfg):
                    return result
                """,
            )
            _write_action(
                actions_dir / "a_action.py",
                body="""
                def validate(params, cfg):
                    return params

                def run(validated):
                    return validated

                def postcheck(result, cfg):
                    return result
                """,
            )

            cfg = _make_cfg(root)
            actions = discover_actions(cfg=cfg)

            self.assertEqual(list(actions.keys()), ["a_action", "b_action"])

    def test_discover_actions_missing_required_function(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            actions_dir = root / "actions"
            actions_dir.mkdir()
            _write_action(
                actions_dir / "incomplete.py",
                body="""
                def validate(params, cfg):
                    return params

                def run(validated):
                    return validated
                """,
            )

            cfg = _make_cfg(root)
            with self.assertRaisesRegex(ValueError, "missing required functions"):
                discover_actions(cfg=cfg)

    def test_discover_actions_rejects_non_callable(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            actions_dir = root / "actions"
            actions_dir.mkdir()
            _write_action(
                actions_dir / "bad.py",
                body="""
                validate = 123

                def run(validated):
                    return validated

                def postcheck(result, cfg):
                    return result
                """,
            )

            cfg = _make_cfg(root)
            with self.assertRaisesRegex(TypeError, "must be callable"):
                discover_actions(cfg=cfg)

    def test_discover_actions_rejects_duplicate_names(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            actions_dir = root / "actions"
            actions_dir.mkdir()
            _write_action(
                actions_dir / "Alpha.py",
                body="""
                def validate(params, cfg):
                    return params

                def run(validated):
                    return validated

                def postcheck(result, cfg):
                    return result
                """,
            )
            _write_action(
                actions_dir / "alpha.py",
                body="""
                def validate(params, cfg):
                    return params

                def run(validated):
                    return validated

                def postcheck(result, cfg):
                    return result
                """,
            )

            cfg = _make_cfg(root)
            with self.assertRaisesRegex(ValueError, "Duplicate action name"):
                discover_actions(cfg=cfg)

    def test_discover_actions_rejects_bad_signature(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            actions_dir = root / "actions"
            actions_dir.mkdir()
            _write_action(
                actions_dir / "bad_sig.py",
                body="""
                def validate(params):
                    return params

                def run(validated):
                    return validated

                def postcheck(result, cfg):
                    return result
                """,
            )

            cfg = _make_cfg(root)
            with self.assertRaisesRegex(TypeError, "validate must accept at least"):
                discover_actions(cfg=cfg)


if __name__ == "__main__":
    unittest.main()
