import unittest

from adaad6.config import AdaadConfig
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
                {"id": "step-1", "action": "clarify_goal", "params": {"goal": "Deliver a minimal credible plan"}},
                {"id": "step-2", "action": "propose_actions", "params": {"goal": "Deliver a minimal credible plan"}},
                {"id": "step-3", "action": "report", "params": {"goal": "Deliver a minimal credible plan"}},
            ],
            "meta": {"truncated": False, "time_capped": False},
        }

        self.assertEqual(first_plan, expected)
        self.assertEqual(second_plan, expected)


if __name__ == "__main__":
    unittest.main()
