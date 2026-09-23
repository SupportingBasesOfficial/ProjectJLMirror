from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g10-itsm"))
from domain import AuthoritySnapshot,require_transition,require_comment

class Tests(unittest.TestCase):
    def test_authority(self):
        a=AuthoritySnapshot("t","p",True,"itsm:write","r1")
        a.validate(tenant_id="t",actor_principal_id="p")
        with self.assertRaises(PermissionError):
            AuthoritySnapshot("t","p",False,"x","r").validate(tenant_id="t",actor_principal_id="p")
    def test_transition_graph_and_comment_bound(self):
        require_transition("open","in_progress");require_transition("open","resolved")
        require_transition("in_progress","resolved");require_transition("resolved","closed")
        with self.assertRaises(ValueError):require_transition("resolved","in_progress")
        require_comment("ok")
        with self.assertRaises(ValueError):require_comment("")
if __name__=="__main__":unittest.main()
