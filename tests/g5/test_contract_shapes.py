from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def schema(self,name):
        return json.loads((ROOT/"contracts/g5-problem-health"/name).read_text(encoding="utf-8"))

    def test_problem_list_contract_is_closed(self):
        schema=self.schema("problems.schema.json")
        self.assertFalse(schema["additionalProperties"])
        item=schema["$defs"]["item"]
        self.assertFalse(item["additionalProperties"])
        self.assertNotIn("provider_acknowledged",item["properties"])
        self.assertNotIn("provider_metadata",item["properties"])

    def test_health_contract_has_only_canonical_classes(self):
        schema=self.schema("health.schema.json")
        classes=schema["$defs"]["item"]["properties"]["health_class"]["enum"]
        self.assertEqual(classes,["unknown","healthy","degraded","unhealthy"])

    def test_health_contract_exposes_evidence_separately_from_class(self):
        schema=self.schema("health.schema.json")
        item=schema["$defs"]["item"]
        self.assertIn("health_class",item["properties"])
        self.assertIn("evidence_state",item["properties"])
        self.assertIn("reconciliation_required",item["properties"]["evidence_state"]["enum"])


if __name__=="__main__":
    unittest.main()
