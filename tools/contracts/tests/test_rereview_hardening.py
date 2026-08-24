from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.contracts.core import compare_object_schemas, validate_registry_schema_contract


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "contracts" / "catalog" / "source-registry.schema.json"


class ReReviewHardeningTests(unittest.TestCase):
    def test_new_required_name_without_property_forces_review(self):
        previous = {
            "type": "object",
            "properties": {"a": {}},
            "required": ["a"],
        }
        candidate = {
            "type": "object",
            "properties": {"a": {}},
            "required": ["a", "b"],
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structural_change_requires_review")
        self.assertEqual(report["added_required_properties"], ["b"])
        self.assertIn("required_properties_added", report["review_reasons"])

    def test_invalid_required_shape_fails_to_review(self):
        previous = {"properties": {"a": {}}, "required": ["a"]}
        candidate = {"properties": {"a": {}}, "required": ["a", "a"]}
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structural_change_requires_review")
        self.assertIn("required_shape_changed", report["review_reasons"])

    def test_manifest_source_property_refs_are_enforced(self):
        baseline = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for field in ("http_manifest_source", "event_manifest_source"):
            with self.subTest(field=field), TemporaryDirectory() as temp:
                root = Path(temp)
                target = root / "contracts" / "catalog" / "source-registry.schema.json"
                target.parent.mkdir(parents=True)
                broken = deepcopy(baseline)
                broken["properties"][field] = {}
                target.write_text(json.dumps(broken), encoding="utf-8")
                findings = validate_registry_schema_contract(root)
                self.assertTrue(
                    any(field in finding and "manifest_source" in finding for finding in findings),
                    findings,
                )


if __name__ == "__main__":
    unittest.main()
