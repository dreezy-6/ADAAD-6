from __future__ import annotations

from pathlib import Path
from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    root_param = params.get("root", ".")
    root = Path(str(root_param)).expanduser()
    base = Path(cfg.home).expanduser().resolve()
    resolved = (base / root).resolve()
    try:
        resolved.relative_to(base)
    except Exception as exc:
        raise ValueError("root must resolve under cfg.home") from exc
    rel = resolved.relative_to(base)
    probe = base
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("root must not traverse symlinks")
    depth = int(params.get("max_depth", 3))
    if depth < 0:
        raise ValueError("max_depth must be non-negative")
    return {"root": resolved, "max_depth": depth}


def run(validated: dict[str, Any]) -> list[dict[str, str]]:
    root: Path = validated["root"]
    max_depth: int = validated["max_depth"]
    results: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        # max_depth counts path segments beneath root; 0 means only immediate children.
        if len(rel.parts) > max_depth + 1:
            continue
        entry_type = "dir" if path.is_dir() else "file"
        results.append({"path": str(rel), "type": entry_type})
    return results


def postcheck(result: list[dict[str, str]], cfg: AdaadConfig) -> list[dict[str, str]]:
    if not isinstance(result, list):
        raise ValueError("scan_repo_tree result must be a list")
    return result
