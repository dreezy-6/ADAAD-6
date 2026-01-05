from __future__ import annotations

import hashlib
import importlib.util
import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

from adaad6.config import AdaadConfig

ActionValidator = Callable[[dict[str, Any], AdaadConfig], Any]
ActionRunner = Callable[[Any], Any]
ActionPostcheck = Callable[[Any, AdaadConfig], Any]


@dataclass(frozen=True)
class ActionModule:
    name: str
    module: ModuleType
    validate: ActionValidator
    run: ActionRunner
    postcheck: ActionPostcheck


def _is_valid_callable(obj: Any) -> bool:
    return callable(obj)


def _load_module(path: Path) -> ModuleType:
    module_id = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(f"adaad6.planning.actions.{path.stem}_{module_id}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load action module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_action_module(name: str, module: ModuleType) -> ActionModule:
    required = {"validate", "run", "postcheck"}
    missing = [item for item in required if not hasattr(module, item)]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Action module '{name}' missing required functions: {missing_list}")

    validate_fn = getattr(module, "validate")
    run_fn = getattr(module, "run")
    postcheck_fn = getattr(module, "postcheck")

    for fn_name, fn in {"validate": validate_fn, "run": run_fn, "postcheck": postcheck_fn}.items():
        if not _is_valid_callable(fn):
            raise TypeError(f"Action module '{name}' attribute '{fn_name}' must be callable")

    _verify_signature("validate", validate_fn)
    _verify_signature("run", run_fn)
    _verify_signature("postcheck", postcheck_fn)

    return ActionModule(name=name, module=module, validate=validate_fn, run=run_fn, postcheck=postcheck_fn)


def _iter_action_paths(actions_dir: Path) -> Iterable[Path]:
    if not actions_dir.exists():
        return tuple()
    if actions_dir.is_symlink():
        raise ValueError("actions_dir must not be a symlink")
    return tuple(
        sorted(
            (
                path
                for path in actions_dir.iterdir()
                if path.is_file() and path.suffix == ".py" and not path.name.startswith("__")
            ),
            key=lambda p: p.name,
        )
    )


def _verify_signature(name: str, fn: Callable[..., Any]) -> None:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Cannot inspect signature for '{name}': {exc}") from exc

    params = list(signature.parameters.values())
    for param in params:
        if param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            raise TypeError(f"{name} must not use variadic parameters")

    usable = [
        param
        for param in params
        if param.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    ]
    required = {"validate": 2, "run": 1, "postcheck": 2}.get(name)
    if required is None:
        return
    if len(usable) < required:
        if name == "validate":
            raise TypeError("validate must accept at least (params, cfg)")
        if name == "run":
            raise TypeError("run must accept at least (validated)")
        raise TypeError("postcheck must accept at least (result, cfg)")


def _ensure_actions_dir(actions_dir: Path, *, cfg: AdaadConfig) -> Path:
    home = Path(cfg.home).expanduser().resolve()
    target = actions_dir if actions_dir.is_absolute() else (home / actions_dir)
    try:
        resolved = target.resolve(strict=False)
    except TypeError:
        resolved = Path(os.path.abspath(str(target)))

    try:
        rel = resolved.relative_to(home)
    except Exception as exc:
        raise ValueError("actions_dir must resolve under cfg.home") from exc

    probe = home
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("actions_dir must not traverse symlinks")

    return resolved


def discover_actions(actions_dir: Path | None = None, *, cfg: AdaadConfig) -> dict[str, ActionModule]:
    base_dir = _ensure_actions_dir(actions_dir or Path(cfg.actions_dir), cfg=cfg)
    actions: dict[str, ActionModule] = {}

    for path in _iter_action_paths(base_dir):
        if path.is_symlink():
            raise ValueError("action files must not be symlinks")
        module = _load_module(path)
        action_module = _validate_action_module(path.stem.lower(), module)
        if action_module.name in actions:
            raise ValueError(f"Duplicate action name: {action_module.name}")
        actions[action_module.name] = action_module

    return actions


__all__ = ["ActionModule", "discover_actions"]
