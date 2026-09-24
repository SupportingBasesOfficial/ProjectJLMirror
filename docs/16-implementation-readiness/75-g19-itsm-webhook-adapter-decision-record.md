# G19 — ITSM Webhook Adapter

**Record #75 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

G11 implemented the `action_request` outbox and the incident response
worker, but left `open_ticket` wired to a fixture stub
(`fixture-ticket-{hex}`). No external ITSM provider had been chosen.

G19 replaces the stub with a provider-neutral HTTP webhook adapter.
The design defers the provider choice to operator configuration —
any ITSM that can accept a POST and return JSON with a ticket ref
is supported without code changes.

---

## 2. Adapter contract

**Module**: `shared/itsm_adapter.py`

**Environment variables**:

| Variable | Required | Description |
|---|---|---|
| `ITSM_WEBHOOK_URL` | No | Full URL to POST ticket payloads to |
| `ITSM_WEBHOOK_TOKEN` | No | Bearer token for Authorization header |
| `ITSM_TIMEOUT` | No | Request timeout in seconds (default: 15) |

**Payload** (POST, `application/json`):
```json
{
  "action": "open_ticket",
  "tenant_id": "...",
  "request_id": "...",
  "event_id": "...",
  "metadata": {}
}
```

**Ref extraction** — the adapter searches the response JSON for the
first non-empty value at keys (in order):
`ref`, `ticket_id`, `id`, `number`, `sys_id`, `key`, `issue_id`.
Also searches a nested `result` object (ServiceNow pattern).

**Provider compatibility**:

| Provider | Ref key |
|---|---|
| ServiceNow | `sys_id` / `number` |
| Jira | `id` / `key` |
| Freshdesk | `id` |
| Linear | `id` |
| Custom webhook | `ref` |

---

## 3. Worker behavior change

`workers/incident_response.py` `open_ticket` branch:

| Condition | Result state | Notes |
|---|---|---|
| `ITSM_WEBHOOK_URL` not set | `skipped` | `failure_class = itsm_not_configured` |
| Webhook succeeds, ref found | `linked` | `provider_ref = <ref>` |
| Webhook fails (HTTP/network) | `unknown` | exception logged, G11 retry logic applies |
| Ref not in response | `linked` | `provider_ref = None` — ticket opened, no ref |

---

## 4. Deliverables

- [x] Decision record (this document)
- [x] `shared/itsm_adapter.py`
- [x] `workers/incident_response.py` — stub replaced
- [x] `.env.example` — ITSM_WEBHOOK_URL, ITSM_WEBHOOK_TOKEN, ITSM_TIMEOUT
