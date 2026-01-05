from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _require_non_empty_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field} cannot be empty")
    return trimmed


def _require_identifier(value: Any, field: str) -> str:
    trimmed = _require_non_empty_str(value, field)
    if not _ID_PATTERN.fullmatch(trimmed):
        raise ValueError(f"{field} must match pattern {_ID_PATTERN.pattern}")
    return trimmed


def _coerce_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    if params is None:
        return {}
    if not isinstance(params, Mapping):
        raise ValueError("params must be a mapping")
    return dict(params)


def _coerce_str_sequence(raw: Iterable[str] | None, field: str) -> tuple[str, ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, (str, bytes)):
        raise ValueError(f"{field} must be an iterable of strings")
    normalized: list[str] = []
    for i, item in enumerate(raw):
        normalized.append(_require_non_empty_str(item, f"{field}[{i}]"))
    return tuple(normalized)


def _coerce_cost_hint(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("cost_hint must be numeric")
    if value != value or value in {float("inf"), float("-inf")}:
        raise ValueError("cost_hint must be finite")
    return float(value)


@dataclass(frozen=True)
class ActionSpec:
    id: str
    action: str
    params: dict[str, Any]
    preconditions: tuple[str, ...]
    effects: tuple[str, ...]
    cost_hint: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "params": dict(self.params),
            "preconditions": list(self.preconditions),
            "effects": list(self.effects),
            "cost_hint": self.cost_hint,
        }


def validate_action_spec(spec: ActionSpec) -> ActionSpec:
    return ActionSpec(
        id=_require_identifier(spec.id, "id"),
        action=_require_non_empty_str(spec.action, "action"),
        params=_coerce_params(spec.params),
        preconditions=_coerce_str_sequence(spec.preconditions, "preconditions"),
        effects=_coerce_str_sequence(spec.effects, "effects"),
        cost_hint=_coerce_cost_hint(spec.cost_hint),
    )


def action_spec_from_dict(raw: Mapping[str, Any]) -> ActionSpec:
    if raw is None:
        raise ValueError("action spec payload is required")
    params = _coerce_params(raw.get("params"))
    preconditions = _coerce_str_sequence(raw.get("preconditions"), "preconditions")
    effects = _coerce_str_sequence(raw.get("effects"), "effects")
    cost_hint = _coerce_cost_hint(raw.get("cost_hint"))

    spec = ActionSpec(
        id=_require_identifier(raw.get("id"), "id"),
        action=_require_non_empty_str(raw.get("action"), "action"),
        params=params,
        preconditions=preconditions,
        effects=effects,
        cost_hint=cost_hint,
    )
    return validate_action_spec(spec)


def validate_action_spec_list(specs: Sequence[ActionSpec]) -> list[ActionSpec]:
    return [validate_action_spec(spec) for spec in specs]


__all__ = ["ActionSpec", "action_spec_from_dict", "validate_action_spec", "validate_action_spec_list"]
