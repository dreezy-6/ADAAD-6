"""Built-in planning action modules.

The ADAAD-6 planner supports user-supplied actions loaded from a sandboxed
directory. This module exposes the built-in modules so the registry can
auto-register them without relying on filesystem discovery.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

_BUILTIN_ACTION_MODULE_NAMES: tuple[str, ...] = (
    "scan_repo_tree",
    "scan_risks",
    "mutate_code",
    "generate_patch",
    "run_tests",
    "summarize_results",
    "write_report",
)


def _load_builtin_module(name: str) -> ModuleType:
    return import_module(f"{__name__}.{name}")


def builtin_action_modules() -> tuple[tuple[str, ModuleType], ...]:
    """Return built-in action modules in deterministic order.

    The registry uses this mapping to seed the action catalog before applying
    any user-provided modules from the configured actions directory.
    """

    modules: list[tuple[str, ModuleType]] = []
    for name in _BUILTIN_ACTION_MODULE_NAMES:
        modules.append((name, _load_builtin_module(name)))
    return tuple(modules)


def builtin_action_names() -> tuple[str, ...]:
    return _BUILTIN_ACTION_MODULE_NAMES


__all__ = ["builtin_action_modules", "builtin_action_names"]
