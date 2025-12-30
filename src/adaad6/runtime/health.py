from pathlib import Path


def _package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check_structure() -> bool:
    root = _package_root()
    required = [
        root,
        root / "runtime",
        root / "planning",
        root / "adapters",
        root / "assurance",
    ]
    return all(path.exists() for path in required)


__all__ = ["check_structure"]
