import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/g11-incident-response"))

import io, json
from http.server import BaseHTTPRequestHandler
from unittest.mock import MagicMock
from http_app import make_handler


# --- Minimal fake port ---

class FakePort:
    def __init__(self):
        self.policy = None
        self.events = {}
        self.dedupe = set()
        self.actions = []

    def get_policy(self, tenant_id):
        return self.policy

    def upsert_policy(self, tenant_id, policy, actor_principal_id):
        self.policy = policy
        return policy

    def claim_dedupe(self, tenant_id, application_id, error_code, bucket_ts):
        key = (tenant_id, application_id, error_code, bucket_ts)
        if key in self.dedupe:
            return False
        self.dedupe.add(key)
        return True

    def store_event(self, event):
        eid = f"evt:{event.error_code}"
        self.events[eid] = {"event_id": eid, "status": "received",
                             "application_id": event.application_id,
                             "error_code": event.error_code,
                             "occurred_at": event.occurred_at,
                             "severity_hint": event.severity_hint}
        return {"event_id": eid, "status": "received"}

    def enqueue_action(self, tenant_id, event_id, action_kind):
        self.actions.append((tenant_id, event_id, action_kind))
        return {"request_id": f"req:{action_kind}", "action_kind": action_kind, "status": "pending"}

    def list_events(self, tenant_id):
        return list(self.events.values())

    def get_event(self, tenant_id, event_id):
        return self.events.get(event_id)

    def next_pending_action(self, tenant_id): return None
    def claim_action(self, *a): return {}
    def complete_action(self, *a): return {}
    def record_action_attempt(self, *a): return None


# --- HTTP test helper ---

class FakeSocket:
    def __init__(self, data: bytes):
        self._input = io.BytesIO(data)
        self._output = io.BytesIO()
    def makefile(self, mode, buffering=None, **_):
        return self._input if "r" in mode else self._output
    def sendall(self, data): self._output.write(data)
    def getpeername(self): return ("127.0.0.1", 9999)


def _request(handler_cls, method, path, body=None, headers=None):
    body_bytes = json.dumps(body).encode() if body else b""
    base_headers = {
        "X-Tenant-Id": "t1",
        "X-Principal-Id": "machine-p1",
        "X-Scopes": "incident_response:push incident_response:read incident_response:write",
    }
    if headers:
        base_headers.update(headers)
    h_lines = "".join(f"{k}: {v}\r\n" for k, v in base_headers.items())
    if body_bytes:
        h_lines += f"Content-Length: {len(body_bytes)}\r\n"
    raw = (
        f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n{h_lines}\r\n"
    ).encode() + body_bytes
    sock = FakeSocket(raw)
    handler_cls(sock, ("127.0.0.1", 0), MagicMock())
    sock._output.seek(0)
    response = sock._output.read().decode(errors="replace")
    status_line = response.split("\r\n")[0]
    status_code = int(status_line.split()[1])
    body_part = response.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in response else ""
    try:
        body_json = json.loads(body_part)
    except Exception:
        body_json = None
    return status_code, body_json, body_part


# --- Tests ---

def _make():
    port = FakePort()
    handler = make_handler(port)
    return port, handler


def test_push_event_returns_202_accepted():
    port, Handler = _make()
    status, body, _ = _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", {
        "application_id": "erp", "error_code": "ERR_DB", "error_message": "DB failed",
        "occurred_at": "2026-09-23T14:05:00Z", "severity_hint": "HIGH",
    })
    assert status == 202
    assert body["status"] == "accepted"
    assert "event_id" in body


def test_push_event_missing_required_field_returns_422():
    _, Handler = _make()
    status, body, _ = _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", {
        "application_id": "erp",  # missing error_code, error_message, occurred_at
    })
    assert status == 422


def test_push_event_duplicate_returns_200_deduplicated():
    port, Handler = _make()
    payload = {"application_id": "erp", "error_code": "ERR_DB",
               "error_message": "DB failed", "occurred_at": "2026-09-23T14:05:00Z"}
    _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", payload)
    status, body, _ = _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", payload)
    assert status == 200
    assert body["status"] == "deduplicated"


