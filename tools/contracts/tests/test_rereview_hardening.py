from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.contracts.core import compare_object_schemas, validate_registry_schema_contract


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "contracts" / "catalog" / "source-registry.schema.json"


def _schema_findings_after(mutator):
    baseline = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    with TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "contracts" / "catalog" / "source-registry.schema.json"
        target.parent.mkdir(parents=True)
        broken = deepcopy(baseline)
        mutator(broken)
        target.write_text(json.dumps(broken), encoding="utf-8")
        return validate_registry_schema_contract(root)


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

    def test_definition_added_for_previously_required_name_forces_review(self):
        previous = {
            "type": "object",
            "properties": {"a": {}},
            "required": ["a", "b"],
            "additionalProperties": True,
        }
        candidate = {
            "type": "object",
            "properties": {"a": {}, "b": {"type": "string"}},
            "required": ["a", "b"],
            "additionalProperties": True,
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structural_change_requires_review")
        self.assertEqual(report["added_previously_required_properties"], ["b"])
        self.assertIn(
            "definitions_added_for_previously_required_properties",
            report["review_reasons"],
        )

    def test_invalid_required_shape_fails_to_review(self):
        previous = {"properties": {"a": {}}, "required": ["a"]}
        candidate = {"properties": {"a": {}}, "required": ["a", "a"]}
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structural_change_requires_review")
        self.assertIn("required_shape_changed", report["review_reasons"])

    def test_manifest_source_property_refs_are_enforced(self):
        for field in ("http_manifest_source", "event_manifest_source"):
            with self.subTest(field=field):
                findings = _schema_findings_after(
                    lambda schema, field=field: schema["properties"].__setitem__(field, {})
                )
                self.assertTrue(
                    any(field in finding and "manifest_source" in finding for finding in findings),
                    findings,
                )

    def test_registry_schema_structural_type_guards_are_enforced(self):
        cases = (
            ("root type", lambda schema: schema.__setitem__("type", "string")),
            (
                "profile_sources type",
                lambda schema: schema["properties"]["profile_sources"].__setitem__(
                    "type", "object"
                ),
            ),
            (
                "pinned_source type",
                lambda schema: schema["$defs"]["pinned_source"].__setitem__(
                    "type", "string"
                ),
            ),
            (
                "manifest_source type",
                lambda schema: schema["$defs"]["manifest_source"].__setitem__(
                    "type", "string"
                ),
            ),
            (
                "composite_requirement type",
                lambda schema: schema["$defs"]["composite_requirement"].__setitem__(
                    "type", "string"
                ),
            ),
        )
        for label, mutator in cases:
            with self.subTest(case=label):
                self.assertTrue(_schema_findings_after(mutator))

    def test_restrictive_optional_property_definition_forces_review(self):
        previous = {
            "type": "object",
            "properties": {"a": {}},
            "required": ["a"],
            "additionalProperties": True,
        }
        candidate = {
            "type": "object",
            "properties": {"a": {}, "b": {"type": "string"}},
            "required": ["a"],
            "additionalProperties": True,
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structural_change_requires_review")
        self.assertEqual(report["restrictive_added_optional_properties"], ["b"])
        self.assertIn(
            "restrictive_optional_property_definitions_added", report["review_reasons"]
        )

    def test_unconstrained_optional_property_can_remain_additive_candidate(self):
        previous = {
            "type": "object",
            "properties": {"a": {}},
            "required": ["a"],
            "additionalProperties": True,
        }
        candidate = {
            "type": "object",
            "properties": {"a": {}, "b": {}},
            "required": ["a"],
            "additionalProperties": True,
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structurally_additive_candidate")


if __name__ == "__main__":
    unittest.main()
