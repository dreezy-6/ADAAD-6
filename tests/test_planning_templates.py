import unittest

from adaad6.planning.templates import compose_doctor_report_template


class PlanningTemplatesTest(unittest.TestCase):
    def test_compose_doctor_report_template_has_expected_steps(self) -> None:
        plan = compose_doctor_report_template(destination="custom.txt").to_dict()

        self.assertEqual("doctor_report", plan["goal"])
        self.assertEqual({"template": "doctor_report", "destination": "custom.txt"}, plan["meta"])
        self.assertEqual(
            ["doctor_gate", "summarize_results", "write_report"],
            [step["action"] for step in plan["steps"]],
        )
        first, second, third = plan["steps"]
        self.assertEqual("doctor-gate", first["id"])
        self.assertEqual([], first["preconditions"])
        self.assertEqual(["doctor_passed"], first["effects"])
        self.assertEqual(["doctor_passed"], second["preconditions"])
        self.assertEqual(["summary_ready"], second["effects"])
        self.assertEqual(["summary_ready"], third["preconditions"])
        self.assertEqual(["report_written"], third["effects"])
        self.assertEqual("custom.txt", third["params"]["destination"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
