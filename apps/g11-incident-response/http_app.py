from __future__ import annotations

import html,json,re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from domain import ApplicationErrorEvent
from service import IncidentResponseService

EVENTS_RE=re.compile(r"^/api/v1/tenants/([^/]+)/application-error-events$")
EVENT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/application-error-events/([^/]+)$")
POLICY_RE=re.compile(r"^/api/v1/tenants/([^/]+)/incident-response-policy$")
UI_RE=re.compile(r"^/tenants/([^/]+)/incident-response$")

SCOPE_PUSH="incident_response:push"
SCOPE_READ="incident_response:read"
SCOPE_WRITE="incident_response:write"


def make_handler(port,authority_provider):
    service=IncidentResponseService(port=port)

    def _auth(handler:BaseHTTPRequestHandler,tenant_id:str)->tuple[str,str,frozenset[str]]:
        supplied=handler.headers.get("X-Tenant-Id","")
        if supplied!=tenant_id: raise PermissionError("tenant mismatch")
        bearer=handler.headers.get("Authorization","")
        if not bearer.startswith("Bearer "): raise PermissionError("bearer required")
        token=bearer[7:]
        principal,scopes=authority_provider(token,tenant_id)
        return supplied,principal,scopes

    class Handler(BaseHTTPRequestHandler):
        max_body=65536
        def log_message(self,format,*args): return
        def _send(self,status,content_type,payload):
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(payload)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(payload)
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
                m=POLICY_RE.fullmatch(path)
                if m:
                    tenant,=m.groups()
                    _,_,scopes=_auth(self,tenant)
                    if SCOPE_READ not in scopes: raise PermissionError(SCOPE_READ)
                    self._json(200,service.get_policy(tenant)); return
                m=EVENT_RE.fullmatch(path)
                if m:
                    tenant,event_id=m.groups()
                    _,_,scopes=_auth(self,tenant)
                    if SCOPE_READ not in scopes: raise PermissionError(SCOPE_READ)
                    self._json(200,service.get_event(tenant,event_id)); return
                m=EVENTS_RE.fullmatch(path)
                if m:
                    tenant,=m.groups()
                    _,_,scopes=_auth(self,tenant)
                    if SCOPE_READ not in scopes: raise PermissionError(SCOPE_READ)
                    self._json(200,{"events":service.list_events(tenant)}); return
                m=UI_RE.fullmatch(path)
                if m:
                    tenant,=m.groups()
                    _auth(self,tenant)
                    self._send(200,"text/html; charset=utf-8",_render_ui(service,tenant).encode()); return
                self._json(404,{"error":"not_found"})
            except PermissionError: self._json(403,{"error":"forbidden"})
            except KeyError: self._json(404,{"error":"not_found"})

        def do_POST(self):
            path=urlsplit(self.path).path
            try:
                body=self._body()
                m=EVENTS_RE.fullmatch(path)
                if m:
                    tenant,=m.groups()
                    _,principal,scopes=_auth(self,tenant)
                    if SCOPE_PUSH not in scopes: raise PermissionError(SCOPE_PUSH)
                    for _f in ("application_id","error_code","error_message","occurred_at"):
                        if not isinstance(body.get(_f),str): raise ValueError(f"{_f} must be a string")
                    event=ApplicationErrorEvent(
                        tenant_id=tenant,
                        application_id=body["application_id"],
                        error_code=body["error_code"],
                        error_message=body["error_message"],
                        occurred_at=body["occurred_at"],
                        source_principal_id=principal,
                        principal_id=body.get("principal_id"),
                        operation=body.get("operation"),
                        session_context=body.get("session_context"),
                        severity_hint=body.get("severity_hint"),
                        raw_payload=body.get("raw_payload") if isinstance(body.get("raw_payload"),dict) else None,
                    )
                    result=service.ingest_event(event)
                    status=202 if result.get("status")=="accepted" else 200
                    self._json(status,result); return
                self._json(404,{"error":"not_found"})
            except PermissionError: self._json(403,{"error":"forbidden"})
            except (KeyError,TypeError,ValueError,json.JSONDecodeError): self._json(422,{"error":"invalid_request"})

        def do_PUT(self):
            path=urlsplit(self.path).path
            try:
                body=self._body()
                m=POLICY_RE.fullmatch(path)
                if m:
                    tenant,=m.groups()
                    _,principal,scopes=_auth(self,tenant)
                    if SCOPE_WRITE not in scopes: raise PermissionError(SCOPE_WRITE)
                    result=service.upsert_policy(tenant,body,principal)
                    self._json(200,result); return
                self._json(404,{"error":"not_found"})
            except PermissionError: self._json(403,{"error":"forbidden"})
            except (KeyError,TypeError,ValueError,json.JSONDecodeError): self._json(422,{"error":"invalid_request"})

    return Handler


def _render_ui(service:IncidentResponseService,tenant_id:str)->str:
    events=service.list_events(tenant_id)
    policy=service.get_policy(tenant_id)
    h=html.escape
    rows="".join(
        f"<tr><td>{h(e.get('event_id','')[:8])}…</td>"
        f"<td>{h(e.get('application_id',''))}</td>"
        f"<td>{h(e.get('error_code',''))}</td>"
        f"<td>{h(e.get('severity_hint') or '—')}</td>"
        f"<td>{h(e.get('occurred_at',''))}</td>"
        f"<td>{h(e.get('status',''))}</td></tr>"
        for e in events
    )
    auto=h(str(policy.get("auto_open_ticket","false")))
    threshold=h(str(policy.get("severity_threshold","HIGH")))
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<title>Incident Response — JLMirror</title></head><body>"
        f"<h1>Incident Response — {h(tenant_id)}</h1>"
        f"<p>Policy: threshold={threshold} auto_open_ticket={auto}</p>"
        "<table border=1><tr><th>ID</th><th>App</th><th>Code</th>"
        "<th>Severity</th><th>Occurred</th><th>Status</th></tr>"
        f"{rows}</table></body></html>"
    )
