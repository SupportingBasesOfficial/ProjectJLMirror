from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def schema(self,name):
        return json.loads((ROOT/"contracts/g6-monitoring-alerting-transport"/name).read_text(encoding="utf-8"))

    def test_envelope_is_closed_and_contract_bounded(self):
        schema=self.schema("envelope.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["contract_name"]["enum"],
            ["monitoring.problem-state.changed","monitoring.health-projection.changed"],
        )
        self.assertEqual(schema["properties"]["message_class"]["const"],"integration_event")
        self.assertEqual(schema["properties"]["producer"]["const"],"Monitoring")

    def test_result_has_no_alert_business_shape(self):
        schema=self.schema("result.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("alert_id",schema["properties"])
        kinds=schema["properties"]["effect_result_kind"]["enum"]
        self.assertIn("monitoring_owner_reread_noncurrent_generation",kinds)


if __name__=="__main__":
    unittest.main()
