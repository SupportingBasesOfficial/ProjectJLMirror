from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g10-itsm"))
from worker import ITSMSyncWorker,FixtureNeutralAdapter

class Port:
    def __init__(self): self.completed=[]
    def next_sync_candidate(self,tenant_id):
        return {"sync_outbox_id":"o1","incident_id":"i1","sync_identity":"s1"}
    def claim_sync(self,tenant_id,outbox_id,executor_id,claim_seconds):
        return {"state":"dispatching"}
    def complete_sync(self,*args):
        self.completed.append(args)
        return {"state":args[3]}
    def reconcile_sync(self,*args): return {"reconciled":True}

class Tests(unittest.TestCase):
    def test_provider_link_does_not_mutate_incident_state(self):
        p=Port();w=ITSMSyncWorker(p,FixtureNeutralAdapter("linked"),"w1")
        r=w.sync_next("t")
        self.assertEqual(r["state"],"linked")
        self.assertEqual(p.completed[-1][3],"linked")
    def test_adapter_exception_is_unknown(self):
        class Boom:
            version="fixture-neutral@1"
            def create_or_link(self,*,incident,sync_identity): raise RuntimeError("x")
        p=Port();w=ITSMSyncWorker(p,Boom(),"w1")
        self.assertEqual(w.sync_next("t")["state"],"unknown")
if __name__=="__main__":unittest.main()
