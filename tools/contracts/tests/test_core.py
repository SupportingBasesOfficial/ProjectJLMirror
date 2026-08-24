import unittest

from tools.contracts.core import (
    ContractProjectionError,
    compare_object_schemas,
    extract_manifest_requirements,
    extract_versioned_ids,
)


class ContractProjectionTests(unittest.TestCase):
    def test_extract_versioned_ids_is_unique_and_sorted(self):
        text = "`runtime.api@1` runtime.api@1 `worker.async-consumer@1`"
        self.assertEqual(
            extract_versioned_ids(text),
            ("runtime.api@1", "worker.async-consumer@1"),
        )

    def test_manifest_fields_preserve_composite_without_guessing(self):
        text = """# X

## Semantic manifest

```text
contract_name
allowed_consumer_contracts or discovery policy
data_classification
```

## Next
"""
        req = extract_manifest_requirements(text, "Semantic manifest")
        self.assertEqual(req.fields, ("contract_name", "data_classification"))
        self.assertEqual(
            req.composite_requirements,
            ("allowed_consumer_contracts or discovery policy",),
        )

    def test_missing_heading_fails_closed(self):
        with self.assertRaises(ContractProjectionError):
            extract_manifest_requirements("# no", "Endpoint contract manifest")

    def test_structural_compatibility_detects_removed_and_new_required(self):
        previous = {"properties": {"a": {}, "b": {}}, "required": ["a"]}
        candidate = {"properties": {"a": {}, "c": {}}, "required": ["a", "c"]}
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structurally_breaking")
        self.assertEqual(report["removed_properties"], ["b"])
        self.assertEqual(report["added_required_properties"], ["c"])

    def test_optional_addition_is_structurally_non_breaking_only(self):
        previous = {"properties": {"a": {}}, "required": ["a"]}
        candidate = {"properties": {"a": {}, "b": {}}, "required": ["a"]}
        report = compare_object_schemas(previous, candidate)
        self.assertEqual(report["classification"], "structurally_non_breaking")
        self.assertIn(
            "semantic compatibility",
            report["semantic_compatibility_authority"],
        )


if __name__ == "__main__":
    unittest.main()
