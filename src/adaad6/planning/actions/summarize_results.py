from __future__ import annotations

from typing import Any

from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    title = params.get("title", "Summary")
    results = params.get("results", [])
    if not isinstance(results, list):
        raise ValueError("results must be a list")
    return {"title": str(title), "results": results}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    title = validated["title"]
    results = validated["results"]
    lines = [f"# {title}"]
    for item in results:
        lines.append(f"- {item}")
    return {"title": title, "summary": "\n".join(lines)}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("summarize_results result must be a dict")
    if "summary" not in result:
        raise ValueError("summarize_results result missing summary")
    return result
