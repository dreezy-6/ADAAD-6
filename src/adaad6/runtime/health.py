from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from adaad6.config import AdaadConfig


def _package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _required_entries() -> set[str]:
    return {
        "__init__.py",
        "__main__.py",
        "cli.py",
        "config.py",
        "runtime",
        "planning",
        "adapters",
        "assurance",
        "kernel",
        "provenance",
    }


def _allowed_dirs() -> set[str]:
    return {
        "runtime",
        "planning",
        "adapters",
        "assurance",
        "kernel",
        "provenance",
    }


def _allowed_files() -> set[str]:
    return {
        "__init__.py",
        "config.py",
        "__main__.py",
        "cli.py",
        "py.typed",
        "version.py",
        "_version.py",
    }


def _ignored_entries() -> set[str]:
    return {"__pycache__", ".DS_Store"}


def _is_allowed_file(name: str) -> bool:
    return name in _allowed_files()


def _tree_law_status() -> tuple[bool, str | None]:
    root = _package_root()
    required = _required_entries()
    allowed_dirs = _allowed_dirs()
    ignored = _ignored_entries()
    missing = sorted(entry for entry in required if not (root / entry).exists())
    if missing:
        return False, f"Missing required entries in package root: {', '.join(missing)}"

    extras: list[str] = []
    for item in root.iterdir():
        name = item.name
        if name in ignored or name.startswith(".") or name.endswith(".pyc"):
            continue
        if item.is_dir():
            if name not in allowed_dirs:
                extras.append(name)
        elif item.is_file():
            if not _is_allowed_file(name):
                extras.append(name)
        else:
            extras.append(name)

    if extras:
        return False, f"Unexpected entries in package root: {', '.join(sorted(extras))}"
    return True, None


def _can_write_to_dir(directory: Path) -> tuple[bool, str | None]:
    try:
        fd, path_str = tempfile.mkstemp(dir=directory, prefix=".__adaad_health__")
        os.close(fd)
        Path(path_str).unlink(missing_ok=True)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _can_create_under(parent: Path) -> tuple[bool, str | None]:
    try:
        with tempfile.TemporaryDirectory(dir=parent):
            pass
        return True, None
    except Exception as exc:
        return False, str(exc)


def _ledger_dirs_status(cfg: AdaadConfig) -> tuple[bool, str | None]:
    if not cfg.ledger_enabled:
        return True, None

    home = Path(getattr(cfg, "home", ".")).expanduser().resolve()
    ledger_dir = Path(cfg.ledger_dir)
    if not ledger_dir.is_absolute():
        ledger_dir = home / ledger_dir
    try:
        ledger_dir = ledger_dir.resolve(strict=False)
    except TypeError:
        ledger_dir = Path(os.path.abspath(str(ledger_dir)))
    ledger_file_path = ledger_dir / cfg.ledger_filename
    ledger_file_parent = ledger_file_path.parent

    if ledger_dir.exists():
        if not ledger_dir.is_dir():
            return False, "Ledger directory path exists and is not a directory"
        writable, error = _can_write_to_dir(ledger_dir)
        if not writable:
            return False, f"Ledger directory is not writable: {error}"
    else:
        dir_ancestor = ledger_dir
        while not dir_ancestor.exists() and dir_ancestor != dir_ancestor.parent:
            dir_ancestor = dir_ancestor.parent

        if dir_ancestor.exists() and not dir_ancestor.is_dir():
            return False, "Ledger directory ancestry contains a non-directory"

        base_parent = dir_ancestor if dir_ancestor != Path() else Path(".")
        creatable, error = _can_create_under(base_parent)
        if not creatable:
            return False, f"Ledger directory cannot be created: {error}"

    file_parent_ancestor = ledger_file_parent
    while not file_parent_ancestor.exists() and file_parent_ancestor != file_parent_ancestor.parent:
        file_parent_ancestor = file_parent_ancestor.parent

    if file_parent_ancestor.exists() and not file_parent_ancestor.is_dir():
        return False, "Ledger file parent ancestry contains a non-directory"

    probe = file_parent_ancestor
    try:
        remaining_parts = ledger_file_parent.relative_to(file_parent_ancestor).parts
    except ValueError:
        remaining_parts = ()

    for part in remaining_parts:
        probe = probe / part
        if probe.exists() and not probe.is_dir():
            return False, "Ledger file parent exists and is not a directory"

    if remaining_parts:
        try:
            with tempfile.TemporaryDirectory(dir=file_parent_ancestor if file_parent_ancestor != Path() else Path(".")) as tmpdir:
                test_root = Path(tmpdir)
                (test_root / Path(*remaining_parts)).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Ledger file parent cannot be created: {exc}"

    if file_parent_ancestor.exists():
        writable, error = _can_write_to_dir(file_parent_ancestor)
        if not writable:
            return False, f"Ledger file parent is not writable: {error}"
    else:
        base_parent = file_parent_ancestor
        if base_parent == Path():
            base_parent = Path(".")
        creatable, error = _can_create_under(base_parent)
        if not creatable:
            return False, f"Ledger file parent cannot be created: {error}"

    if ledger_file_path.exists() and ledger_file_path.is_dir():
        return False, "Ledger file path points to a directory"

    if ledger_file_path.exists():
        try:
            with ledger_file_path.open("a", encoding="utf-8"):
                pass
        except Exception as exc:
            return False, f"Ledger file is not writable: {exc}"

    return True, None


def check_structure_details(cfg: AdaadConfig | None = None) -> dict[str, Any]:
    config = cfg or AdaadConfig()

    root = _package_root()
    tree_law_ok, tree_law_error = _tree_law_status()
    required = [root] + [root / entry for entry in _required_entries()]

    structure_ok = all(path.exists() for path in required) and tree_law_ok
    ledger_dirs_ok, ledger_error = _ledger_dirs_status(config)

    return {
        "structure": structure_ok,
        "ledger_dirs": ledger_dirs_ok,
        "ledger_dirs_error": ledger_error,
        "tree_law": tree_law_ok,
        "tree_law_error": tree_law_error,
    }


def check_structure(cfg: AdaadConfig | None = None) -> bool:
    details = check_structure_details(cfg=cfg)
    return bool(details["structure"] and details["ledger_dirs"])


__all__ = ["check_structure", "check_structure_details"]
