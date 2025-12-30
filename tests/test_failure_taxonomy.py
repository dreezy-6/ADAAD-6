import unittest

from adaad6.kernel.failures import (
    DETERMINISM_BREACH,
    EVIDENCE_MISSING,
    INTEGRITY_VIOLATION,
    UNLOGGED_EXECUTION,
    KernelCrash,
)


class FailureTaxonomyTest(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertEqual(INTEGRITY_VIOLATION, "CRASH_0x01")
        self.assertEqual(EVIDENCE_MISSING, "CRASH_0x02")
        self.assertEqual(DETERMINISM_BREACH, "CRASH_0x03")
        self.assertEqual(UNLOGGED_EXECUTION, "CRASH_0x04")

    def test_kernel_crash(self) -> None:
        err = KernelCrash(INTEGRITY_VIOLATION, "detail")
        self.assertEqual(err.code, INTEGRITY_VIOLATION)
        self.assertEqual(err.detail, "detail")
        self.assertIn("CRASH_0x01", str(err))


if __name__ == "__main__":
    unittest.main()
