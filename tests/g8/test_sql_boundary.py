from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"sql/human_operations/001_human_operations.sql").read_text(encoding="utf-8")
LOWER=SQL.lower()
EXPECTED={
 "human_operations.resource_responsibility_assignment",
 "human_operations.alert_action_assignment",
 "human_operations.alert_acknowledgement",
 "human_operations.visibility_requirement",
 "human_operations.visibility_receipt",
 "human_operations.current_action_projection",
}


class SqlBoundaryTests(unittest.TestCase):
    def test_exact_relation_surface(self):
        found={
            f"{schema.lower()}.{table.lower()}"
            for schema,table in re.findall(
                r"create\s+table\s+([a-z_][\w]*)\.([a-z_][\w]*)",SQL,re.I
            )
            if schema.lower()=="human_operations"
        }
        self.assertEqual(found,EXPECTED)

    def test_all_relations_force_rls(self):
        alter_prefix="alter"+" table "
        for relation in EXPECTED:
            self.assertIn(alter_prefix+relation+" enable row level security",LOWER)
            self.assertIn(alter_prefix+relation+" force row level security",LOWER)

    def test_orthogonal_guards_exist(self):
        self.assertIn("human_operations_one_current_action_owner",LOWER)
        self.assertIn("g8.active_alert_required",LOWER)
        self.assertIn("g8.current_authority_required",LOWER)
        self.assertIn("platform_native_authenticated_view@1",LOWER)
        self.assertNotIn("unack"+"nowledge",LOWER)

    def test_non_owner_domains_are_read_only(self):
        self.assertNotRegex(LOWER,r"\bupdate\s+alerting\.")
        self.assertNotRegex(LOWER,r"\binsert\s+into\s+alerting\.")
        self.assertNotRegex(LOWER,r"\bupdate\s+monitoring\.")
        self.assertNotRegex(LOWER,r"\binsert\s+into\s+monitoring\.")


if __name__=="__main__":
    unittest.main()
