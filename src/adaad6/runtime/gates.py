from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from adaad6.kernel.hashing import hash_object


@dataclass(frozen=True)
class LineageGateResult:
    ok: bool
    reason: str | None = None
    lineage_hash: str | None = None


class EvidenceStore:
    """Minimal in-memory Cryovant evidence store.

    The store retains lineage nodes keyed by their canonical hash and refuses to
    return nodes whose hash does not match their contents. This keeps the gate
    logic deterministic and tamper-resistant for unit tests.
    """

    def __init__(self, lineages: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._lineages: dict[str, dict[str, Any]] = {}
        for lineage_hash, payload in (lineages or {}).items():
            self._lineages[lineage_hash] = dict(payload)

    def add_lineage(self, payload: Mapping[str, Any]) -> str:
        base = dict(payload)
        base.pop("hash", None)
        lineage_hash = hash_object(base)
        record = {**base, "hash": lineage_hash}
        self._lineages[lineage_hash] = record
        return lineage_hash

    def resolve_lineage(self, lineage_hash: str) -> Mapping[str, Any] | None:
        node = self._lineages.get(lineage_hash)
        if node is None:
            return None
        expected = hash_object({k: v for k, v in node.items() if k != "hash"})
        if node.get("hash") != expected or lineage_hash != expected:
            return None
        return dict(node)


def cryovant_lineage_gate(
    *, evidence_store: EvidenceStore | None, lineage_hash: str | None
) -> LineageGateResult:
    if lineage_hash is None or not str(lineage_hash).strip():
        return LineageGateResult(False, "cryovant_lineage_missing", None)
    if evidence_store is None:
        return LineageGateResult(False, "cryovant_evidence_store_missing", lineage_hash)
    lineage = evidence_store.resolve_lineage(lineage_hash)
    if lineage is None:
        return LineageGateResult(False, "cryovant_lineage_unknown", lineage_hash)
    expected = hash_object({k: v for k, v in lineage.items() if k != "hash"})
    if expected != lineage_hash:
        return LineageGateResult(False, "cryovant_lineage_hash_mismatch", lineage_hash)
    return LineageGateResult(True, None, lineage_hash)


__all__ = ["EvidenceStore", "LineageGateResult", "cryovant_lineage_gate"]
