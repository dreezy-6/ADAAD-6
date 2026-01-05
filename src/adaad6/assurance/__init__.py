"""Assurance utilities such as structured logging."""

__all__ = ["logging", "run_doctor"]

from . import logging  # noqa: F401
from typing import Any


def run_doctor(*args: Any, **kwargs: Any) -> Any:
    """Lazy import wrapper for adaad6.assurance.doctor.run_doctor."""
    from .doctor import run_doctor as _run_doctor

    return _run_doctor(*args, **kwargs)
