import unittest

from adaad6.planning.templates import compose_diff_report_template, compose_doctor_report_template


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

    def test_compose_diff_report_template_has_expected_flow(self) -> None:
        plan = compose_diff_report_template(base_ref="origin/main", destination="changes.md").to_dict()

        self.assertEqual("diff_report", plan["goal"])
        self.assertEqual(
            {
                "template": "diff_report",
                "destination": "changes.md",
                "base_ref": "origin/main",
                "ledger": "record execution to ledger",
            },
            plan["meta"],
        )
        self.assertEqual(
            ["scan_repo_tree", "git_diff_snapshot", "format_changelog", "write_report"],
            [step["action"] for step in plan["steps"]],
        )
        scan, diff, format_step, write = plan["steps"]
        self.assertEqual([], scan["preconditions"])
        self.assertEqual(["repo_scanned"], scan["effects"])
        self.assertEqual(["repo_scanned"], diff["preconditions"])
        self.assertEqual(["diff_snapshot"], diff["effects"])
        self.assertEqual(["diff_snapshot"], format_step["preconditions"])
        self.assertEqual(["changelog_ready"], format_step["effects"])
        self.assertEqual(["changelog_ready"], write["preconditions"])
        self.assertEqual(["report_written"], write["effects"])
        self.assertEqual("changes.md", write["params"]["destination"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
