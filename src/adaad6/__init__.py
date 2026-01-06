"""
ADAAD-6 credibility-first core package.
"""

from .config import AdaadConfig, load_config

_LAZY_EXPORTS = {
    "ArchetypePolicy",
    "MetaOrchestrator",
    "OrchestratorResult",
    "get_archetype",
    "register_archetype",
}


def __getattr__(name):  # pragma: no cover - thin lazy import shim
    if name in _LAZY_EXPORTS:
        import importlib

        _mo = importlib.import_module(".meta_orchestrator", __name__)

        return getattr(_mo, name)
    raise AttributeError(name)


__all__ = ["AdaadConfig", "load_config", *_LAZY_EXPORTS]
