from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from callback import WhatsAppCallbackBoundary

CALLBACK_PATH="/api/v1/provider-callbacks/whatsapp"


def make_callback_handler(boundary:WhatsAppCallbackBoundary):
    class Handler(BaseHTTPRequestHandler):
        max_body=16384

        def log_message(self,format,*args):
            return

        def _json(self,status:int,value:dict)->None:
            payload=json.dumps(value,separators=(",",":")).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(payload)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self)->None:
            if urlsplit(self.path).path!=CALLBACK_PATH:
                self._json(HTTPStatus.NOT_FOUND,{"error":"not_found"})
                return
            try:
                length=int(self.headers.get("Content-Length","0"))
                if length<0 or length>self.max_body:
                    raise ValueError("body size")
                body=self.rfile.read(length)
                account=self.headers["X-Provider-Account-Ref"]
                callback_ref=self.headers["X-Provider-Callback-Ref"]
                message_ref=self.headers["X-Provider-Message-Ref"]
                evidence_kind=self.headers["X-Provider-Evidence-Kind"]
                timestamp=int(self.headers["X-Provider-Timestamp"])
                signature=self.headers["X-Provider-Signature"]
                value=boundary.admit(
                    provider_account_ref=account,
                    callback_ref=callback_ref,
                    provider_message_ref=message_ref,
                    evidence_kind=evidence_kind,
                    body=body,
                    timestamp_epoch=timestamp,
                    signature_hex=signature,
                )
                self._json(HTTPStatus.OK,value)
            except (PermissionError,KeyError):
                self._json(HTTPStatus.UNAUTHORIZED,{"error":"callback_not_authorized"})
            except (ValueError,TypeError,json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST,{"error":"invalid_callback"})

    return Handler
