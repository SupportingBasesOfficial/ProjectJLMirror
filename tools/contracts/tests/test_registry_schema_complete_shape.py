from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.contracts.core import validate_registry_schema_contract


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "contracts" / "catalog" / "source-registry.schema.json"


def _findings_after(mutator):
    baseline = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    broken = deepcopy(baseline)
    mutator(broken)
    with TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "contracts" / "catalog" / "source-registry.schema.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(broken), encoding="utf-8")
        return validate_registry_schema_contract(root)


class RegistrySchemaCompleteShapeTests(unittest.TestCase):
    def test_unmodeled_top_level_constraint_is_rejected(self):
        findings = _findings_after(lambda schema: schema.__setitem__("not", {}))
        self.assertTrue(
            any("unmodeled constraint" in finding for finding in findings), findings
        )

    def test_unmodeled_nested_constraint_is_rejected(self):
        findings = _findings_after(
            lambda schema: schema["$defs"]["pinned_source"].__setitem__("not", {})
        )
        self.assertTrue(
            any("unmodeled constraint" in finding for finding in findings), findings
        )


if __name__ == "__main__":
    unittest.main()