def test_push_event_wrong_tenant_returns_403():
    _, Handler = _make()
    status, body, _ = _request(
        Handler, "POST", "/api/v1/tenants/t2/application-error-events",
        {"application_id": "erp", "error_code": "ERR", "error_message": "x", "occurred_at": "2026-01-01T00:00Z"},
        headers={"X-Tenant-Id": "t1"},
    )
    assert status == 403


def test_push_event_without_push_scope_returns_403():
    _, Handler = _make()
    status, _, _ = _request(
        Handler, "POST", "/api/v1/tenants/t1/application-error-events",
        {"application_id": "erp", "error_code": "E", "error_message": "m", "occurred_at": "2026-01-01T00:00Z"},
        headers={"X-Tenant-Id": "t1", "X-Principal-Id": "p1", "X-Scopes": "incident_response:read"},
    )
    assert status == 403


def test_get_policy_returns_defaults_when_none_set():
    _, Handler = _make()
    status, body, _ = _request(Handler, "GET", "/api/v1/tenants/t1/incident-response-policy")
    assert status == 200
    assert body["severity_threshold"] == "HIGH"
    assert body["auto_open_ticket"] is False
    assert body["manual_override_only"] is False


def test_put_policy_updates_and_get_returns_updated():
    port, Handler = _make()
    put_status, put_body, _ = _request(Handler, "PUT", "/api/v1/tenants/t1/incident-response-policy", {
        "severity_threshold": "MEDIUM", "auto_open_ticket": True,
    })
    assert put_status == 200
    assert put_body["auto_open_ticket"] is True
    get_status, get_body, _ = _request(Handler, "GET", "/api/v1/tenants/t1/incident-response-policy")
    assert get_status == 200
    assert get_body["auto_open_ticket"] is True


def test_put_invalid_severity_threshold_returns_422():
    _, Handler = _make()
    status, body, _ = _request(Handler, "PUT", "/api/v1/tenants/t1/incident-response-policy", {
        "severity_threshold": "EXTREME",
    })
    assert status == 422


def test_list_events_empty():
    _, Handler = _make()
    status, body, _ = _request(Handler, "GET", "/api/v1/tenants/t1/application-error-events")
    assert status == 200
    assert body["events"] == []


def test_get_event_after_push():
    port, Handler = _make()
    _, push_body, _ = _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", {
        "application_id": "erp", "error_code": "ERR_DB", "error_message": "DB failed",
        "occurred_at": "2026-09-23T14:05:00Z",
    })
    event_id = push_body["event_id"]
    status, body, _ = _request(Handler, "GET", f"/api/v1/tenants/t1/application-error-events/{event_id}")
    assert status == 200
    assert body["error_code"] == "ERR_DB"


def test_get_unknown_event_returns_404():
    _, Handler = _make()
    status, _, _ = _request(Handler, "GET", "/api/v1/tenants/t1/application-error-events/nonexistent")
    assert status == 404


def test_push_auto_ticket_action_enqueued_when_policy_configured():
    port, Handler = _make()
    port.policy = {"severity_threshold": "LOW", "auto_open_ticket": True,
                   "manual_override_only": False, "notify_channels": [], "automation_triggers": []}
    _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", {
        "application_id": "erp", "error_code": "ERR_DB", "error_message": "DB failed",
        "occurred_at": "2026-09-23T14:05:00Z", "severity_hint": "HIGH",
    })
    assert any(a[2] == "open_ticket" for a in port.actions)


def test_push_no_action_when_manual_override_only():
    port, Handler = _make()
    port.policy = {"severity_threshold": "LOW", "auto_open_ticket": True,
                   "manual_override_only": True, "notify_channels": [], "automation_triggers": []}
    _request(Handler, "POST", "/api/v1/tenants/t1/application-error-events", {
        "application_id": "erp", "error_code": "ERR_DB", "error_message": "DB failed",
        "occurred_at": "2026-09-23T14:05:00Z", "severity_hint": "CRITICAL",
    })
    assert port.actions == []
