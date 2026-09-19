from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from domain import AuthoritySnapshot
from http_app import make_handler


class FakePort:
    def __init__(self):
        self.items={}

    def create_intent(self,**kwargs):
        iid="intent-"+kwargs["logical_action_id"]
        self.items[iid]={
            "notification_intent_id":iid,
            "alert_id":kwargs["alert_id"],
            "recipient_principal_id":kwargs["recipient_principal_id"],
            "destination_ref":kwargs["destination_ref"],
            "channel_class":kwargs["channel_class"],
            "reason":kwargs["reason"],
            "payload_ref":kwargs["payload_ref"],
            "payload_hash":kwargs["payload_hash"],
            "projection":{
                "delivery_state":"unknown",
                "external_read_observed":False,
                "native_visibility_state":"not_linked",
                "fallback_action_required":False,
            },
            "attempts":[],
            "provider_evidence":[],
        }
        return {"notification_intent_id":iid,"duplicate":False}

    def get_intent(self,tenant_id,intent_id):
        if intent_id not in self.items: raise KeyError(intent_id)
        return self.items[intent_id]

    def list_alert_intents(self,tenant_id,alert_id):
        return [v for v in self.items.values() if v["alert_id"]==alert_id]


class HttpE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port=FakePort()

        def authority_provider(auth,action):
            return AuthoritySnapshot(
                auth.tenant_id,auth.principal_id,True,action,"policy-r1"
            )

        cls.server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(cls.port,authority_provider))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self,path,*,method="GET",tenant="tenant-a",principal="actor-a",scopes="notification:read",body=None):
        payload=None if body is None else json.dumps(body).encode()
        req=Request(
            self.base+path,data=payload,method=method,
            headers={
                "Content-Type":"application/json",
                "X-Tenant-Id":tenant,
                "X-Principal-Id":principal,
                "X-Scopes":scopes,
            },
        )
        with urlopen(req,timeout=2) as response:
            return response.status,response.headers.get_content_type(),response.read()

    def test_create_then_read(self):
        status,_,body=self.request(
            "/api/v1/tenants/tenant-a/alerts/alert-a/notifications",
            method="POST",scopes="notification:write",
            body={
                "recipient_principal_id":"customer-a",
                "destination_ref":"dest-a",
                "reason":"alert_requires_attention",
                "payload_ref":"template-a",
                "payload_hash":"hash-a",
                "logical_action_id":"op-a",
            },
        )
        self.assertEqual(status,200)
        iid=json.loads(body)["notification_intent_id"]
        status,_,body=self.request(
            f"/api/v1/tenants/tenant-a/notifications/{iid}",
            scopes="notification:read",
        )
        self.assertEqual(status,200)
        item=json.loads(body)
        self.assertEqual(item["projection"]["delivery_state"],"unknown")

    def test_tenant_and_scope_fail_closed(self):
        with self.assertRaises(HTTPError) as caught:
            self.request(
                "/api/v1/tenants/tenant-b/alerts/alert-a/notifications",
                method="POST",tenant="tenant-a",scopes="notification:write",
                body={
                    "destination_ref":"dest-a","reason":"alert_requires_attention",
                    "payload_ref":"template-a","payload_hash":"hash-a",
                    "logical_action_id":"op-b",
                },
            )
        self.assertEqual(caught.exception.code,403)

        with self.assertRaises(HTTPError) as caught:
            self.request(
                "/api/v1/tenants/tenant-a/alerts/alert-a/notifications",
                method="POST",scopes="notification:read",
                body={
                    "destination_ref":"dest-a","reason":"alert_requires_attention",
                    "payload_ref":"template-a","payload_hash":"hash-a",
                    "logical_action_id":"op-c",
                },
            )
        self.assertEqual(caught.exception.code,403)


if __name__=="__main__":
    unittest.main()
