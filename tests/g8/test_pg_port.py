from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g8-human-operations"))

from domain import AuthoritySnapshot
from pg_port import PgHumanOperationsGateway


class Cursor:
    def __init__(self,owner): self.owner=owner
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def execute(self,statement,params): self.owner.calls.append((statement,params))
    def fetchone(self): return (self.owner.result,)


class Connection:
    def __init__(self,result): self.result=result; self.calls=[]
    def cursor(self): return Cursor(self)


class PgPortTests(unittest.TestCase):
    def test_only_guarded_capability_is_called(self):
        conn=Connection({"acknowledgement_id":"ack-a","duplicate":False})
        gateway=PgHumanOperationsGateway(conn)
        authority=AuthoritySnapshot("tenant-a","actor-a",True,"human-operations:ack","r1")
        value=gateway.acknowledge_alert(
            authority=authority,tenant_id="tenant-a",alert_id="alert-a",
            actor_principal_id="actor-a",logical_action_id="op-a",note=None,
        )
        self.assertEqual(value["acknowledgement_id"],"ack-a")
        self.assertEqual(
            conn.calls[-1][0],
            "SELECT human_operations.g8_acknowledge_alert(%s,%s,%s,%s,%s,%s::jsonb)",
        )


if __name__=="__main__":
    unittest.main()
