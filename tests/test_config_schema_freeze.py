import unittest

from adaad6.config import load_config


class ConfigSchemaFreezeTest(unittest.TestCase):
    def test_schema_mismatch_freezes_even_when_sig_not_required(self) -> None:
        env = {
            "ADAAD6_CONFIG_SCHEMA_VERSION": "0",
            "ADAAD6_CONFIG_SIG_REQUIRED": "false",
        }
        cfg = load_config(env=env)

        self.assertTrue(cfg.emergency_halt)
        self.assertEqual(cfg.freeze_reason, "CONFIG_SCHEMA_VERSION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
