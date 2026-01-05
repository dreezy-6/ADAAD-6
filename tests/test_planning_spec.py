import math
import unittest

from adaad6.planning.spec import ActionSpec, action_spec_from_dict, validate_action_spec


class PlanningSpecTest(unittest.TestCase):
    def test_validate_normalizes_and_to_dict(self) -> None:
        spec = ActionSpec(
            id="  Foo_bar ",
            action="  do_stuff ",
            params={"x": 1},
            preconditions=(" ready ",),
            effects=(" done ",),
            cost_hint=1.5,
        )

        normalized = validate_action_spec(spec)

        self.assertEqual(normalized.id, "Foo_bar")
        self.assertEqual(normalized.action, "do_stuff")
        self.assertEqual(normalized.preconditions, ("ready",))
        self.assertEqual(normalized.effects, ("done",))
        self.assertEqual(
            normalized.to_dict(),
            {
                "id": "Foo_bar",
                "action": "do_stuff",
                "params": {"x": 1},
                "preconditions": ["ready"],
                "effects": ["done"],
                "cost_hint": 1.5,
            },
        )

    def test_action_spec_from_dict_rejects_invalid_cost_hint(self) -> None:
        for bad_cost in (True, math.inf, math.nan):
            with self.assertRaises(ValueError):
                action_spec_from_dict(
                    {
                        "id": "example",
                        "action": "run",
                        "params": {},
                        "preconditions": [],
                        "effects": [],
                        "cost_hint": bad_cost,
                    }
                )

    def test_action_spec_from_dict_rejects_preconditions_string(self) -> None:
        with self.assertRaises(ValueError):
            action_spec_from_dict({"id": "x", "action": "y", "preconditions": "not-an-iterable"})

    def test_action_spec_from_dict_reports_index_for_empty_entry(self) -> None:
        with self.assertRaisesRegex(ValueError, "preconditions\\[1\\]"):
            action_spec_from_dict({"id": "x", "action": "y", "preconditions": ["ok", " "], "effects": [], "params": {}})

    def test_action_spec_from_dict_rejects_invalid_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "pattern"):
            action_spec_from_dict({"id": "bad/value", "action": "y", "preconditions": [], "effects": []})


if __name__ == "__main__":
    unittest.main()
