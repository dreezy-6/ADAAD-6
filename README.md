# ADAAD-6

Deterministic planning core for auditable, resource-bound systems.

ADAAD-6 converts a goal into a predictable, validated sequence of actions under strict limits. It is intentionally narrow in scope, fully inspectable, and safe by default.

> ADAAD-6 is not an autonomous agent. It does not execute actions, learn, self-modify, or make uncontrolled decisions.

---

## What ADAAD-6 is

- **Deterministic planner**: same goal plus same config yields the same plan.
- **ActionSpec-based**: plans are sequences of validated `ActionSpec` objects.
- **Resource-aware**: planning output adapts to `mobile`, `edge`, `server` tiers.
- **Auditable**: no randomness, no hidden state, no external side effects during planning.
- **Sandboxed extensibility**: dynamic action modules are loaded only from validated, trusted paths.

---

## What ADAAD-6 is not

- Not a self-directing or self-modifying AI.
- Not an LLM wrapper.
- Not an agent runtime or executor.
- Not open-ended autonomy.

Everything is explicit, bounded, and inspectable.

---

## Core concept: ActionSpec

`ActionSpec` is the atomic unit of planning.

Each action declares:

- `id`: identifier (planner assigns deterministic ids like `act-001`)
- `action`: action name
- `params`: structured parameters
- `preconditions`: required prior effects
- `effects`: produced state markers
- `cost_hint`: relative execution cost used for tier filtering

All specs are validated and normalized before use. Malformed specs are rejected early.

---

## Quickstart

```python
from adaad6.planning.planner import make_plan
from adaad6.config import AdaadConfig

cfg = AdaadConfig()
plan = make_plan("Deliver a minimal credible plan", cfg)

print(plan.to_dict())
```

### Planner guarantees

- Same input → same output
- No randomness
- No hidden global state
- No external calls during planning
- Golden-testable output

---

## Resource tiers

Planning output is filtered by `cfg.resource_tier`:

| Tier   | Behavior                    |
| ------ | --------------------------- |
| mobile | Low-cost actions only       |
| edge   | Moderate-cost actions       |
| server | No cost ceiling             |

Configure via:

```python
from adaad6.config import AdaadConfig, ResourceTier

cfg = AdaadConfig(resource_tier=ResourceTier.MOBILE)
```

Cost handling rule: actions with `cost_hint=None` are treated as unbounded and excluded from constrained tiers.

---

## Hard limits

All plans respect strict deterministic limits:

- `planner_max_steps`
- `planner_max_seconds`

Limits are enforced during plan construction and recorded in `plan.meta`:

```json
{
  "truncated": false,
  "time_capped": false,
  "tier": "mobile"
}
```

---

## Action registry

Action implementations are loaded dynamically from a sandboxed directory.

- **Config**: `AdaadConfig(actions_dir=".adaad/actions")`
- **Built-ins**: pre-registered by the registry (see `adaad6.planning.actions.builtin_action_modules()`)
- **Discovery**: `adaad6.planning.registry.discover_actions(...)`

Safety guarantees:

- Directory must resolve under `cfg.home`
- No symlinks (directory traversal blocked)
- No `..` traversal
- Deterministic load order

Required module functions:

- `validate(params, cfg)`
- `run(validated)`
- `postcheck(result, cfg)`

Additional guarantees:

- Function signatures are inspected
- Variadic args (`*args`, `**kwargs`) are rejected
- Duplicate action names are rejected
- Dynamic imports are restricted to trusted paths only

---

## Determinism and auditability

ADAAD-6 is engineered for systems where predictability matters more than cleverness:

- Compliance-sensitive pipelines
- Embedded and mobile planning
- CI-verified decision logic
- Replayable and inspectable plans

Planning is deterministic; action execution may depend on external runtimes and should be audited separately.

---

## Status and scope

ADAAD-6 is a planning substrate.

Execution, orchestration, learning, and autonomy layers are intentionally out of scope and must be built explicitly on top if needed.

---

## Docs

- `ARCHITECTURE.md` (system overview, invariants, diagrams)
- `docs/` (additional references)

---

## License

See `LICENSE`.
