from __future__ import annotations

import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from read_ui import AuthContext, detail_api, list_api, render_detail, render_list

LIST_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts$")
DETAIL_RE=re.compile(r"^/api/v1/tenants/([^/]+)/alerts/([^/]+)$")
UI_LIST_RE=re.compile(r"^/tenants/([^/]+)/alerts$")
UI_DETAIL_RE=re.compile(r"^/tenants/([^/]+)/alerts/([^/]+)$")


def _auth(handler:BaseHTTPRequestHandler,tenant_id:str)->AuthContext:
    supplied_tenant=handler.headers.get("X-Tenant-Id","")
    subject=handler.headers.get("X-Subject-Id","")
    scopes=frozenset(x for x in handler.headers.get("X-Scopes","").split() if x)
    if supplied_tenant!=tenant_id:
        raise PermissionError("tenant path/context mismatch")
    return AuthContext(tenant_id=supplied_tenant,subject_id=subject,scopes=scopes)


def make_handler(port):
    class G7Handler(BaseHTTPRequestHandler):
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
            split=urlsplit(self.path)
            path=split.path
            try:
                match=LIST_RE.fullmatch(path)
                if match:
                    tenant=match.group(1)
                    auth=_auth(self,tenant)
                    requested=parse_qs(split.query).get("limit",["50"])[0]
                    self._json(HTTPStatus.OK,list_api(port,auth,int(requested)))
                    return

                match=DETAIL_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    auth=_auth(self,tenant)
                    self._json(HTTPStatus.OK,detail_api(port,auth,alert_id))
                    return

                match=UI_LIST_RE.fullmatch(path)
                if match:
                    tenant=match.group(1)
                    auth=_auth(self,tenant)
                    self._send(HTTPStatus.OK,"text/html; charset=utf-8",render_list(port,auth).encode())
                    return

                match=UI_DETAIL_RE.fullmatch(path)
                if match:
                    tenant,alert_id=match.groups()
                    auth=_auth(self,tenant)
                    self._send(HTTPStatus.OK,"text/html; charset=utf-8",render_detail(port,auth,alert_id).encode())
                    return

                self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"})
            except PermissionError:
                self._json(HTTPStatus.FORBIDDEN,{"error":"forbidden"})
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"})
            except (TypeError,ValueError):
                self._json(HTTPStatus.BAD_REQUEST,{"error":"invalid_request"})

        def log_message(self,format,*args):
            return

    return G7Handler
