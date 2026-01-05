import tempfile
import types
import unittest

from adaad6.config import AdaadConfig
from adaad6.kernel.context import KernelContext
from adaad6.kernel.failures import (
    DETERMINISM_BREACH,
    EVIDENCE_MISSING,
    INTEGRITY_VIOLATION,
    KernelCrash,
)
from adaad6.planning.registry import ActionModule
from adaad6.planning.spec import ActionSpec
from adaad6.runtime.executor import ExecutionLog, execute_plan
from adaad6.runtime.executor import execute_and_record
from adaad6.provenance.ledger import read_events


def _spec(action: str, *, id_: str = "act-001") -> ActionSpec:
    return ActionSpec(
        id=id_,
        action=action,
        params={},
        preconditions=(),
        effects=(),
        cost_hint=None,
    )


def _action_module(name: str, validate, run, postcheck) -> ActionModule:
    module = types.ModuleType(name)
    module.validate = validate
    module.run = run
    module.postcheck = postcheck
    return ActionModule(name=name, module=module, validate=validate, run=run, postcheck=postcheck)


class ExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = AdaadConfig()

    def test_successful_execution_logs_all_stages(self) -> None:
        def validate(params, cfg):
            return {"checked": params, "cfg_mode": cfg.mode.value}

        def run(validated):
            return {"ran": validated["checked"], "mode": validated["cfg_mode"]}

        def postcheck(result, cfg):
            return {"postchecked": True, "result": result, "tier": cfg.resource_tier.value}

        actions = {"demo": _action_module("demo", validate, run, postcheck)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)

        self.assertIsInstance(log, ExecutionLog)
        self.assertTrue(log.ok)
        self.assertEqual("ok", log.status)
        self.assertEqual(1, len(log.steps))
        step = log.steps[0]
        self.assertEqual("ok", step.status)
        self.assertEqual(("precheck", "execute", "postcheck"), tuple(stage.stage for stage in step.stages))
        self.assertEqual({"postchecked": True, "result": {"ran": {}, "mode": "dev"}, "tier": "mobile"}, step.output)
        self.assertIsNone(log.crash_code)
        self.assertIsNone(log.crash_stage)
        self.assertEqual(log.context.run_id, log.to_dict()["run_id"])
        self.assertEqual(log.context.config.hash, log.to_dict()["config_hash"])
        self.assertIn("act-001:demo:result", log.context.artifacts.to_dict())

    def test_precheck_failure_maps_to_kernel_crash(self) -> None:
        def validate(params, cfg):
            raise ValueError("bad params")

        actions = {"demo": _action_module("demo", validate, lambda _: None, lambda r, c: r)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)

        self.assertFalse(log.ok)
        self.assertEqual("crash", log.status)
        self.assertEqual(INTEGRITY_VIOLATION, log.crash_code)
        step = log.steps[0]
        self.assertEqual("crash", step.status)
        self.assertEqual("precheck", log.crash_stage)
        self.assertEqual("act-001", log.crash_step)
        self.assertEqual(INTEGRITY_VIOLATION, step.code)
        self.assertEqual("bad params", step.detail)
        self.assertEqual("crash", step.stages[0].status)

    def test_execute_failure_and_halt_subsequent_steps(self) -> None:
        def validate(params, cfg):
            return params

        def run(validated):
            raise TimeoutError("hung")

        actions = {
            "fail": _action_module("fail", validate, run, lambda r, c: r),
            "skipped": _action_module("skipped", validate, lambda r: r, lambda r, c: r),
        }
        plan = [_spec("fail"), _spec("skipped", id_="act-002")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)

        self.assertFalse(log.ok)
        self.assertEqual(DETERMINISM_BREACH, log.crash_code)
        self.assertEqual("execute", log.crash_stage)
        self.assertEqual("act-001", log.crash_step)
        first, second = log.steps
        self.assertEqual("crash", first.status)
        self.assertEqual("skipped", second.status)
        self.assertEqual("skipped_after_crash", second.detail)
        self.assertEqual("halted_after_crash", second.stages[0].detail)

    def test_postcheck_failure_propagates_kernel_crash(self) -> None:
        def validate(params, cfg):
            return params

        def run(validated):
            return {"ok": True}

        def postcheck(result, cfg):
            raise KernelCrash(EVIDENCE_MISSING, "missing evidence")

        actions = {"demo": _action_module("demo", validate, run, postcheck)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)

        self.assertFalse(log.ok)
        self.assertEqual(EVIDENCE_MISSING, log.crash_code)
        self.assertEqual("postcheck", log.crash_stage)
        step = log.steps[0]
        self.assertEqual("crash", step.status)
        self.assertEqual(EVIDENCE_MISSING, step.code)
        self.assertEqual("missing evidence", step.detail)

    def test_unknown_action_produces_evidence_missing(self) -> None:
        plan = [_spec("unknown")]
        log = execute_plan(plan, actions={}, cfg=self.cfg)

        self.assertFalse(log.ok)
        self.assertEqual("crash", log.status)
        self.assertEqual(EVIDENCE_MISSING, log.crash_code)
        self.assertEqual("precheck", log.crash_stage)
        self.assertEqual("act-001", log.crash_step)
        self.assertEqual("crash", log.steps[0].status)

    def test_permission_error_maps_to_integrity(self) -> None:
        def validate(params, cfg):
            raise PermissionError("nope")

        actions = {"demo": _action_module("demo", validate, lambda _: None, lambda r, c: r)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)

        self.assertEqual(INTEGRITY_VIOLATION, log.crash_code)
        self.assertEqual("crash", log.steps[0].status)

    def test_context_is_used_when_provided(self) -> None:
        ctx = KernelContext.build(self.cfg, run_id="fixed-run")

        def validate(params, cfg):
            return {"ok": True}

        def run(validated):
            return {"result": True}

        def postcheck(result, cfg):
            return result

        actions = {"demo": _action_module("demo", validate, run, postcheck)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg, ctx=ctx)

        self.assertEqual("fixed-run", log.context.run_id)
        self.assertIn("act-001:demo:result", log.context.artifacts.to_dict())

    def test_execution_log_to_dict_includes_crash_summary(self) -> None:
        def validate(params, cfg):
            return params

        def run(validated):
            raise TimeoutError("determinism breach")

        actions = {"demo": _action_module("demo", validate, run, lambda r, c: r)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)
        serialized = log.to_dict()

        self.assertFalse(serialized["ok"])
        self.assertEqual("crash", serialized["status"])
        self.assertEqual(
            {
                "code": DETERMINISM_BREACH,
                "detail": "determinism breach",
                "stage": "execute",
                "step": "act-001",
            },
            serialized["crash"],
        )
        self.assertEqual("execute", serialized["steps"][0]["stages"][1]["stage"])
        self.assertEqual(DETERMINISM_BREACH, serialized["steps"][0]["stages"][1]["code"])

    def test_non_serializable_outputs_are_normalized(self) -> None:
        class Custom:
            def __repr__(self) -> str:
                return "<custom>"

        def validate(params, cfg):
            return Custom()

        def run(validated):
            return validated

        def postcheck(result, cfg):
            return result

        actions = {"demo": _action_module("demo", validate, run, postcheck)}
        plan = [_spec("demo")]

        log = execute_plan(plan, actions=actions, cfg=self.cfg)
        serialized = log.to_dict()

        self.assertFalse(isinstance(serialized["steps"][0]["output"], Custom))
        self.assertEqual({"__type__": "Custom", "__repr__": "<custom>"}, serialized["steps"][0]["output"])
        import json as _json

        _json.dumps(serialized)

    def test_execute_and_record_writes_ledger_events(self) -> None:
        def validate(params, cfg):
            return params

        def run(validated):
            return {"ok": True}

        def postcheck(result, cfg):
            return result

        actions = {"demo": _action_module("demo", validate, run, postcheck)}
        plan = [_spec("demo")]

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(
                home=tmpdir,
                ledger_enabled=True,
                ledger_dir=".adaad/ledger",
                ledger_filename="events.jsonl",
                log_path=".logs/adaad6.jsonl",
                actions_dir=".actions",
            )
            log = execute_and_record(plan, actions=actions, cfg=cfg)
            events = read_events(cfg)

        self.assertTrue(log.ok)
        self.assertEqual(3, len(events))
        self.assertEqual("execution_run_start", events[0]["type"])
        self.assertEqual("execution_step", events[1]["type"])
        self.assertEqual("execution_run_end", events[2]["type"])
        self.assertEqual(log.context.run_id, events[0]["payload"]["run_id"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
