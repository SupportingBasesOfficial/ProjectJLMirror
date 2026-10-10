"""
HTTP reverse proxy handler.
Routes /api/v1/ and /tenants/ requests to the correct gate process by port.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

# Route table: (pattern, gate_key) — specific before general
_ROUTES: list[tuple[re.Pattern, str]] = [
    # G11
    (re.compile(r"^/api/v1/tenants/[^/]+/application-error-events(?:/[^/]+)?(?:\?.*)?$"), "g11"),
    (re.compile(r"^/api/v1/tenants/[^/]+/incident-response-policy(?:\?.*)?$"), "g11"),
    (re.compile(r"^/tenants/[^/]+/incident-response(?:\?.*)?$"), "g11"),
    # G8 — specific alert sub-routes before bare /alerts
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts/[^/]+/human-operations(?:\?.*)?$"), "g8"),
    (re.compile(r"^/api/v1/tenants/[^/]+/resources/[^/]+/responsibilities(?:/[^/]+/end)?(?:\?.*)?$"), "g8"),
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts/[^/]+/actions(?:\?.*)?$"), "g8"),
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts/[^/]+/acknowledgements(?:\?.*)?$"), "g8"),
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts/[^/]+/visibility-requirements(?:\?.*)?$"), "g8"),
    (re.compile(r"^/api/v1/tenants/[^/]+/visibility-requirements/[^/]+/receipts(?:\?.*)?$"), "g8"),
    (re.compile(r"^/tenants/[^/]+/alerts/[^/]+/human-operations(?:\?.*)?$"), "g8"),
    # G9
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts/[^/]+/notifications(?:\?.*)?$"), "g9"),
    (re.compile(r"^/api/v1/tenants/[^/]+/notifications/[^/]+(?:\?.*)?$"), "g9"),
    (re.compile(r"^/tenants/[^/]+/notifications/[^/]+(?:\?.*)?$"), "g9"),
    # G10
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts/[^/]+/incidents(?:\?.*)?$"), "g10"),
    (re.compile(r"^/api/v1/tenants/[^/]+/incidents/[^/]+(?:/(?:transition|assignment|comments))?(?:\?.*)?$"), "g10"),
    (re.compile(r"^/tenants/[^/]+/incidents/[^/]+(?:\?.*)?$"), "g10"),
    # G7 — least specific
    (re.compile(r"^/api/v1/tenants/[^/]+/alerts(?:/[^/]+)?(?:\?.*)?$"), "g7"),
    (re.compile(r"^/tenants/[^/]+/alerts(?:/[^/]+)?(?:\?.*)?$"), "g7"),
]

# Hop-by-hop headers not forwarded by proxy
_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})

_PROXY_HOST = "127.0.0.1"


class ProxyHandler(BaseHTTPRequestHandler):
    # Set by runtime: gate_key -> port number
    gate_ports: dict[str, int] = {}

    def log_message(self, fmt, *args):
        pass

    def do_GET(self): self._proxy()
    def do_POST(self): self._proxy()
    def do_PUT(self): self._proxy()
    def do_DELETE(self): self._proxy()

    def _proxy(self):
        path = self.path

        if path == "/health":
            self._send_json(200, {"status": "ok", "gates": list(self.gate_ports)})
            return

        gate = None
        for pattern, gkey in _ROUTES:
            if pattern.match(path):
                gate = gkey
                break

        if gate is None:
            self._send_json(404, {"error": "not_found", "path": path.split("?")[0]})
            return

        gate_port = self.gate_ports.get(gate)
        if not gate_port:
            self._send_json(503, {"error": "gate_not_started", "gate": gate})
            return

        target = f"http://{_PROXY_HOST}:{gate_port}{path}"
        body = self._read_body()
        req = urllib.request.Request(target, data=body or None, method=self.command)

        for key, val in self.headers.items():
            if key.lower() not in _HOP_BY_HOP:
                req.add_header(key, val)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in _HOP_BY_HOP:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            for k, v in exc.headers.items():
                if k.lower() not in _HOP_BY_HOP:
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self._send_json(502, {"error": "upstream_error", "gate": gate, "detail": str(exc)})

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else None

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
