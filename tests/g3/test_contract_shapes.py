from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def schema(self, name: str) -> dict:
        return json.loads((ROOT / "contracts/g3-resource-inventory" / name).read_text(encoding="utf-8"))

    def test_list_contract_is_closed_and_current_only(self):
        schema = self.schema("resource-list.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["generation_state"]["const"], "active_generation")
        item = schema["$defs"]["resource"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(item["properties"]["resource_kind"]["const"], "host")
        self.assertNotIn("external_references", item["properties"])

    def test_detail_contract_keeps_provider_reference_bounded(self):
        schema = self.schema("resource-detail.schema.json")
        self.assertFalse(schema["additionalProperties"])
        refs = schema["properties"]["external_references"]
        self.assertFalse(refs["additionalProperties"])
        self.assertEqual(refs["properties"]["provider_object_kind"]["const"], "zabbix_host")
        self.assertEqual(refs["properties"]["provider_external_ref"]["maxLength"], 256)


if __name__ == "__main__":
    unittest.main()
