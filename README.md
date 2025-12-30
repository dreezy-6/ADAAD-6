# ADAAD-6

## Credibility-first doctrine
ADAAD-6 exists to prove claims, not to accumulate features. Every component is scoped to a clear, falsifiable responsibility so that credibility is earned through evidence. The system prioritizes auditable behaviors, predictable interfaces, and minimal inter-module coupling.

### Scope and module boundaries
- **Command & Orchestration**: A slim controller that sequences tasks, enforces policies, and exposes deterministic entry points. No embedded business logic; it only routes and validates.
- **Reasoning & Decomposition**: Modules that transform objectives into actionable plans using bounded reasoning cycles. Inputs/outputs are structured and serializable; side effects are disallowed.
- **Memory & State**: Persistence layer for episodic traces and durable artifacts with explicit retention rules. Writing requires provenance metadata; reading requires capability checks.
- **Execution Adapters**: Sandbox-facing workers that perform external actions with idempotent contracts and auditable logs. Adapters cannot call each other directly; the orchestrator mediates all calls.
- **Assurance & Verification**: Cross-cutting hooks (schema checks, invariants, audits) that run before/after critical actions. These modules produce machine-verifiable evidence instead of dashboards only.

### Responsibilities
- Maintain minimal public APIs with typed contracts and reproducible behaviors.
- Route all side effects through adapters gated by policy checks.
- Record proofs (logs, traces, checksums) for every externally observable action.
- Keep reasoning loops bounded (iteration limits, time caps) and observable.
- Prefer small, composable workers over monoliths; every boundary should make verification easier.

## Invariants and verification hooks
The following claims must hold; CI should contain or trigger checks for each item:
- **Deterministic inputs/outputs**: Given the same request, orchestration produces the same planned steps unless configuration changes are present. Verification: golden snapshot tests for planner outputs.
- **Bounded reasoning**: No planner exceeds configured step/time limits. Verification: unit tests with timers and iteration counters; CI guardrails that fail on overrun.
- **Auditable side effects**: Every adapter call emits a structured log with actor, intent, inputs, outputs, and checksum. Verification: contract tests that assert log shape and checksum presence.
- **Provenance-enforced storage**: Writes to memory require provenance tokens; reads enforce capability scope. Verification: policy tests and simulated access attempts with expected denials.
- **Idempotent adapters**: External operations are safe to retry. Verification: integration tests that re-run the same action and assert stable outputs/state.
- **Configuration-first safety**: Defaults are conservative; escalations require explicit flags. Verification: configuration lint that rejects unsafe defaults and missing limits.

### Claims-to-components mapping
- Deterministic inputs/outputs → Orchestrator + Planner interfaces + Golden snapshot suite.
- Bounded reasoning → Planner loop controls + Time/step guards + CI overrun tests.
- Auditable side effects → Execution Adapters + Structured logging library + Log schema contracts.
- Provenance-enforced storage → Memory layer + Capability validator + Policy fixtures.
- Idempotent adapters → Adapter contracts + Integration retry harness.
- Configuration-first safety → Config schemas + Lint checks + Safe-default presets.

## Non-goals and anti-features
- No implicit network or filesystem access; every side effect must be explicit and logged.
- No hidden state, global singletons, or mutable caches inside reasoning modules.
- No unbounded agent loops or self-modifying behaviors without human-reviewed proofs.
- No opaque heuristics without measurable accuracy/error budgets.
- No cross-adapter coupling that bypasses orchestration.
- No “move fast” shortcuts that weaken verification or observability.

## Roadmap (fork-ready, milestone-linked)
1. **Baseline credibility (Week 1)**: Establish config schemas, golden planner tests, and log contract checks; wire CI to fail on invariant drift.
2. **Auditable adapters (Week 2)**: Implement structured logging wrappers and idempotent adapter templates; add retry harness tests.
3. **Provenance-first memory (Week 3)**: Enforce provenance tokens on writes and capability scopes on reads; add policy simulation tests.
4. **Bounded reasoning (Week 4)**: Add iteration/time guards to planners with CI overrun detection; publish safe-default presets.
5. **Hardening and misuse resistance (Week 5+)**: Expand non-goal guardrails (lint rules, config validators), tighten observability, and document escalation paths.

### Terminology
- **Adapter**: A sandboxed worker that performs a side effect under orchestrator control.
- **Planner**: Reasoning module that decomposes goals into steps under bounded constraints.
- **Provenance token**: Metadata proving origin and authorization for a state mutation.
- **Golden snapshot**: Recorded planner output used to detect drift or non-determinism.
