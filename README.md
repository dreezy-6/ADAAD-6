
ADAAD-6

Autonomous Device-Anchored Adaptive Development
Governed, deterministic, repo-first autonomous planning engine


---

Overview

ADAAD-6 is a governed autonomous planning and execution engine designed to operate safely in constrained environments while producing deterministic, auditable outcomes.

It is not a general AI agent.
It is a software factory core.

ADAAD-6 generates plans, executes validated actions, records provable lineage, and produces machine- and human-readable artifacts without uncontrolled mutation.

Key design goals:

Deterministic execution

Governance before autonomy

Stable schemas

Explicit failure modes

Mobile-safe operation

Ledger-backed provenance



---

Core Capabilities

1. Deterministic Planning Engine

Plans are explicit DAGs of actions.

Each step has:

Preconditions

Effects

Cost hints


No hidden execution paths.


2. Governed Action System

Actions are:

Validated

Executed

Post-checked


Every action has a fixed schema contract.

Failures are explicit, not implicit.


3. Built-in Planning Templates

ADAAD-6 ships with auditable, reusable planning templates:

Template	Purpose

doctor_report	Structural and health checks
diff_report	Git-based changelog and patch analysis
scaffold	Governed project scaffolding pipeline


Templates emit Plan JSON, not side effects.

4. Mobile-Tier Safety

Heavy operations automatically skip on ResourceTier.MOBILE.

Skips still return valid results.

Summaries record limitations instead of failing.


5. Ledger-Backed Provenance

Optional append-only ledger.

Events recorded deterministically.

Ledger disabled or readonly modes are respected.

Skips still mark completion.



---

Repository Structure

src/adaad6/
├── cli.py                     # CLI entrypoint
├── config.py                  # Runtime configuration
├── planning/
│   ├── planner.py             # Plan construction
│   ├── spec.py                # ActionSpec + validation
│   ├── templates.py           # Built-in planning templates
│   └── actions/
│       ├── _command_utils.py  # Safe command execution primitives
│       ├── run_tests.py
│       ├── generate_scaffold.py
│       ├── record_ledger.py
│       ├── select_template.py
│       └── ...
└── provenance/
    └── ledger.py              # Hash-chained event log


---

Installation

Supported Python: 3.10 or newer.

Install dependencies:

pip install .

Or install the published package:

pip install adaad6

Verify the CLI is available:

adaad6 --help

Minimal end-to-end example (local install):

pip install . && adaad6 version

The version command prints a stable, single-line version string suitable for scripts.


---

CLI Usage

Show Version

adaad6 version

Generate a Plan

adaad6 plan "generate scaffold"

Emit a Planning Template (JSON Only)

Doctor Report

adaad6 template doctor_report --destination doctor.txt

Diff Report

adaad6 template diff_report --base-ref origin/main --destination changelog.md

Scaffold Pipeline

adaad6 template scaffold --destination scaffold.md

> These commands do not execute actions.
They emit deterministic Plan JSON suitable for review, storage, or downstream execution.




---

Scaffold Template Flow

The scaffold template is a governed multi-step pipeline:

1. select_template


2. generate_scaffold


3. run_tests


4. record_ledger


5. summarize_results


6. write_report



Mobile tier behavior:

Scaffold generation is skipped.

Tests are skipped.

Summary records limitations instead of failing.



---

Safe Command Execution

ADAAD-6 never executes arbitrary shell strings.

All command execution flows through:

adaad6.planning.actions._command_utils

Guarantees

No shell execution

No empty commands

No byte tokens

Allow-listed binaries only

Stable return schema in all cases


Execution Result Schema

{
  "timeout": false,
  "returncode": 0,
  "stdout": "",
  "stderr": "",
  "error": null
}

Errors are explicit:

EmptyCommand

NotPermitted

FileNotFoundError

Timeout



---

Governance Model (He65-Aligned)

Mutation is not automatic

Plans are inspectable artifacts

Execution is deterministic

Lineage is append-only

Drift is treated as failure


ADAAD-6 is designed to be embedded inside larger autonomous systems without compromising control or auditability.


---

What ADAAD-6 Is Not

Not a chatbot

Not a self-mutating agent

Not a probabilistic executor

Not a black box


Every decision path is visible.
Every side effect is intentional.


---

Testing

Run full test suite:

python -m unittest -q

The test suite enforces:

Schema stability

Mobile tier behavior

Command safety

Ledger correctness

Template integrity

Expected outcome: all tests should pass quickly on a local CPU-only environment without external services; no network access is required.



---

Strategic Positioning

ADAAD-6 is the core execution spine for:

Autonomous code factories

Governed agent swarms

Compliance-critical automation

Mobile-constrained AI systems

Long-running self-evolving software


It optimizes for trust, determinism, and longevity, not novelty.


---

License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for full terms.
