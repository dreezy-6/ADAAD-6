from dataclasses import InitVar, dataclass
from os import environ
from pathlib import PurePosixPath, PureWindowsPath
from typing import Mapping, MutableMapping


ENV_PREFIX = "ADAAD6_"


@dataclass(frozen=True)
class AdaadConfig:
    version: str = "0.0.0"
    mutation_enabled: bool = False
    planner_max_steps: int = 25
    planner_max_seconds: float = 2.0
    log_schema_version: str = "1"
    ledger_enabled: bool = False
    ledger_dir: str = ".adaad/ledger"
    ledger_filename: str = "events.jsonl"
    ledger_schema_version: str = "1"
    ledger_file: InitVar[str | None] = None

    def __post_init__(self, ledger_file: str | None) -> None:
        normalized = (self.ledger_filename or "").strip()
        object.__setattr__(self, "ledger_filename", normalized)
        if ledger_file is not None and self.ledger_filename == AdaadConfig.ledger_filename:
            object.__setattr__(self, "ledger_filename", (ledger_file or "").strip())

    def __getattribute__(self, name: str):
        if name == "ledger_file":
            raise AttributeError(name)
        return super().__getattribute__(name)

    def __getattr__(self, name: str) -> str:
        if name == "ledger_file":
            return self.ledger_filename
        raise AttributeError(name)

    def validate(self) -> None:
        if self.planner_max_steps <= 0:
            raise ValueError("planner_max_steps must be > 0")
        if self.planner_max_seconds <= 0:
            raise ValueError("planner_max_seconds must be > 0")
        if self.ledger_enabled and not (self.ledger_dir or "").strip():
            raise ValueError("ledger_dir must be set when ledger logging is enabled")
        if self.ledger_enabled and not (self.ledger_filename or "").strip():
            raise ValueError("ledger_filename must be set when ledger logging is enabled")
        if self.ledger_enabled:
            ledger_file_raw = (self.ledger_filename or "").strip()
            ledger_file_posix = PurePosixPath(ledger_file_raw)
            ledger_file_windows = PureWindowsPath(ledger_file_raw)

            if ledger_file_posix.is_absolute() or ledger_file_windows.is_absolute() or ledger_file_windows.drive:
                raise ValueError("ledger_filename must be a relative path")
            if ledger_file_raw.startswith("~"):
                raise ValueError("ledger_filename must not start with ~")
            if ".." in ledger_file_posix.parts or ".." in ledger_file_windows.parts:
                raise ValueError("ledger_filename must not contain parent directory traversal")
            if not (self.ledger_schema_version or "").strip():
                raise ValueError("ledger_schema_version must be set when ledger logging is enabled")


def _coerce_bool(value: str) -> bool:
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    lowered = value.strip().lower()
    if lowered in truthy:
        return True
    if lowered in falsy:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _coerce_int(value: str, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer for {field}: {value}") from exc


def _coerce_float(value: str, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid float for {field}: {value}") from exc


def _get_env(env: Mapping[str, str], key: str) -> str | None:
    return env.get(f"{ENV_PREFIX}{key}")


def load_config(env: Mapping[str, str] | None = None) -> AdaadConfig:
    source: Mapping[str, str] | MutableMapping[str, str] = env or environ

    version = _get_env(source, "VERSION") or AdaadConfig.version
    mutation_raw = _get_env(source, "MUTATION_ENABLED")
    mutation_enabled = (
        _coerce_bool(mutation_raw) if mutation_raw is not None else AdaadConfig.mutation_enabled
    )

    steps_raw = _get_env(source, "PLANNER_MAX_STEPS")
    planner_max_steps = (
        _coerce_int(steps_raw, "planner_max_steps")
        if steps_raw is not None
        else AdaadConfig.planner_max_steps
    )

    seconds_raw = _get_env(source, "PLANNER_MAX_SECONDS")
    planner_max_seconds = (
        _coerce_float(seconds_raw, "planner_max_seconds")
        if seconds_raw is not None
        else AdaadConfig.planner_max_seconds
    )

    log_schema_version = _get_env(source, "LOG_SCHEMA_VERSION") or AdaadConfig.log_schema_version

    ledger_enabled_raw = _get_env(source, "LEDGER_ENABLED")
    ledger_enabled = (
        _coerce_bool(ledger_enabled_raw)
        if ledger_enabled_raw is not None
        else AdaadConfig.ledger_enabled
    )

    ledger_dir = _get_env(source, "LEDGER_DIR") or AdaadConfig.ledger_dir
    ledger_file_env = _get_env(source, "LEDGER_FILE")
    ledger_filename_env = _get_env(source, "LEDGER_FILENAME")
    ledger_filename = ledger_file_env or ledger_filename_env or AdaadConfig.ledger_filename

    ledger_schema_version = (
        _get_env(source, "LEDGER_SCHEMA_VERSION")
        # default ledger schema matches log schema unless explicitly overridden
        or log_schema_version
    )

    cfg = AdaadConfig(
        version=version,
        mutation_enabled=mutation_enabled,
        planner_max_steps=planner_max_steps,
        planner_max_seconds=planner_max_seconds,
        log_schema_version=log_schema_version,
        ledger_enabled=ledger_enabled,
        ledger_dir=ledger_dir,
        ledger_filename=ledger_filename,
        ledger_schema_version=ledger_schema_version,
    )
    cfg.validate()
    return cfg


__all__ = ["AdaadConfig", "load_config"]
