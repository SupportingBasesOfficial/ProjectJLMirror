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
sys.path.insert(0,str(ROOT/"apps/g8-human-operations"))

from domain import AuthoritySnapshot
from http_app import make_handler


class FakePort:
    def __init__(self):
        self.current_owner="principal-owner"
        self.acks=[]
        self.views=[]
        self.responsibilities=[]

    def assign_resource_responsibility(self,**kwargs):
        row={
            "responsibility_assignment_id":"resp-"+kwargs["logical_action_id"],
            "principal_id":kwargs["responsible_principal_id"],
            "responsibility_role":kwargs["responsibility_role"],
        }
        self.responsibilities.append(row)
        return {**row,"duplicate":False}

    def end_resource_responsibility(self,**kwargs):
        return {"responsibility_assignment_id":kwargs["assignment_id"],"duplicate":False}

    def assign_alert_action(self,**kwargs):
        self.current_owner=kwargs["owner_principal_id"]
        return {"action_assignment_id":"action-"+kwargs["logical_action_id"],"duplicate":False}

    def acknowledge_alert(self,**kwargs):
        self.acks.append({"principal_id":kwargs["actor_principal_id"],"acknowledged_at":"2026-09-18T12:00:00Z"})
        return {"acknowledgement_id":"ack-"+kwargs["logical_action_id"],"duplicate":False}

    def create_visibility_requirement(self,**kwargs):
        return {"visibility_requirement_id":"view-required-"+kwargs["logical_action_id"],"duplicate":False}

    def record_visibility_receipt(self,**kwargs):
        self.views.append(kwargs["viewer_principal_id"])
        return {"visibility_receipt_id":"view-receipt-"+kwargs["logical_action_id"],"duplicate":False}

    def alert_human_operations(self,tenant_id,alert_id):
        return {
            "alert_id":alert_id,
            "alert_lifecycle_state":"active",
            "current_action":{"owner_principal_id":self.current_owner,"action_kind":"investigate_alert"},
            "acknowledgements":list(self.acks),
            "visibility":[{"viewer_side":"customer","visibility_state":"viewed" if self.views else "not_viewed_yet"}],
            "timeline":[],
        }

    def resource_responsibilities(self,tenant_id,resource_id):
        return list(self.responsibilities)


class HttpE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port=FakePort()

        def authority_provider(auth,required_action):
            return AuthoritySnapshot(
                tenant_id=auth.tenant_id,
                principal_id=auth.principal_id,
                current=True,
                action=required_action,
                policy_revision="policy-r1",
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

    def request(self,path,*,method="GET",tenant="tenant-a",principal="actor-a",scopes="human-operations:read",body=None):
        payload=None if body is None else json.dumps(body).encode()
        req=Request(
            self.base+path,
            data=payload,
            method=method,
            headers={
                "Content-Type":"application/json",
                "X-Tenant-Id":tenant,
                "X-Principal-Id":principal,
                "X-Scopes":scopes,
            },
        )
        with urlopen(req,timeout=2) as response:
            return response.status,response.headers.get_content_type(),response.read()

    def test_write_then_read_distinct_dimensions(self):
        status,_,body=self.request(
            "/api/v1/tenants/tenant-a/alerts/alert-a/actions",
            method="POST",scopes="human-operations:write",
            body={"owner_principal_id":"owner-b","action_kind":"investigate_alert","logical_action_id":"op-action"},
        )
        self.assertEqual(status,200)
        self.assertIn("action_assignment_id",json.loads(body))

        status,_,body=self.request(
            "/api/v1/tenants/tenant-a/alerts/alert-a/acknowledgements",
            method="POST",principal="ack-c",scopes="human-operations:ack",
            body={"logical_action_id":"op-ack","note":"triaged"},
        )
        self.assertEqual(status,200)

        status,_,body=self.request(
            "/api/v1/tenants/tenant-a/alerts/alert-a/human-operations",
            scopes="human-operations:read",
        )
        item=json.loads(body)
        self.assertEqual(item["current_action"]["owner_principal_id"],"owner-b")
        self.assertEqual(item["acknowledgements"][0]["principal_id"],"ack-c")
        self.assertNotEqual(item["current_action"]["owner_principal_id"],item["acknowledgements"][0]["principal_id"])

    def test_resource_responsibility_and_native_view(self):
        status,_,_=self.request(
            "/api/v1/tenants/tenant-a/resources/resource-a/responsibilities",
            method="POST",scopes="human-operations:write",
            body={
                "responsible_principal_id":"principal-r",
                "responsibility_role":"technical_responsible",
                "assignment_source":"manual",
                "logical_action_id":"op-resp",
            },
        )
        self.assertEqual(status,200)

        status,_,body=self.request(
            "/api/v1/tenants/tenant-a/resources/resource-a/responsibilities",
            scopes="human-operations:read",
        )
        self.assertEqual(json.loads(body)["items"][0]["principal_id"],"principal-r")

        status,_,body=self.request(
            "/api/v1/tenants/tenant-a/alerts/alert-a/visibility-requirements",
            method="POST",scopes="human-operations:write",
            body={
                "viewer_principal_id":"viewer-a",
                "viewer_side":"customer",
                "capability_class":"platform_native_authenticated_view@1",
                "presentation_ref":"alert-a",
                "logical_action_id":"op-view-required",
            },
        )
        requirement=json.loads(body)["visibility_requirement_id"]

        status,_,_=self.request(
            f"/api/v1/tenants/tenant-a/visibility-requirements/{requirement}/receipts",
            method="POST",principal="viewer-a",scopes="human-operations:view",
            body={
                "logical_action_id":"op-view-receipt",
                "session_evidence":{"session_generation":"s1"},
            },
        )
        self.assertEqual(status,200)

    def test_tenant_and_scope_fail_closed(self):
        with self.assertRaises(HTTPError) as caught:
            self.request(
                "/api/v1/tenants/tenant-b/alerts/alert-a/actions",
                method="POST",tenant="tenant-a",scopes="human-operations:write",
                body={"owner_principal_id":"p","action_kind":"review_alert","logical_action_id":"x"},
            )
        self.assertEqual(caught.exception.code,403)

        with self.assertRaises(HTTPError) as caught:
            self.request(
                "/api/v1/tenants/tenant-a/alerts/alert-a/actions",
                method="POST",scopes="human-operations:read",
                body={"owner_principal_id":"p","action_kind":"review_alert","logical_action_id":"x2"},
            )
        self.assertEqual(caught.exception.code,403)


if __name__=="__main__":
    unittest.main()
