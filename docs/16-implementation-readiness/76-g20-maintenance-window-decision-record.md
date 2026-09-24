# G20 — Maintenance Window

**Record #76 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

When a monitoring source undergoes planned maintenance (DB upgrade, network
change, agent restart), alerts from that source still fire but notifications
sent to operators are noise — they know about the outage. Without a suppression
mechanism, on-call staff receive false-positive pages during every planned
maintenance event.

G20 adds a tenant-scoped maintenance window: operators declare a time range
and optionally a set of source IDs. During that window the G9 notification
dispatch worker skips WhatsApp/ITSM delivery for covered sources. Alerts still
fire and remain visible in the NOC dashboard (with a "maintenance" badge) —
only delivery is suppressed.

---

## 2. Data model

`monitoring.maintenance_window`:

| Column | Type | Notes |
|--------|------|-------|
| window_id | TEXT PK | `mw:<uuid>` |
| tenant_id | TEXT | RLS enforced |
| label | TEXT | operator-visible description |
| source_ids | TEXT[] NULL | NULL = all sources for this tenant |
| starts_at | TIMESTAMPTZ | window start |
| ends_at | TIMESTAMPTZ | window end; must be > starts_at |
| created_by | TEXT | principal_id |
| created_at | TIMESTAMPTZ | immutable |
| cancelled_at | TIMESTAMPTZ NULL | soft cancel; NULL = not cancelled |

---

## 3. Functions

| Function | Caller | Purpose |
|----------|--------|---------|
| `g20_list_windows(tenant)` | app role | Active + upcoming windows |
| `g20_create_window(...)` | app role | Create a window |
| `g20_cancel_window(tenant, id, actor)` | app role | Soft-cancel a window |
| `g20_is_in_maintenance(tenant, source_id)` | app + worker | Check if source is currently in maintenance |

All SECURITY DEFINER with schema-qualified search path.
Invoker roles: `jlmirror_g20_mw_app_invoker`, `jlmirror_g20_mw_worker_invoker`.

---

## 4. API

```
GET    /api/v1/maintenance/windows           list active + upcoming
POST   /api/v1/maintenance/windows           create
DELETE /api/v1/maintenance/windows/{id}      cancel (soft delete)
```

Permission gate: `monitoring:operate` (same permission that gates the
monitoring operate sidebar nav item).

---

## 5. Notification dispatch integration

`workers/notification_dispatch.py` joins `alerting.alert` to resolve the
`monitoring_source_id` for each notification intent, then calls
`g20_is_in_maintenance()`. If `true`, the dispatch is released (not failed or
skipped in the outbox) so a future worker cycle retries when the window ends.

---

## 6. Frontend

- `MaintenancePage.tsx` — CRUD UI with Active / Upcoming sections, create form
  with datetime pickers and optional source filter
- `Shell.tsx` — Maintenance nav item gated on `monitoring:operate` permission
- `NOCDashboard.tsx` — orange "maintenance" badge on source cards that are
  currently in an active window; fetches window list every 60 s

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `sql/monitoring/020_maintenance_window.sql`
- [x] `api/routers/maintenance.py`
- [x] `api/main.py` — router registered
- [x] `workers/notification_dispatch.py` — maintenance check integrated
- [x] `frontend/src/pages/MaintenancePage.tsx`
- [x] `frontend/src/components/Shell.tsx` — Maintenance nav
- [x] `frontend/src/pages/NOCDashboard.tsx` — maintenance badge
- [x] `frontend/src/api/client.ts` — `delete()` method added
