from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from read_ui import AuthContext,alert_api,resource_api,render_alert

ALERT_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)/human-operations$")
RESOURCE_RE=re.compile(r"^/api/v1/tenants/([^/]+)/resources/([^/]+)/responsibilities$")
UI_ALERT_RE=re.compile(r"^/tenants/([^/]+)/alerts/([^/]+)/human-operations$")


def _auth(handler:BaseHTTPRequestHandler,tenant_id:str)->AuthContext:
    supplied=handler.headers.get("X-Tenant-Id","")
    principal=handler.headers.get("X-Principal-Id","")
    scopes=frozenset(x for x in handler.headers.get("X-Scopes","").split() if x)
    if supplied!=tenant_id:
        raise PermissionError("tenant mismatch")
    return AuthContext(supplied,principal,scopes)


def make_handler(port):
    class Handler(BaseHTTPRequestHandler):
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

    return Handler
