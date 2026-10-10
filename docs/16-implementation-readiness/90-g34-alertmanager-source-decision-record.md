# G34 — Prometheus/Alertmanager Source

**Record #90 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-25**

---

## 1. Context

JLMirror clients operating Kubernetes clusters typically run Prometheus + Alertmanager
as their local alert evaluation engine.  G34 allows Alertmanager to push firing and
resolved alerts directly into JLMirror via a standard webhook receiver, providing
real-time ingestion without a polling agent.

---

## 2. Architecture

### Source isolation

Each registered Alertmanager source is tenant-scoped and identified by a unique
`source_id`.  The ingest endpoint is at:

```
POST /api/v1/sources/alertmanager/{source_id}/ingest
```

Authentication uses a pre-shared token (stored as SHA-256 hex).  The caller sends the
raw token in the `X-JLM-Webhook-Secret` header; the endpoint uses `secrets.compare_digest`
to prevent timing attacks.

### Middleware bypass

The ingest path bypasses the BFF/session middleware (same pattern as the G9 provider
callback).  The bypass is path-scoped:
`path.startswith("/api/v1/sources/alertmanager/") and path.endswith("/ingest")`.

Config management endpoints (`GET/POST/DELETE /api/v1/sources/alertmanager`) require
a standard tenant session.

### Event storage

Alertmanager webhook events are stored in `g1.alertmanager_event` — separate from
`alerting.alert`, which is constrained to Zabbix-originated events
(`source_kind IN ('monitoring_problem','monitoring_health_projection')`).  An `UPSERT ON
CONFLICT (source_id, fingerprint)` keeps only the latest state per alert fingerprint,
so repeated firings don't accumulate duplicates.

---

## 3. Schema

### `g1.alertmanager_source_config`
| Column | Type | Notes |
|--------|------|-------|
| source_id | TEXT PK | `'amgr:<uuid>'` |
| tenant_id | TEXT | FK → g1.tenants |
| display_name | TEXT | operator label |
| token_hash | TEXT | SHA-256 hex of pre-shared token |
| enabled | BOOLEAN | soft-disable stops ingest |
| created_at / updated_at | TIMESTAMPTZ | |

### `g1.alertmanager_event`
| Column | Type | Notes |
|--------|------|-------|
| event_id | TEXT PK | `'amev:<uuid>'` |
| source_id | TEXT | FK → alertmanager_source_config |
| tenant_id | TEXT | denormalised for query efficiency |
| fingerprint | TEXT | from Alertmanager payload |
| alert_name | TEXT | `labels.alertname` |
| severity | TEXT | `critical / warning / info / ok` |
| status | TEXT | `firing / resolved` |
| labels / annotations | JSONB | full payload from Alertmanager |
| starts_at / ends_at | TIMESTAMPTZ | |
| received_at | TIMESTAMPTZ | `DEFAULT now()` |
| UNIQUE | (source_id, fingerprint) | upsert key |

Severity mapping from Alertmanager `labels.severity`:
`critical/error → critical`, `warning/warn → warning`, `info → info`,
`none/ok → ok`, fallback → `warning`.

---

## 4. API

Prefix: `/api/v1/sources/alertmanager`

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `` | tenant session | List sources |
| POST | `` | tenant session | Create source; returns raw token ONCE |
| POST | `/{id}/rotate-token` | tenant session | Rotate token; returns new raw token ONCE |
| DELETE | `/{id}` | tenant session | Soft-disable |
| GET | `/{id}/events` | tenant session | Last 200 events, newest first |
| POST | `/{id}/ingest` | `X-JLM-Webhook-Secret` | Public ingest; no session |

---

## 5. Frontend

`frontend/src/pages/AlertmanagerPage.tsx` — single-page layout:

- **Source list** (left panel) — click to select
- **Detail panel** — webhook URL display, "Rotate token" + "Disable" actions, events table (30 s auto-refresh)
- **Create form** — display_name → creates source, shows one-time token modal
- **Token modal** — full-screen overlay showing raw token with copy-all text; closed manually; never shown again

Shell nav item "Alertmanager" shown to principals with `monitoring:operate`.

---

## 6. Scope boundary

G34 stores Alertmanager events in `g1.alertmanager_event`.  Integration with the core
`alerting.alert` pipeline (NOC dashboard, SLA tracker, incident correlation) requires a
separate gate that extends `alerting.alert.source_kind` and the transition model — deferred
to a future gate to avoid touching the core alert schema in this release.

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/019_g34_alertmanager.sql` — alertmanager_source_config + alertmanager_event tables
- [x] `api/routers/alertmanager_ingest.py` — config CRUD + public ingest endpoint
- [x] `api/main.py` — router registered; ingest path added to middleware bypass
- [x] `frontend/src/pages/AlertmanagerPage.tsx` — source management + event viewer
- [x] `frontend/src/components/Shell.tsx` — Alertmanager nav item + render
