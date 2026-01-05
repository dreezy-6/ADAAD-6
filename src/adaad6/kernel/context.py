from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from adaad6.config import AdaadConfig
from adaad6.kernel.hashing import hash_object


def _resolve_under_home(home: Path, raw_path: str) -> str:
    path = Path(raw_path)
    resolved = (path if path.is_absolute() else (home / path)).resolve(strict=False)
    try:
        rel = resolved.relative_to(home)
    except Exception as exc:
        raise ValueError("path must resolve under cfg.home") from exc
    probe = home
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("path must not traverse symlinks under cfg.home")
    return str(resolved)


@dataclass(frozen=True)
class WorkspacePaths:
    home: str
    actions_dir: str
    log_path: str
    ledger_path: str | None = None

    @classmethod
    def from_config(cls, cfg: AdaadConfig) -> "WorkspacePaths":
        home = Path(cfg.home).expanduser().resolve()
        actions_dir = _resolve_under_home(home, cfg.actions_dir)
        log_path = _resolve_under_home(home, cfg.log_path)

        ledger_path: str | None = None
        if cfg.ledger_enabled and (cfg.ledger_filename or "").strip():
            ledger_path = _resolve_under_home(home, str(Path(cfg.ledger_dir) / cfg.ledger_filename))

        return cls(home=str(home), actions_dir=actions_dir, log_path=log_path, ledger_path=ledger_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home": self.home,
            "actions_dir": self.actions_dir,
            "log_path": self.log_path,
            "ledger_path": self.ledger_path,
        }


@dataclass(frozen=True)
class ConfigSnapshot:
    values: Mapping[str, Any]
    hash: str

    @classmethod
    def from_config(cls, cfg: AdaadConfig) -> "ConfigSnapshot":
        snapshot = asdict(cfg)
        digest = hash_object(snapshot)
        return cls(values=MappingProxyType(snapshot), hash=digest)

    def to_dict(self) -> dict[str, Any]:
        return {"values": dict(self.values), "hash": self.hash}


@dataclass(frozen=True)
class ArtifactRegistry:
    artifacts: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def register(self, name: str, uri: str) -> "ArtifactRegistry":
        if not name.strip():
            raise ValueError("artifact name must be set")
        if not uri.strip():
            raise ValueError("artifact uri must be set")
        if any(existing == name for existing, _ in self.artifacts):
            raise ValueError(f"artifact {name} already registered")
        return ArtifactRegistry(artifacts=self.artifacts + ((name, uri),))

    def to_dict(self) -> dict[str, str]:
        return {name: uri for name, uri in self.artifacts}


@dataclass(frozen=True)
class KernelContext:
    workspace: WorkspacePaths
    run_id: str
    config: ConfigSnapshot
    artifacts: ArtifactRegistry = field(default_factory=ArtifactRegistry)

    @classmethod
    def build(
        cls, cfg: AdaadConfig, *, run_id: str | None = None, artifacts: ArtifactRegistry | None = None
    ) -> "KernelContext":
        return cls(
            workspace=WorkspacePaths.from_config(cfg),
            run_id=run_id or uuid4().hex,
            config=ConfigSnapshot.from_config(cfg),
            artifacts=artifacts or ArtifactRegistry(),
        )

    def register_artifact(self, name: str, uri: str) -> "KernelContext":
        return KernelContext(
            workspace=self.workspace,
            run_id=self.run_id,
            config=self.config,
            artifacts=self.artifacts.register(name, uri),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace.to_dict(),
            "run_id": self.run_id,
            "config": self.config.to_dict(),
            "artifacts": self.artifacts.to_dict(),
        }


__all__ = ["ArtifactRegistry", "ConfigSnapshot", "KernelContext", "WorkspacePaths"]
