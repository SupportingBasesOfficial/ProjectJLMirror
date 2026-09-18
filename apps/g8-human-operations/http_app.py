from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from domain import AuthoritySnapshot
from read_ui import AuthContext,alert_api,resource_api,render_alert
from service import HumanOperationsService

ALERT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/human-operations$")
RESOURCE_RE=re.compile(r"^/api/v1/tenants/([^/]+)/resources/([^/]+)/responsibilities$")
RESOURCE_END_RE=re.compile(r"^/api/v1/tenants/([^/]+)/resources/([^/]+)/responsibilities/([^/]+)/end$")
ACTION_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/actions$")
ACK_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/acknowledgements$")
VIEW_REQ_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/visibility-requirements$")
VIEW_RECEIPT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/visibility-requirements/([^/]+)/receipts$")
UI_ALERT_RE=re.compile(r"^/tenants/([^/]+)/alerts/([^/]+)/human-operations$")


def _auth(handler:BaseHTTPRequestHandler,tenant_id:str)->AuthContext:
    supplied=handler.headers.get("X-Tenant-Id","")
    principal=handler.headers.get("X-Principal-Id","")
    scopes=frozenset(x for x in handler.headers.get("X-Scopes","").split() if x)
    if supplied!=tenant_id:
        raise PermissionError("tenant mismatch")
    return AuthContext(supplied,principal,scopes)


def make_handler(port,authority_provider):
    service=HumanOperationsService(port)

    class Handler(BaseHTTPRequestHandler):
        max_body=16384

        def log_message(self,format,*args):
            return

        def _send(self,status:int,content_type:str,payload:bytes)->None:
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(payload)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _json(self,status:int,value)->None:
            self._send(status,"application/json",json.dumps(value,separators=(",",":")).encode())

        def _body(self)->dict:
            raw_len=self.headers.get("Content-Length","0")
            length=int(raw_len)
            if length<0 or length>self.max_body:
                raise ValueError("body size")
            raw=self.rfile.read(length)
            value=json.loads(raw or b"{}")
            if not isinstance(value,dict):
                raise ValueError("object body required")
            return value

        def _write_context(self,tenant_id:str,required_action:str)->tuple[AuthContext,AuthoritySnapshot]:
            auth=_auth(self,tenant_id)
            if required_action not in auth.scopes:
                raise PermissionError(required_action)
            authority=authority_provider(auth,required_action)
            if not isinstance(authority,AuthoritySnapshot):
                raise PermissionError("authority unavailable")
            authority.validate(tenant_id=tenant_id,actor_principal_id=auth.principal_id)
            return auth,authority

        def do_GET(self)->None:
            path=urlsplit(self.path).path
            try:
                match=ALERT_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    self._json(HTTPStatus.OK,alert_api(port,_auth(self,tenant),alert_id))
                    return
                match=RESOURCE_RE.fullmatch(path)
                if match:
                    tenant,resource_id=match.groups()
                    self._json(HTTPStatus.OK,resource_api(port,_auth(self,tenant),resource_id))
                    return
                match=UI_ALERT_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    self._send(
                        HTTPStatus.OK,"text/html; charset=utf-8",
                        render_alert(port,_auth(self,tenant),alert_id).encode(),
                    )
                    return
                self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"})
            except PermissionError:
                self._json(HTTPStatus.FORBIDDEN,{"error":"forbidden"})
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"})

        def do_POST(self)->None:
            path=urlsplit(self.path).path
            try:
                match=RESOURCE_RE.fullmatch(path)
                if match:
                    tenant,resource_id=match.groups()
                    auth,authority=self._write_context(tenant,"human-operations:write")
                    body=self._body()
                    value=service.assign_resource(
                        authority=authority,tenant_id=tenant,resource_id=resource_id,
                        responsible_principal_id=str(body["responsible_principal_id"]),
                        responsibility_role=str(body["responsibility_role"]),
                        assignment_source=str(body["assignment_source"]),
                        actor_principal_id=auth.principal_id,
                        logical_action_id=str(body["logical_action_id"]),
                    )
                    self._json(HTTPStatus.OK,value); return

                match=RESOURCE_END_RE.fullmatch(path)
                if match:
                    tenant,_resource_id,assignment_id=match.groups()
                    auth,authority=self._write_context(tenant,"human-operations:write")
                    body=self._body()
                    value=service.end_resource(
                        authority=authority,tenant_id=tenant,assignment_id=assignment_id,
                        actor_principal_id=auth.principal_id,end_reason=str(body["end_reason"]),
                    )
                    self._json(HTTPStatus.OK,value); return

                match=ACTION_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    auth,authority=self._write_context(tenant,"human-operations:write")
                    body=self._body()
                    value=service.assign_action(
                        authority=authority,tenant_id=tenant,alert_id=alert_id,
                        owner_principal_id=str(body["owner_principal_id"]),
                        action_kind=str(body["action_kind"]),
                        actor_principal_id=auth.principal_id,
                        logical_action_id=str(body["logical_action_id"]),
                    )
                    self._json(HTTPStatus.OK,value); return

                match=ACK_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    auth,authority=self._write_context(tenant,"human-operations:ack")
                    body=self._body()
                    value=service.ack(
                        authority=authority,tenant_id=tenant,alert_id=alert_id,
                        actor_principal_id=auth.principal_id,
                        logical_action_id=str(body["logical_action_id"]),
                        note=body.get("note"),
                    )
                    self._json(HTTPStatus.OK,value); return

                match=VIEW_REQ_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    auth,authority=self._write_context(tenant,"human-operations:write")
                    body=self._body()
                    value=service.require_visibility(
                        authority=authority,tenant_id=tenant,alert_id=alert_id,
                        viewer_principal_id=str(body["viewer_principal_id"]),
                        viewer_side=str(body["viewer_side"]),
                        capability_class=str(body["capability_class"]),
                        presentation_ref=str(body["presentation_ref"]),
                        actor_principal_id=auth.principal_id,
                        logical_action_id=str(body["logical_action_id"]),
                    )
                    self._json(HTTPStatus.OK,value); return

                match=VIEW_RECEIPT_RE.fullmatch(path)
                if match:
                    tenant,requirement_id=match.groups()
                    auth,authority=self._write_context(tenant,"human-operations:view")
                    body=self._body()
                    value=service.record_visibility(
                        authority=authority,tenant_id=tenant,requirement_id=requirement_id,
                        viewer_principal_id=auth.principal_id,
                        logical_action_id=str(body["logical_action_id"]),
                        session_evidence=dict(body["session_evidence"]),
                    )
                    self._json(HTTPStatus.OK,value); return

                self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"})
            except PermissionError:
                self._json(HTTPStatus.FORBIDDEN,{"error":"forbidden"})
            except (KeyError,TypeError,ValueError,json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST,{"error":"invalid_request"})

    return Handler
