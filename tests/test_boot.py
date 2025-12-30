import unittest

from adaad6.config import AdaadConfig
from adaad6.runtime.boot import boot_sequence


class BootSequenceTest(unittest.TestCase):
    def test_boot_defaults(self) -> None:
        result = boot_sequence(cfg=AdaadConfig())

        self.assertIn("ok", result)
        self.assertIn("mutation_enabled", result)
        self.assertIn("limits", result)
        self.assertIn("checks", result)
        self.assertIn("build", result)

        self.assertFalse(result["mutation_enabled"])
        self.assertEqual(result["limits"]["planner_max_steps"], 25)
        self.assertEqual(result["limits"]["planner_max_seconds"], 2.0)


if __name__ == "__main__":
    unittest.main()
