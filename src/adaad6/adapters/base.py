from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from adaad6.assurance.logging import build_log_event, compute_checksum
from adaad6.config import AdaadConfig


def idempotency_key(intent: str, inputs: dict[str, Any]) -> str:
    payload = {"intent": intent, "inputs": inputs}
    return compute_checksum(payload)


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    output: dict[str, Any]
    log: dict[str, Any]


class BaseAdapter:
    name: str = "base"

    def _execute(self, intent: str, inputs: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement _execute")

    @staticmethod
    def _utc_now_iso_z() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def run(
        self,
        intent: str,
        inputs: dict[str, Any],
        actor: str,
        cfg: AdaadConfig,
        now_fn: Callable[[], str] | None = None,
    ) -> AdapterResult:
        cfg.validate()
        timestamp_fn = now_fn or self._utc_now_iso_z
        outputs = self._execute(intent=intent, inputs=inputs, cfg=cfg)
        log_event = build_log_event(
            schema_version=cfg.log_schema_version,
            ts=timestamp_fn(),
            actor=actor,
            intent=intent,
            inputs=inputs,
            outputs=outputs,
        )
        return AdapterResult(ok=True, output=outputs, log=log_event.to_dict())


__all__ = ["BaseAdapter", "AdapterResult", "idempotency_key"]
