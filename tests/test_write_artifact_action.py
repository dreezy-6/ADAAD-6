import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from adaad6.config import AdaadConfig
from adaad6.planning.actions import write_artifact


class WriteArtifactActionTest(unittest.TestCase):
    def test_write_artifact_writes_file_and_postchecks(self) -> None:
        with TemporaryDirectory() as td:
            destination = Path("out") / "artifact.txt"
            cfg = AdaadConfig(home=td)
            validated = write_artifact.validate(
                {"destination": str(destination), "content": "hello artifact", "content_type": "text/plain"},
                cfg,
            )
            result = write_artifact.run(validated)
            checked = write_artifact.postcheck(result, cfg)
            materialized = Path(td) / destination
            self.assertEqual("hello artifact", materialized.read_text(encoding="utf-8"))
            self.assertEqual(materialized.stat().st_size, checked["bytes"])

    def test_write_artifact_rejects_absolute_destination(self) -> None:
        with TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                write_artifact.validate(
                    {"destination": str(Path(td) / "abs.txt"), "content": "x"},
                    AdaadConfig(home=td),
                )

    def test_write_artifact_rejects_parent_traversal(self) -> None:
        with TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                write_artifact.validate(
                    {"destination": "../escape.txt", "content": "x"},
                    AdaadConfig(home=td),
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
