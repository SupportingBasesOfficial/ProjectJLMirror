from __future__ import annotations

import json,re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from domain import AuthoritySnapshot
from read_ui import AuthContext,alert_incidents_api,incident_api,render_incident
from service import IncidentService

ALERT_INCIDENTS_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/incidents$")
INCIDENT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/incidents/([^/]+)$")
INCIDENT_TRANSITION_RE=re.compile(r"^/api/v1/tenants/([^/]+)/incidents/([^/]+)/transition$")
INCIDENT_ASSIGN_RE=re.compile(r"^/api/v1/tenants/([^/]+)/incidents/([^/]+)/assignment$")
INCIDENT_COMMENT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/incidents/([^/]+)/comments$")
UI_INCIDENT_RE=re.compile(r"^/tenants/([^/]+)/incidents/([^/]+)$")


def _auth(handler:BaseHTTPRequestHandler,tenant_id:str)->AuthContext:
    supplied=handler.headers.get("X-Tenant-Id","")
    principal=handler.headers.get("X-Principal-Id","")
    scopes=frozenset(x for x in handler.headers.get("X-Scopes","").split() if x)
    if supplied!=tenant_id:
        raise PermissionError("tenant mismatch")
    return AuthContext(supplied,principal,scopes)


def make_handler(port,authority_provider):
    service=IncidentService(port)
    class Handler(BaseHTTPRequestHandler):
        max_body=16384
        def log_message(self,format,*args): return
        def _send(self,status,content_type,payload):
            self.send_response(status);self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(payload)));self.send_header("Cache-Control","no-store")
            self.end_headers();self.wfile.write(payload)
        def _json(self,status,value):
            self._send(status,"application/json",json.dumps(value,separators=(",",":")).encode())
        def _body(self):
            length=int(self.headers.get("Content-Length","0"))
            if length<0 or length>self.max_body: raise ValueError("body size")
            value=json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value,dict): raise ValueError("object required")
            return value
        def do_GET(self):
            path=urlsplit(self.path).path
            try:
                m=INCIDENT_RE.fullmatch(path)
                if m:
                    tenant,iid=m.groups();self._json(200,incident_api(port,_auth(self,tenant),iid));return
                m=ALERT_INCIDENTS_RE.fullmatch(path)
                if m:
                    tenant,aid=m.groups();self._json(200,alert_incidents_api(port,_auth(self,tenant),aid));return
                m=UI_INCIDENT_RE.fullmatch(path)
                if m:
                    tenant,iid=m.groups();self._send(200,"text/html; charset=utf-8",render_incident(port,_auth(self,tenant),iid).encode());return
                self._json(404,{"error":"not_found"})
            except PermissionError:self._json(403,{"error":"forbidden"})
            except KeyError:self._json(404,{"error":"not_found"})
        def do_POST(self):
            path=urlsplit(self.path).path
            try:
                auth_scope="itsm:write"; body=self._body()
                m=ALERT_INCIDENTS_RE.fullmatch(path)
                if m:
                    tenant,aid=m.groups();auth=_auth(self,tenant)
                    if auth_scope not in auth.scopes: raise PermissionError(auth_scope)
                    a=authority_provider(auth,auth_scope)
                    self._json(200,service.create(
                        authority=a,tenant_id=tenant,alert_id=aid,title=str(body["title"]),
                        description=body.get("description"),actor_principal_id=auth.principal_id,
                        logical_action_id=str(body["logical_action_id"])
                    ));return
                for regex,kind in ((INCIDENT_TRANSITION_RE,"transition"),(INCIDENT_ASSIGN_RE,"assign"),(INCIDENT_COMMENT_RE,"comment")):
                    m=regex.fullmatch(path)
                    if not m: continue
                    tenant,iid=m.groups();auth=_auth(self,tenant)
                    if auth_scope not in auth.scopes: raise PermissionError(auth_scope)
                    a=authority_provider(auth,auth_scope)
                    if kind=="transition":
                        value=service.transition(authority=a,tenant_id=tenant,incident_id=iid,target_state=str(body["target_state"]),actor_principal_id=auth.principal_id,logical_action_id=str(body["logical_action_id"]))
                    elif kind=="assign":
                        value=service.assign(authority=a,tenant_id=tenant,incident_id=iid,assignee_principal_id=str(body["assignee_principal_id"]),actor_principal_id=auth.principal_id,logical_action_id=str(body["logical_action_id"]))
                    else:
                        value=service.comment(authority=a,tenant_id=tenant,incident_id=iid,body=str(body["body"]),actor_principal_id=auth.principal_id,logical_action_id=str(body["logical_action_id"]))
                    self._json(200,value);return
                self._json(404,{"error":"not_found"})
            except PermissionError:self._json(403,{"error":"forbidden"})
            except (KeyError,TypeError,ValueError,json.JSONDecodeError):self._json(400,{"error":"invalid_request"})
    return Handler
