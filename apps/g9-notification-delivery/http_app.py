from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from domain import AuthoritySnapshot
from read_ui import AuthContext,alert_intents_api,intent_api,render_intent
from service import NotificationService

ALERT_INTENTS_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/notifications$")
INTENT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/notifications/([^/]+)$")
UI_INTENT_RE=re.compile(r"^/tenants/([^/]+)/notifications/([^/]+)$")


def _auth(handler:BaseHTTPRequestHandler,tenant_id:str)->AuthContext:
    supplied=handler.headers.get("X-Tenant-Id","")
    principal=handler.headers.get("X-Principal-Id","")
    scopes=frozenset(x for x in handler.headers.get("X-Scopes","").split() if x)
    if supplied!=tenant_id:
        raise PermissionError("tenant mismatch")
    return AuthContext(supplied,principal,scopes)


def make_handler(port,authority_provider):
    service=NotificationService(port)

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
            length=int(self.headers.get("Content-Length","0"))
            if length<0 or length>self.max_body:
                raise ValueError("body size")
            value=json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value,dict):
                raise ValueError("object body required")
            return value

        def do_GET(self)->None:
            path=urlsplit(self.path).path
            try:
                match=INTENT_RE.fullmatch(path)
                if match:
                    tenant,intent_id=match.groups()
                    self._json(HTTPStatus.OK,intent_api(port,_auth(self,tenant),intent_id))
                    return
                match=ALERT_INTENTS_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    self._json(HTTPStatus.OK,alert_intents_api(port,_auth(self,tenant),alert_id))
                    return
                match=UI_INTENT_RE.fullmatch(path)
                if match:
                    tenant,intent_id=match.groups()
                    self._send(
                        HTTPStatus.OK,"text/html; charset=utf-8",
                        render_intent(port,_auth(self,tenant),intent_id).encode(),
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
                match=ALERT_INTENTS_RE.fullmatch(path)
                if not match:
                    self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"});return
                tenant,alert_id=match.groups()
                auth=_auth(self,tenant)
                required="notification:write"
                if required not in auth.scopes:
                    raise PermissionError(required)
                authority=authority_provider(auth,required)
                if not isinstance(authority,AuthoritySnapshot):
                    raise PermissionError("authority unavailable")
                authority.validate(tenant_id=tenant,actor_principal_id=auth.principal_id)
                body=self._body()
                value=service.create(
                    authority=authority,tenant_id=tenant,alert_id=alert_id,
                    recipient_principal_id=body.get("recipient_principal_id"),
                    destination_ref=str(body["destination_ref"]),
                    reason=str(body["reason"]),payload_ref=str(body["payload_ref"]),
                    payload_hash=str(body["payload_hash"]),
                    visibility_requirement_id=body.get("visibility_requirement_id"),
                    actor_principal_id=auth.principal_id,
                    logical_action_id=str(body["logical_action_id"]),
                )
                self._json(HTTPStatus.OK,value)
            except PermissionError:
                self._json(HTTPStatus.FORBIDDEN,{"error":"forbidden"})
            except (KeyError,TypeError,ValueError,json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST,{"error":"invalid_request"})

    return Handler
