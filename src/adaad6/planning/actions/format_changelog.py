from __future__ import annotations

from typing import Any, Mapping

from adaad6.config import AdaadConfig


def _coerce_changes(raw: Any) -> list[dict[str, str | None]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("changes must be a list")
    changes: list[dict[str, str | None]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"changes[{i}] must be a mapping")
        status = str(item.get("status", "")).strip()
        path = str(item.get("path", "")).strip()
        from_path_raw = item.get("from_path")
        from_path = None if from_path_raw is None else str(from_path_raw).strip()
        if not status:
            raise ValueError(f"changes[{i}].status must be non-empty")
        if not path:
            raise ValueError(f"changes[{i}].path must be non-empty")
        if from_path_raw is not None and not from_path:
            raise ValueError(f"changes[{i}].from_path must be non-empty when provided")
        changes.append({"status": status, "path": path, "from_path": from_path or None})
    return changes


def _coerce_stats(raw: Any) -> list[dict[str, int | None | str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("stats must be a list")
    stats: list[dict[str, int | None | str]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"stats[{i}] must be a mapping")
        path = str(item.get("path", "")).strip()
        if not path:
            raise ValueError(f"stats[{i}].path must be non-empty")
        additions_raw = item.get("additions")
        deletions_raw = item.get("deletions")
        additions = None if additions_raw is None else int(additions_raw)
        deletions = None if deletions_raw is None else int(deletions_raw)
        if additions is not None and additions < 0:
            raise ValueError(f"stats[{i}].additions must be non-negative")
        if deletions is not None and deletions < 0:
            raise ValueError(f"stats[{i}].deletions must be non-negative")
        stats.append({"path": path, "additions": additions, "deletions": deletions})
    return stats


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    title = str(params.get("title", "Changelog")).strip() or "Changelog"
    base_ref = str(params.get("base_ref", "HEAD")).strip() or "HEAD"
    target_ref = str(params.get("target_ref", "WORKTREE")).strip() or "WORKTREE"
    changes = _coerce_changes(params.get("changes", []))
    stats = _coerce_stats(params.get("stats", []))
    patch = str(params.get("patch", "") or "")
    max_patch_bytes_raw = params.get("max_patch_bytes")
    max_patch_bytes = 65_536
    if max_patch_bytes_raw is not None:
        try:
            max_patch_bytes = int(max_patch_bytes_raw)
        except Exception as exc:
            raise ValueError("max_patch_bytes must be an integer") from exc
        if max_patch_bytes <= 0:
            raise ValueError("max_patch_bytes must be positive")
    return {
        "title": title,
        "base_ref": base_ref,
        "target_ref": target_ref,
        "changes": changes,
        "stats": stats,
        "patch": patch,
        "max_patch_bytes": max_patch_bytes,
    }


def _change_line(change: Mapping[str, Any]) -> str:
    status = change.get("status") or "?"
    path = change.get("path") or "<unknown>"
    from_path = change.get("from_path")
    if from_path:
        return f"- {status} {from_path} -> {path}"
    return f"- {status} {path}"


def _stat_line(stat: Mapping[str, Any]) -> str:
    path = stat.get("path") or "<unknown>"
    additions = stat.get("additions")
    deletions = stat.get("deletions")
    add_str = "?" if additions is None else f"+{additions}"
    del_str = "?" if deletions is None else f"-{deletions}"
    return f"- {path}: {add_str} / {del_str}"


def run(validated: dict[str, Any]) -> dict[str, Any]:
    title: str = validated["title"]
    base_ref: str = validated["base_ref"]
    target_ref: str = validated["target_ref"]
    changes: list[Mapping[str, Any]] = validated["changes"]
    stats: list[Mapping[str, Any]] = validated["stats"]
    patch: str = validated["patch"]
    max_patch_bytes: int = validated["max_patch_bytes"]

    lines = [f"# {title}", "", f"- Base: {base_ref}", f"- Target: {target_ref}"]

    if changes:
        lines.append("")
        lines.append("## Files")
        for change in changes:
            lines.append(_change_line(change))

    if stats:
        lines.append("")
        lines.append("## Diffstat")
        for stat in stats:
            lines.append(_stat_line(stat))

    if patch.strip():
        lines.append("")
        prefix = "## Patch"
        encoded_patch = patch.encode("utf-8")
        truncated = False
        if len(encoded_patch) > max_patch_bytes:
            truncated = True
            encoded_patch = encoded_patch[:max_patch_bytes]
        decoded_patch = encoded_patch.decode("utf-8", errors="ignore")
        if truncated:
            prefix = f"{prefix} (truncated to {max_patch_bytes} bytes)"
        lines.append(prefix)
        lines.append("```diff")
        lines.append(decoded_patch.rstrip())
        lines.append("```")

    changelog = "\n".join(lines).rstrip() + "\n"
    return {"title": title, "changelog": changelog}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("format_changelog result must be a dict")
    if "changelog" not in result:
        raise ValueError("format_changelog result missing changelog")
    if not isinstance(result["changelog"], str):
        raise ValueError("format_changelog changelog must be a string")
    return result


__all__ = ["validate", "run", "postcheck"]
