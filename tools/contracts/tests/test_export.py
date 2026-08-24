from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.contracts.export_contracts import _resolve_safe_output


class ExportBoundaryTests(unittest.TestCase):
    def test_repository_normative_path_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with self.assertRaises(ValueError):
                _resolve_safe_output(root, Path("docs/generated.json"))

    def test_repository_build_projection_path_is_allowed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            output = _resolve_safe_output(
                root, Path("build/contract-projections/bundle.json")
            )
            self.assertEqual(
                output,
                (root / "build" / "contract-projections" / "bundle.json").resolve(),
            )

    def test_explicit_output_outside_repository_is_allowed(self):
        with TemporaryDirectory() as repo_temp, TemporaryDirectory() as out_temp:
            root = Path(repo_temp).resolve()
            requested = (Path(out_temp) / "bundle.json").resolve()
            self.assertEqual(_resolve_safe_output(root, requested), requested)


if __name__ == "__main__":
    unittest.main()
