from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from domain import AuthoritySnapshot
from pg_port import PgNotificationGateway


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
    def test_create_intent_uses_guarded_capability(self):
        conn=Connection({"notification_intent_id":"intent-a","duplicate":False})
        gateway=PgNotificationGateway(conn)
        auth=AuthoritySnapshot("tenant-a","actor-a",True,"notification:write","policy-r1")
        value=gateway.create_intent(
            authority=auth,tenant_id="tenant-a",alert_id="alert-a",
            recipient_principal_id="customer-a",destination_ref="dest-ref-a",
            channel_class="whatsapp_business@1",reason="alert_requires_attention",
            payload_ref="template-a",payload_hash="hash-a",
            visibility_requirement_id=None,actor_principal_id="actor-a",
            logical_action_id="op-a",
        )
        self.assertEqual(value["notification_intent_id"],"intent-a")
        self.assertTrue(conn.calls[-1][0].startswith("SELECT notification.g9_create_intent("))


if __name__=="__main__":
    unittest.main()
