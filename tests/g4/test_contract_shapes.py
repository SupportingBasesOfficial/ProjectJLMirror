from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def schema(self, name: str) -> dict:
        return json.loads((ROOT / "contracts/g4-metrics" / name).read_text(encoding="utf-8"))

    def test_definition_list_is_closed_and_metadata_only(self):
        schema = self.schema("metric-definitions.schema.json")
        self.assertFalse(schema["additionalProperties"])
        item = schema["$defs"]["item"]
        self.assertFalse(item["additionalProperties"])
        self.assertNotIn("value", item["properties"])
        self.assertNotIn("external_references", item["properties"])

    def test_current_contract_preserves_null_value(self):
        schema = self.schema("metric-current.schema.json")
        item = schema["$defs"]["item"]
        self.assertIn("value", item["properties"])
        self.assertIn("incomplete", item["properties"]["evidence_state"]["enum"])

    def test_history_contract_is_single_metric_and_bounded(self):
        schema = self.schema("metric-history.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["items"]["maxItems"], 500)
        states = schema["properties"]["completeness"]["properties"]["state"]["enum"]
        self.assertEqual(
            states,
            ["complete", "incomplete", "gap_detected", "reconciliation_required"],
        )


if __name__ == "__main__":
    unittest.main()
