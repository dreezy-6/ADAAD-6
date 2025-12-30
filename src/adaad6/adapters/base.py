from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from adaad6.assurance.logging import build_log_event, compute_checksum
from adaad6.config import AdaadConfig
from adaad6.provenance.ledger import append_event


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
        ts = timestamp_fn()
        log_event = build_log_event(
            schema_version=cfg.log_schema_version,
            ts=ts,
            actor=actor,
            intent=intent,
            inputs=inputs,
            outputs=outputs,
        )
        log_base = log_event.to_dict()

        ledger_appended = False
        ledger_event_hash: str | None = None
        ledger_error: str | None = None

        if cfg.ledger_enabled:
            try:
                event = append_event(
                    cfg=cfg,
                    event_type="adapter_call",
                    payload=log_base,
                    ts=ts,
                    actor=actor,
                )
                ledger_appended = True
                hash_value = event.get("hash")
                ledger_event_hash = hash_value if isinstance(hash_value, str) else None
            except Exception as exc:  # pragma: no cover - defensive
                ledger_appended = False
                ledger_error = str(exc)

        log_dict = log_base | {
            "ledger_appended": ledger_appended,
            "ledger_error": ledger_error,
            "ledger_event_hash": ledger_event_hash,
        }

        return AdapterResult(ok=True, output=outputs, log=log_dict)


__all__ = ["BaseAdapter", "AdapterResult", "idempotency_key"]
