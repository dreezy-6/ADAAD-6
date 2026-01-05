from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from adaad6.config import AdaadConfig


def _ensure_no_symlink_components(base: Path, resolved: Path) -> None:
    """Ensure no path components between base and resolved are symlinks."""

    try:
        rel = resolved.relative_to(base)
    except Exception as exc:
        raise ValueError("root must resolve under cfg.home") from exc
    probe = base
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("root must not traverse symlinks")


def _resolve_root(raw_root: Any, *, cfg: AdaadConfig) -> Path:
    root_param = Path(str(raw_root)).expanduser()
    if root_param.exists() and root_param.is_symlink():
        raise ValueError("root must not be a symlink")
    base = root_param if root_param.is_absolute() else Path.cwd() / root_param
    resolved = base.resolve()
    if not resolved.exists():
        raise ValueError("root must exist")
    if not resolved.is_dir():
        raise ValueError("root must be a directory")

    home = Path(cfg.home).expanduser().resolve()
    try:
        resolved.relative_to(home)
    except Exception as exc:
        raise ValueError("root must resolve under cfg.home") from exc

    _ensure_no_symlink_components(home, resolved)

    return resolved


def _coerce_ref(raw: Any, field: str, *, default: str | None = None) -> str:
    value = raw if raw is not None else default
    if value is None:
        raise ValueError(f"{field} is required")
    value_str = str(value).strip()
    if not value_str:
        raise ValueError(f"{field} cannot be empty")
    return value_str


def _coerce_max_bytes(raw: Any) -> int:
    if raw is None:
        return 65_536
    try:
        value = int(raw)
    except Exception as exc:
        raise ValueError("max_patch_bytes must be an integer") from exc
    if value <= 0:
        raise ValueError("max_patch_bytes must be positive")
    return value


def _git(cwd: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git command failed: git is not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or repr(exc)
        raise RuntimeError(f"git command failed: {message}") from exc
    return completed.stdout


def _diff_args(base_ref: str, target_ref: str, *extra: str) -> list[str]:
    args = ["diff", "--no-color", "--no-ext-diff", *extra, base_ref]
    if target_ref.upper() != "WORKTREE":
        args.append(target_ref)
    return args


def _parse_name_status(payload: str) -> list[dict[str, str | None]]:
    changes: list[dict[str, str | None]] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0].strip() if parts else ""
        if len(parts) == 2:
            changes.append({"status": status, "path": parts[1].strip(), "from_path": None})
        elif len(parts) >= 3:
            changes.append({"status": status, "path": parts[2].strip(), "from_path": parts[1].strip()})
        else:
            changes.append({"status": status, "path": "", "from_path": None})
    return changes


def _parse_numstat(payload: str) -> list[dict[str, int | None | str]]:
    stats: list[dict[str, int | None | str]] = []
    for line in payload.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add_raw, del_raw, path = parts
        additions = None if add_raw == "-" else int(add_raw)
        deletions = None if del_raw == "-" else int(del_raw)
        stats.append({"path": path.strip(), "additions": additions, "deletions": deletions})
    return stats


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    root = _resolve_root(params.get("root", "."), cfg=cfg)
    base_ref = _coerce_ref(params.get("base_ref", "HEAD"), "base_ref")
    target_ref = _coerce_ref(params.get("target_ref", "WORKTREE"), "target_ref", default="WORKTREE")
    max_patch_bytes = _coerce_max_bytes(params.get("max_patch_bytes"))
    target_ref_normalized = "WORKTREE" if target_ref.upper() == "WORKTREE" else target_ref
    return {"root": root, "base_ref": base_ref, "target_ref": target_ref_normalized, "max_patch_bytes": max_patch_bytes}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    root: Path = validated["root"]
    base_ref: str = validated["base_ref"]
    target_ref: str = validated["target_ref"]
    max_patch_bytes: int = validated["max_patch_bytes"]

    _git(root, "rev-parse", "--is-inside-work-tree")
    toplevel = Path(_git(root, "rev-parse", "--show-toplevel").strip()).resolve()

    name_status = _git(root, *_diff_args(base_ref, target_ref, "--name-status"))
    numstat = _git(root, *_diff_args(base_ref, target_ref, "--numstat"))
    patch = _git(root, *_diff_args(base_ref, target_ref))
    encoded_patch = patch.encode("utf-8")
    truncated = False
    if len(encoded_patch) > max_patch_bytes:
        truncated = True
        encoded_patch = encoded_patch[:max_patch_bytes]
    patch_text = encoded_patch.decode("utf-8", errors="ignore")

    return {
        "root": str(root),
        "toplevel": str(toplevel),
        "base_ref": base_ref,
        "target_ref": target_ref,
        "max_patch_bytes": max_patch_bytes,
        "changes": _parse_name_status(name_status),
        "stats": _parse_numstat(numstat),
        "patch": patch_text,
        "patch_truncated": truncated,
    }


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("git_diff_snapshot result must be a dict")
    for key in ("base_ref", "target_ref", "patch", "changes", "stats", "root", "toplevel", "max_patch_bytes", "patch_truncated"):
        if key not in result:
            raise ValueError(f"git_diff_snapshot result missing {key}")
    if not isinstance(result["base_ref"], str):
        raise ValueError("git_diff_snapshot base_ref must be a string")
    if not isinstance(result["target_ref"], str):
        raise ValueError("git_diff_snapshot target_ref must be a string")
    if not isinstance(result["root"], str) or not isinstance(result["toplevel"], str):
        raise ValueError("git_diff_snapshot root and toplevel must be strings")
    if not isinstance(result["max_patch_bytes"], int) or result["max_patch_bytes"] <= 0:
        raise ValueError("git_diff_snapshot max_patch_bytes must be a positive integer")
    if not isinstance(result["patch_truncated"], bool):
        raise ValueError("git_diff_snapshot patch_truncated must be a boolean")
    if not isinstance(result["patch"], str):
        raise ValueError("git_diff_snapshot patch must be a string")
    if not isinstance(result["changes"], list):
        raise ValueError("git_diff_snapshot changes must be a list")
    if not isinstance(result["stats"], list):
        raise ValueError("git_diff_snapshot stats must be a list")
    for change in result["changes"]:
        if not isinstance(change, dict):
            raise ValueError("git_diff_snapshot change entries must be dicts")
        if "status" not in change or "path" not in change:
            raise ValueError("git_diff_snapshot change entries missing status or path")
    for stat in result["stats"]:
        if not isinstance(stat, dict):
            raise ValueError("git_diff_snapshot stat entries must be dicts")
        if "path" not in stat:
            raise ValueError("git_diff_snapshot stat entries missing path")
    return result


__all__ = ["validate", "run", "postcheck"]
