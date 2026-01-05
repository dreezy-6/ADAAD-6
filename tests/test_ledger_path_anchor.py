import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.provenance.ledger import ensure_ledger


class LedgerPathAnchorTest(unittest.TestCase):
    def test_relative_ledger_dir_resolves_against_home_not_cwd(self) -> None:
        with TemporaryDirectory() as home_tmp, TemporaryDirectory() as other_tmp:
            cfg = AdaadConfig(
                ledger_enabled=True,
                ledger_dir=".adaad/ledger",
                ledger_filename="events.jsonl",
                home=home_tmp,
            )
            cwd_before = Path.cwd()
            os.chdir(other_tmp)
            try:
                ledger_file = ensure_ledger(cfg)
            finally:
                os.chdir(cwd_before)

            expected_dir = (Path(home_tmp) / ".adaad" / "ledger").resolve()
            self.assertEqual(ledger_file.parent, expected_dir)
            self.assertTrue(ledger_file.exists())


if __name__ == "__main__":
    unittest.main()
