# Canon Law v1.0 Traceability

This document maps the current ADAAD-6 thesis to concrete enforcement points in the codebase and records known governance gaps. The intent is to keep doctrine and implementation aligned and to fail closed when the two diverge.

## Canon Law invariants (current enforcement)

- **LAW-001 — Tree Law (package layout is canonical)**
  - **Enforcement:** `adaad6.runtime.health._tree_law_status` validates the package root contains only the sanctioned Canon Tree entries and no extras. The result is folded into `check_structure_details`, which is consumed by `boot_sequence` to block startup when the tree is violated.  
  - **Failure mode:** `tree_law=False` and a descriptive `tree_law_error`; `boot_sequence` returns `ok=False`, preventing admissibility from proceeding.

- **LAW-011 — Gate Law (ancestry must be validated)**
  - **Current status:** No explicit Cryovant ancestry gate is wired into the kernel. Mutation/evolution remains disabled by default via `AdaadConfig.mutation_enabled=False`, but there is no guard that forces lineage validation before enabling.  
  - **Gap:** Add a gate that refuses planner/evolver entry unless a Cryovant-backed lineage proof is supplied.

- **LAW-015 — Metal Law (Aponi dashboard reads canonical telemetry)**
  - **Current status:** No Aponi integration exists. Ledger writes are canonicalized via `assurance.logging` and `provenance.ledger`, but no dashboard consumer is enforced.  
  - **Gap:** Introduce a telemetry export contract and require dashboard health checks to fail closed when canonical feeds are absent.

## Thesis-to-repo trace table

| Thesis claim | Module | Enforcement mechanism | Failure mode |
| --- | --- | --- | --- |
| Kernel refuses to run on non-canonical tree (LAW-001) | `runtime/health.py` (`_tree_law_status`, `check_structure_details`) | Hard check of allowed root entries; bubbled into boot status | `tree_law=False`, `boot_sequence.ok=False` |
| Evidence must be hash-consistent | `kernel.admissibility._resolve` | Recomputes hash of loaded node and raises `KernelCrash` on mismatch | `KernelCrash(INTEGRITY_VIOLATION)` |
| Ledger appends are hash-chained | `provenance.ledger.append_event` | Computes hash over canonical JSON with `prev_hash` link | Invalid chain rejected by downstream verifiers; on-write failures raise |
| Mutation disabled unless explicitly enabled | `config.AdaadConfig` defaults; `runtime.boot.boot_sequence` exposes `mutation_enabled` flag | Defaults to `False`; no mutation path when flag remains unset | Planner/evolver code paths remain inert |
| Execution must emit records | `kernel.admissibility._evaluate` | Requires `will_emit_execution_record=True` in evidence bundle | `KernelCrash(UNLOGGED_EXECUTION)` |

## Governance gap audit (initial)

- **Cryovant ancestry gating missing (LAW-011):** No hook ensures evolution cycles verify lineage. Add a gate around any planner/evolver entrypoint that checks a Cryovant-backed EvidenceStore for ancestry proof and crashes otherwise.
- **Aponi telemetry contract absent (LAW-015):** Dashboard consumption is unspecified. Define a canonical telemetry schema and enforce its availability during health checks.
- **EvidenceStore abstraction not yet integrated:** Kernel admissibility still relies on caller-provided resolvers instead of a hardened store, leaving room for bypasses. Introduce an `EvidenceStore` interface with crash-on-miss semantics and route admissibility through it.

## Next enforcement steps

1. Wire Gate Law: require a Cryovant ancestry validation step before any evolution/mutation loop runs; fail closed without proof.
2. Add Aponi telemetry health check: require canonical ledger/metrics presence during boot; refuse when absent.
3. Replace ad hoc node resolvers with an `EvidenceStore` backed by canonical JSON hashing, aligning admissibility and replay with content-addressed storage.
