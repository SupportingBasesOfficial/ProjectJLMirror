from __future__ import annotations

import json,sys,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g10-itsm"))

from domain import AuthoritySnapshot
from http_app import make_handler


class FakePort:
    def __init__(self): self.items={}
    def create_incident(self,**k):
        iid="incident-"+k["logical_action_id"]
        self.items[iid]={"incident_id":iid,"alert_id":k["alert_id"],"title":k["title"],
                         "description":k["description"],"lifecycle_state":"open",
                         "assignments":[],"comments":[],"provider_sync":{"sync_state":"pending"}}
        return {"incident_id":iid,"duplicate":False}
    def transition_incident(self,**k):
        self.items[k["incident_id"]]["lifecycle_state"]=k["target_state"]
        return {"incident_id":k["incident_id"],"state":k["target_state"],"duplicate":False}
    def assign_incident(self,**k):
        self.items[k["incident_id"]]["assignments"].append({"assignee_principal_id":k["assignee_principal_id"]})
        return {"incident_assignment_id":"assignment-1","duplicate":False}
    def add_comment(self,**k):
        self.items[k["incident_id"]]["comments"].append({"body":k["body"]})
        return {"incident_comment_id":"comment-1","duplicate":False}
    def get_incident(self,tenant_id,incident_id):
        if incident_id not in self.items: raise KeyError(incident_id)
        return self.items[incident_id]
    def list_alert_incidents(self,tenant_id,alert_id):
        return [x for x in self.items.values() if x["alert_id"]==alert_id]


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port=FakePort()
        def auth_provider(auth,action):
            return AuthoritySnapshot(auth.tenant_id,auth.principal_id,True,action,"policy-r1")
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(cls.port,auth_provider))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)

    def request(self,path,*,method="GET",tenant="tenant-a",scopes="itsm:read",body=None):
        data=None if body is None else json.dumps(body).encode()
        req=Request(self.base+path,data=data,method=method,headers={
            "Content-Type":"application/json","X-Tenant-Id":tenant,
            "X-Principal-Id":"actor-a","X-Scopes":scopes,
        })
        with urlopen(req,timeout=2) as r:return r.status,json.loads(r.read()) if "json" in r.headers.get_content_type() else r.read()

    def test_create_read_transition_assignment_comment(self):
        status,value=self.request("/api/v1/tenants/tenant-a/alerts/alert-a/incidents",
          method="POST",scopes="itsm:write",body={"title":"Incident A","logical_action_id":"op-a"})
        self.assertEqual(status,200);iid=value["incident_id"]
        self.assertNotEqual(iid,"alert-a")
        self.request(f"/api/v1/tenants/tenant-a/incidents/{iid}/assignment",
          method="POST",scopes="itsm:write",body={"assignee_principal_id":"principal-a","logical_action_id":"assign-a"})
        self.request(f"/api/v1/tenants/tenant-a/incidents/{iid}/comments",
          method="POST",scopes="itsm:write",body={"body":"hello","logical_action_id":"comment-a"})
        self.request(f"/api/v1/tenants/tenant-a/incidents/{iid}/transition",
          method="POST",scopes="itsm:write",body={"target_state":"in_progress","logical_action_id":"transition-a"})
        status,item=self.request(f"/api/v1/tenants/tenant-a/incidents/{iid}")
        self.assertEqual(status,200);self.assertEqual(item["lifecycle_state"],"in_progress")

    def test_tenant_and_scope_fail_closed(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/v1/tenants/tenant-b/alerts/alert-a/incidents",
              method="POST",tenant="tenant-a",scopes="itsm:write",
              body={"title":"x","logical_action_id":"op-b"})
        self.assertEqual(caught.exception.code,403)
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/v1/tenants/tenant-a/alerts/alert-a/incidents",
              method="POST",scopes="itsm:read",
              body={"title":"x","logical_action_id":"op-c"})
        self.assertEqual(caught.exception.code,403)

if __name__=="__main__":unittest.main()
