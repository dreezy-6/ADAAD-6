from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig


def _coerce_templates(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ("scaffold",)
    if isinstance(raw, (bytes, bytearray)):
        raise ValueError("available templates must not be bytes")
    if isinstance(raw, str):
        return (str(raw),)
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw)
    raise ValueError("available templates must be a list, tuple, or string")


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    requested = str(params.get("name", "scaffold")).strip() or "scaffold"
    available = _coerce_templates(params.get("available"))
    return {"selected": requested, "available": available}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    selected = validated["selected"]
    available = validated["available"]
    ok = selected in available
    return {"selected": selected, "available": list(available), "ok": ok, "reason": None if ok else "not_available"}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("select_template result must be a dict")
    if "selected" not in result:
        raise ValueError("select_template result missing selection")
    if result.get("ok") is False:
        raise ValueError("select_template failed to select an available template")
    return result
