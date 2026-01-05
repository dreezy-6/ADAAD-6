import unittest
from unittest.mock import patch

from adaad6.config import AdaadConfig, ResourceTier
from adaad6.planning.planner import make_plan


class PlannerGoldenTest(unittest.TestCase):
    def test_deterministic_plan(self) -> None:
        goal = "Deliver a minimal credible plan"
        cfg = AdaadConfig()

        first_plan = make_plan(goal, cfg).to_dict()
        second_plan = make_plan(goal, cfg).to_dict()

        expected = {
            "goal": "Deliver a minimal credible plan",
            "steps": [
                {
                    "id": "act-001",
                    "action": "clarify_goal",
                    "params": {"goal": "Deliver a minimal credible plan"},
                    "preconditions": [],
                    "effects": ["goal_clarity"],
                    "cost_hint": 0.05,
                },
                {
                    "id": "act-002",
                    "action": "identify_constraints",
                    "params": {"goal": "Deliver a minimal credible plan"},
                    "preconditions": ["goal_clarity"],
                    "effects": ["constraints_noted"],
                    "cost_hint": 0.25,
                },
                {
                    "id": "act-003",
                    "action": "propose_actions",
                    "params": {"goal": "Deliver a minimal credible plan", "fanout": 3},
                    "preconditions": ["constraints_noted"],
                    "effects": ["options_listed"],
                    "cost_hint": 0.8,
                },
                {
                    "id": "act-004",
                    "action": "select_minimum_path",
                    "params": {"goal": "Deliver a minimal credible plan", "preference": "credibility_first"},
                    "preconditions": ["options_listed"],
                    "effects": ["plan_candidate"],
                    "cost_hint": 0.35,
                },
                {
                    "id": "act-005",
                    "action": "finalize_report",
                    "params": {"goal": "Deliver a minimal credible plan"},
                    "preconditions": ["plan_candidate"],
                    "effects": ["report_ready"],
                    "cost_hint": 0.15,
                },
            ],
            "meta": {"truncated": False, "time_capped": False, "tier": "mobile"},
        }

        self.assertEqual(first_plan, expected)
        self.assertEqual(second_plan, expected)

    def test_resource_tier_allows_heavier_actions_on_server(self) -> None:
        plan = make_plan("Calibrate heavy pipeline", AdaadConfig(resource_tier=ResourceTier.SERVER)).to_dict()

        self.assertEqual(plan["meta"], {"truncated": False, "time_capped": False, "tier": "server"})
        self.assertEqual(len(plan["steps"]), 6)
        self.assertEqual(plan["steps"][2]["action"], "survey_context")
        self.assertEqual(plan["steps"][2]["id"], "act-003")

    def test_limits_apply_deterministically(self) -> None:
        capped = make_plan("Trim plan", AdaadConfig(planner_max_steps=2)).to_dict()
        self.assertTrue(capped["meta"]["truncated"])
        self.assertFalse(capped["meta"]["time_capped"])
        self.assertEqual([step["id"] for step in capped["steps"]], ["act-001", "act-002"])

        def fake_now_generator():
            timeline = iter([0.0, 0.008, 0.016, 0.024])

            def _next():
                try:
                    return next(timeline)
                except StopIteration:
                    return 0.024

            return _next

        with patch("adaad6.planning.planner._now", new=fake_now_generator()):
            timed = make_plan("Time boxed", AdaadConfig(planner_max_seconds=0.01))
        timed_dict = timed.to_dict()
        self.assertTrue(timed_dict["meta"]["time_capped"])
        self.assertFalse(timed_dict["meta"]["truncated"])
        self.assertEqual(len(timed_dict["steps"]), 1)


if __name__ == "__main__":
    unittest.main()
