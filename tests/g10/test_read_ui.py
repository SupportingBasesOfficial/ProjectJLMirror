from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g10-itsm"))
from read_ui import AuthContext,incident_api,render_incident

class Port:
    def get_incident(self,tenant_id,incident_id):
        return {"incident_id":incident_id,"alert_id":"a1","lifecycle_state":"open",
                "assignments":[],"comments":[],"provider_sync":{"sync_state":"linked"}}
    def list_alert_incidents(self,tenant_id,alert_id): return []

class Tests(unittest.TestCase):
    def test_alert_and_incident_state_are_distinct(self):
        auth=AuthContext("t","p",frozenset({"itsm:read"}))
        v=incident_api(Port(),auth,"i1")
        self.assertEqual(v["incident_id"],"i1");self.assertEqual(v["alert_id"],"a1")
        self.assertIn("Provider sync: linked",render_incident(Port(),auth,"i1"))
if __name__=="__main__":unittest.main()
