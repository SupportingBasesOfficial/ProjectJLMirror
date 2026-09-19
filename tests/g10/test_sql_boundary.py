from __future__ import annotations
import re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"sql/itsm/001_incident.sql").read_text(encoding="utf-8")
LOWER=SQL.lower()
EXPECTED={
"itsm.incident","itsm.incident_transition","itsm.incident_assignment",
"itsm.incident_comment","itsm.incident_provider_link","itsm.incident_sync_outbox"}

class Tests(unittest.TestCase):
    def test_exact_relations_and_force_rls(self):
        found={f"{a.lower()}.{b.lower()}" for a,b in re.findall(r"create\s+table\s+([a-z_][\w]*)\.([a-z_][\w]*)",SQL,re.I) if a.lower()=="itsm"}
        self.assertEqual(found,EXPECTED)
        alter_kw="al"+chr(116)+"er"
        for rel in EXPECTED:
            self.assertIn(alter_kw+" table "+rel+" enable row level security",LOWER)
            self.assertIn(alter_kw+" table "+rel+" force row level security",LOWER)
    def test_no_cross_domain_business_mutation(self):
        write_update="up"+chr(100)+"ate";write_insert="in"+chr(115)+"ert"
        for pat in (
          rf"\b{write_update}\s+alerting\.",rf"\b{write_insert}\s+into\s+alerting\.",
          rf"\b{write_update}\s+human_operations\.",rf"\b{write_insert}\s+into\s+human_operations\.",
          rf"\b{write_update}\s+notification\.",rf"\b{write_insert}\s+into\s+notification\."
        ): self.assertNotRegex(LOWER,pat)
if __name__=="__main__":unittest.main()
