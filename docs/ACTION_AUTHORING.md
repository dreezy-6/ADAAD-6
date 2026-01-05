# Action Authoring Guide

This guide is for plugin writers creating user-supplied action modules loaded by the ADAAD-6 registry.

ADAAD-6 loads actions from `cfg.actions_dir` (default `.adaad/actions`) under `cfg.home`.
Actions are Python modules with a small required API.

---

## Quick summary

You ship a single `your_action.py` file containing:

- `validate(params, cfg) -> validated`
- `run(validated) -> result`
- `postcheck(result, cfg) -> result`

The registry rejects:
- missing functions
- non-callables
- variadic signatures (`*args`, `**kwargs`)
- duplicate action names
- action files that are symlinks
- actions_dir outside cfg.home or traversing symlinks

---

## Action module contract

### Required functions

#### 1) validate

Signature:
```python
def validate(params: dict[str, Any], cfg: AdaadConfig) -> Any: ...
```

Responsibilities:
- Validate types and required keys
- Normalize inputs to a stable structure
- Reject unsafe values early

Rules:
- Deterministic. No randomness.
- No side effects. Do not write files. Do not run subprocesses. Do not network.

#### 2) run

Signature:
```python
def run(validated: Any) -> Any: ...
```

Responsibilities:
- Perform the action’s work, if executed by your runtime.

Rules:
- ADAAD-6 itself does not execute actions. A separate runtime may.
- If your runtime executes actions, `run` may have side effects.
- Prefer idempotent behavior. If not idempotent, document it explicitly.

#### 3) postcheck

Signature:
```python
def postcheck(result: Any, cfg: AdaadConfig) -> Any: ...
```

Responsibilities:
- Validate the result shape
- Enforce tier-based safety rules if needed (example: skip on mobile)
- Raise on malformed or unsafe outputs

Rules:
- Deterministic checks only.
- No side effects.

---

## Determinism requirements

Your module must not introduce non-determinism into planning or registry behavior.

Guidelines:
- Do not rely on unsorted iteration of dicts from external sources.
- Do not call `time.time()` during validate or postcheck.
- Do not read environment variables during validate or postcheck.
- Avoid importing modules with import-time side effects.

If you need time, randomness, or external state, that belongs in your executor runtime, not in ADAAD-6 planning.

---

## Resource tiers

ADAAD-6 supports resource-tier filtering at planning time.
Your action should expose a cost hint through your `ActionSpec` authoring (planner-side), not in the module itself.

If you maintain your own executor:
- Gate expensive actions in `run` or `postcheck` based on `cfg.resource_tier`.
- Example pattern used by built-in `run_tests`:
  - `mobile` => skip
  - `edge/server` => allow

---

## Security and sandboxing rules

The registry enforces directory sandbox rules.
Your action must still enforce safe path handling if it touches the filesystem at runtime.

Runtime file safety:
- Treat all paths as untrusted inputs.
- Resolve under a trusted base directory (usually `cfg.home`).
- Reject `..` traversal.
- Reject symlink traversal if you are enforcing strict containment.

Example safe resolver (runtime-side):
```python
from pathlib import Path

def resolve_under_home_no_symlinks(cfg, raw: str) -> Path:
    home = Path(cfg.home).expanduser().resolve()
    p = Path(raw).expanduser()
    resolved = (p if p.is_absolute() else (home / p)).resolve(strict=False)

    rel = resolved.relative_to(home)

    probe = home
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("path must not traverse symlinks under cfg.home")

    return resolved
```

If you need to allow symlinks, document it and treat it as a policy decision of your executor.

---

## Minimal example action

Create: `.adaad/actions/echo.py`

```python
from __future__ import annotations

from typing import Any
from adaad6.config import AdaadConfig


def validate(params: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    msg = params.get("msg")
    if msg is None:
        raise ValueError("msg is required")
    return {"msg": str(msg)}


def run(validated: dict[str, Any]) -> dict[str, Any]:
    return {"echo": validated["msg"]}


def postcheck(result: dict[str, Any], cfg: AdaadConfig) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("result must be a dict")
    if "echo" not in result:
        raise ValueError("missing echo key")
    return result
```

Expected behavior:
- The registry will discover `echo.py` and register action name `echo`.
- A planner may produce an ActionSpec referencing `action="echo"` with params.

---

## Common pitfalls

### Import-time side effects

Bad:
- doing filesystem reads on import
- initializing global threads
- loading config from env on import

Fix:
- keep imports pure
- do work in `run`

### Accepting bytes for subprocess commands

Bad:
- accepting `bytes` and passing into `subprocess.run`

Fix:
- coerce to `str` or `list[str]`
- reject bytes

### Weak result validation

Bad:
- returning arbitrary objects without a defined shape

Fix:
- return dicts with stable keys
- validate in `postcheck`

---

## Testing your action

You can write a small harness test in your own repo:

```python
import importlib.util
from pathlib import Path
from adaad6.config import AdaadConfig

path = Path(".adaad/actions/echo.py")
spec = importlib.util.spec_from_file_location("echo", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

cfg = AdaadConfig()
validated = mod.validate({"msg": "hi"}, cfg)
result = mod.run(validated)
mod.postcheck(result, cfg)
print(result)
```

If you want registry-level validation, ensure your file is under cfg.home and not a symlink.
