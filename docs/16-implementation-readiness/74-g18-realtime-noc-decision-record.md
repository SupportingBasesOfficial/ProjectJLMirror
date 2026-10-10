# G18 — Realtime NOC

**Record #74 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

The NOC dashboard polled two endpoints every 30 s and 60 s. ADR-011
mandates WebSocket as the primary authenticated realtime transport, but
explicitly carves out SSE for unidirectional server-to-browser workloads
where it "materially reduces cost/complexity while preserving authorization
semantics."

The NOC feed is strictly unidirectional (server → browser). SSE is the
correct transport — it uses the same HTTP session auth as every other API
call, requires no capability-token minting, and needs no new gateway
component.

---

## 2. Endpoint

```
GET /api/v1/noc/stream
```

- **Auth**: BFF-signed context headers (same middleware as all API routes)
- **Media type**: `text/event-stream`
- **Payload per event**: `data: {"alerts":[…],"sources":[…]}\n\n`
- **Cadence**: one snapshot every 5 s
- **Disconnect**: `asyncio.CancelledError` / `GeneratorExit` caught; loop exits cleanly
- **DB**: fresh connection per cycle via `db_tenant_connection(tenant)` — no
  persistent connection held across sleep intervals

---

## 3. BFF proxy

The BFF's `/api/v1/{path}` proxy uses `httpx.AsyncClient.stream()` for
SSE paths (triggered by `Accept: text/event-stream` header or `path ==
"noc/stream"`). All other routes continue to use buffered
`client.request()`. mTLS config (CA cert, client cert) is shared between
both paths.

---

## 4. Frontend behavior

`NOCDashboard.tsx` uses `EventSource`:

- On open → sets `connected = true`, shows pulsing green "live" dot
- On message → updates `alerts` and `sources` state
- On error → closes, falls back to REST poll immediately, retries SSE in
  10 s. Shows "reconnecting…" indicator.
- On unmount → closes EventSource and clears retry timer

---

## 5. Deliverables

- [x] Decision record (this document)
- [x] `api/routers/noc_stream.py`
- [x] `api/main.py` — router registered
- [x] `bff/main.py` — SSE streaming proxy
- [x] `frontend/src/pages/NOCDashboard.tsx` — EventSource + live indicator
