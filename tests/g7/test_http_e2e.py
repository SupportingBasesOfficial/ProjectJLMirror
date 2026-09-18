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
sys.path.insert(0,str(ROOT/"apps/g7-alert-policy-lifecycle"))

from http_app import make_handler


class FakeRead:
    def list_alerts(self,tenant_id,limit):
        rows={
            "tenant-a":[{
                "alert_id":"alert-a","lifecycle_state":"active",
                "source_kind":"monitoring_problem","source_subject_id":"problem-a",
                "policy_id":"policy-a","policy_version":1,
            }],
            "tenant-b":[{
                "alert_id":"alert-b","lifecycle_state":"active",
                "source_kind":"monitoring_health_projection","source_subject_id":"resource-b",
                "policy_id":"policy-b","policy_version":1,
            }],
        }
        return rows.get(tenant_id,[])[:limit]

    def get_alert(self,tenant_id,alert_id):
        for row in self.list_alerts(tenant_id,100):
            if row["alert_id"]==alert_id:
                return {
                    **row,
                    "transitions":[{
                        "to_lifecycle_state":"active",
                        "occurred_at":"2026-09-18T12:00:00Z",
                    }],
                }
        return None


class HttpE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(FakeRead()))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self,path,*,tenant="tenant-a",subject="user-a",scopes="alerts:read"):
        req=Request(
            self.base+path,
            headers={
                "X-Tenant-Id":tenant,
                "X-Subject-Id":subject,
                "X-Scopes":scopes,
            },
        )
        with urlopen(req,timeout=2) as response:
            return response.status,response.headers.get_content_type(),response.read()

    def test_api_list_and_detail_over_http(self):
        status,kind,body=self.request("/api/v1/tenants/tenant-a/alerts?limit=500")
        self.assertEqual((status,kind),(200,"application/json"))
        payload=json.loads(body)
        self.assertEqual(payload["limit"],100)
        self.assertEqual(payload["items"][0]["alert_id"],"alert-a")

        status,_,body=self.request("/api/v1/tenants/tenant-a/alerts/alert-a")
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["policy_id"],"policy-a")

    def test_html_list_and_detail_are_served_over_http(self):
        status,kind,body=self.request("/tenants/tenant-a/alerts")
        self.assertEqual((status,kind),(200,"text/html"))
        self.assertIn(b"<h1>Alerts</h1>",body)

        status,kind,body=self.request("/tenants/tenant-a/alerts/alert-a")
        self.assertEqual((status,kind),(200,"text/html"))
        self.assertIn(b"Lifecycle: active",body)

    def test_tenant_path_mismatch_is_forbidden(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/v1/tenants/tenant-b/alerts",tenant="tenant-a")
        self.assertEqual(caught.exception.code,403)

    def test_missing_scope_is_forbidden(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/v1/tenants/tenant-a/alerts",scopes="")
        self.assertEqual(caught.exception.code,403)

    def test_cross_tenant_alert_detail_is_not_found(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/v1/tenants/tenant-a/alerts/alert-b")
        self.assertEqual(caught.exception.code,404)


if __name__=="__main__":
    unittest.main()
