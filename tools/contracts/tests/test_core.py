import unittest

from tools.contracts.core import (
    CompositeRequirement,
    ContractProjectionError,
    compare_object_schemas,
    extract_manifest_requirements,
    extract_versioned_ids,
    git_blob_sha,
)


class ContractProjectionTests(unittest.TestCase):
    def test_extract_versioned_ids_is_unique_and_sorted(self):
        text = "`runtime.api@1` runtime.api@1 `worker.async-consumer@1`"
        self.assertEqual(
            extract_versioned_ids(text),
            ("runtime.api@1", "worker.async-consumer@1"),
        )

    def test_git_blob_sha_matches_git_object_encoding(self):
        self.assertEqual(
            git_blob_sha(b"test\n"),
            "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
        )

    def test_manifest_composite_is_explicitly_registered(self):
        text = """# X

## Semantic manifest

```text
contract_name
allowed_consumer_contracts or discovery policy
data_classification
```

## Next
"""
        composite = CompositeRequirement(
            "allowed_consumer_contracts or discovery policy",
            ("allowed_consumer_contracts", "discovery_policy"),
        )
        req = extract_manifest_requirements(
            text, "Semantic manifest", (composite,)
        )
        self.assertEqual(req.fields, ("contract_name", "data_classification"))
        self.assertEqual(req.composite_requirements, (composite,))

    def test_unregistered_non_machine_requirement_fails_closed(self):
        text = """## Semantic manifest
```text
contract_name
unexpected prose requirement
```
"""
        with self.assertRaises(ContractProjectionError):
            extract_manifest_requirements(text, "Semantic manifest")

    def test_registered_composite_missing_from_source_fails_closed(self):
        text = """## Semantic manifest
```text
contract_name
```
"""
        composite = CompositeRequirement("a or b", ("a", "b"))
        with self.assertRaises(ContractProjectionError):
            extract_manifest_requirements(text, "Semantic manifest", (composite,))

    def test_missing_heading_fails_closed(self):
        with self.assertRaises(ContractProjectionError):
            extract_manifest_requirements("# no", "Endpoint contract manifest")

    def test_structural_change_detects_removed_new_required_and_relaxation(self):
        previous = {
            "properties": {"a": {"type": "string"}, "b": {}},
            "required": ["a", "b"],
        }
        candidate = {
            "properties": {"a": {"type": "integer"}, "c": {}},
            "required": ["a", "c"],
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(
            report["classification"], "structural_change_requires_review"
        )
        self.assertEqual(report["removed_properties"], ["b"])
        self.assertEqual(report["added_required_properties"], ["c"])
        self.assertEqual(report["relaxed_required_properties"], ["b"])
        self.assertEqual(report["changed_property_definitions"], ["a"])

    def test_optional_addition_is_only_an_additive_candidate(self):
        previous = {"properties": {"a": {}}, "required": ["a"], "allOf": []}
        candidate = {
            "properties": {"a": {}, "b": {}},
            "required": ["a"],
            "allOf": [],
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(
            report["classification"], "structurally_additive_candidate"
        )
        self.assertIn(
            "cannot approve compatibility",
            report["semantic_compatibility_authority"],
        )

    def test_composite_change_requires_review(self):
        previous = {"properties": {"a": {}}, "required": [], "allOf": []}
        candidate = {
            "properties": {"a": {}},
            "required": [],
            "allOf": [{"anyOf": [{"required": ["a"]}]}],
        }
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(
            report["classification"], "structural_change_requires_review"
        )
        self.assertTrue(report["composite_requirements_changed"])


if __name__ == "__main__":
    unittest.main()
