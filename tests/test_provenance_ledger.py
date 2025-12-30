import unittest

from adaad6.config import AdaadConfig
from adaad6.provenance import ensure_ledger


class ProvenanceLedgerTest(unittest.TestCase):
    def test_ensure_ledger_disabled_raises(self) -> None:
        cfg = AdaadConfig(ledger_enabled=False)
        with self.assertRaises(RuntimeError):
            ensure_ledger(cfg)


if __name__ == "__main__":
    unittest.main()
