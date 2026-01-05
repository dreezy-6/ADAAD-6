from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig, ResourceTier


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    template = str(params.get("template", "scaffold")).strip() or "scaffold"
    components = params.get("components", ("core", "actions", "assurance"))
    if isinstance(components, (bytes, bytearray)):
        raise ValueError("components must not be bytes")
    if isinstance(components, str):
        components = (components,)
    elif not isinstance(components, (list, tuple)):
        raise ValueError("components must be a list or tuple of strings")
    normalized = tuple(str(item) for item in components)
    return {"template": template, "components": normalized, "tier": cfg.resource_tier}


def _scaffold_summary(template: str, components: tuple[str, ...]) -> dict[str, Any]:
    return {
        "template": template,
        "components": list(components),
        "files": [f"{template}/{name}.md" for name in components],
        "notes": [f"Generated scaffold for '{template}' with {len(components)} components"],
    }


def run(validated: dict[str, Any]) -> dict[str, Any]:
    tier: ResourceTier = validated["tier"]
    if tier == ResourceTier.MOBILE:
        return {
            "skipped": True,
            "reason": "resource_tier=mobile",
            "scaffold": None,
            "limitations": ["Scaffold generation skipped on mobile tier"],
        }

    scaffold = _scaffold_summary(validated["template"], validated["components"])
    return {"skipped": False, "scaffold": scaffold, "limitations": []}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("generate_scaffold result must be a dict")
    if cfg.resource_tier == ResourceTier.MOBILE:
        if not result.get("skipped"):
            raise ValueError("mobile tier must skip scaffold generation")
    return result
