# G24 — Public Status Page

**Record #80 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

Customers need a public URL they can check to understand whether the monitored
service is operational, degraded, or experiencing an outage. The page must be
accessible without any authentication — it is a customer-facing communication
surface, not an operator tool.

G24 delivers a per-tenant opt-in status page. Operators configure a slug
(URL-safe name) and a public display name; the BFF serves the page at
`/status/{slug}` without requiring a session or signed context.

---

## 2. Status computation

The page derives its status from live data at request time:

| Condition | Status |
|-----------|--------|
| Any alert with severity `critical` is active | `outage` |
| Any alert is active (non-critical) | `degraded` |
| No active alerts | `operational` |

The JSON endpoint returns counts so clients can show detail:

```json
{
  "status": "operational | degraded | outage",
  "public_name": "Acme Corp",
  "active_alerts": 0,
  "critical_alerts": 0,
  "source_count": 12
}
```

---

## 3. Schema

### `g1.tenant_status_config` — new table

| Column | Notes |
|--------|-------|
| tenant_id | PK |
| status_slug | UNIQUE across all tenants (URL namespace) |
| public_name | display name shown on the page |
| enabled | boolean; disabled page returns 404 |
| updated_at | last modified timestamp |

GRANT: `jlmirror_app` → SELECT, INSERT, UPDATE; `jlmirror_owner` → SELECT
(BFF reads this table directly without a tenant context set).

No RLS — the slug lookup is intentionally cross-tenant (to verify the slug
is unique and to serve the BFF's public endpoint).

---

## 4. BFF routes (no auth)

```
GET /status/{slug}
    → Renders the status page HTML
    → Returns 404 if slug not found or enabled=false

GET /api/public/status/{slug}
    → JSON status summary
    → Returns 404 if slug not found or enabled=false
```

Both routes are registered **before** the BFF's `StaticFiles` catch-all mount
so they are not intercepted by the frontend SPA handler.

The HTML page is a self-contained dark-theme page with embedded JS that polls
`/api/public/status/{slug}` every 30 seconds and updates the status indicator
without a page reload.

---

## 5. API (operator)

```
GET /api/v1/platform/status-page
    → { configured, status_slug?, public_name?, enabled?, public_url? }

PUT /api/v1/platform/status-page
    body: { status_slug, public_name, enabled }
    → upsert via ON CONFLICT (tenant_id) DO UPDATE
    → validates slug: alphanumeric + hyphens only
    → returns 409 if slug already claimed by another tenant
```

Router prefix: `/api/v1/platform` (shared with the existing platform router).

---

## 6. Frontend

`StatusPageCard` added to `PlatformPage.tsx`:
- Shows current slug and public URL as a clickable link when configured
- Edit form: slug input (lowercased automatically), public_name, enabled checkbox
- Save via PUT mutation; invalidates query cache on success
- Gated within the Platform view (accessible to operators)

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/011_g24_status_page.sql`
- [x] `api/routers/status_page.py`
- [x] `api/main.py` — status_page router registered
- [x] `bff/main.py` — public /status/{slug} and /api/public/status/{slug} routes
- [x] `frontend/src/pages/PlatformPage.tsx` — StatusPageCard added
