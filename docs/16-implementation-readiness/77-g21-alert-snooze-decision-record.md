# G21 — Alert Snooze

**Record #77 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

Maintenance windows (G20) suppress notifications for planned outages by source.
Alert Snooze is the complementary per-alert control: an operator who has ACKed
an alert and is actively investigating can snooze it to silence further paging
during the investigation window, without declaring full source maintenance.

Unlike lifecycle states (`active`, `resolved`), snooze is an overlay: the alert
remains visible and active in the NOC dashboard and Alerts page, but notification
dispatch skips delivery until the snooze expires.

---

## 2. Data model

`alerting.alert_snooze`:

| Column | Type | Notes |
|--------|------|-------|
| snooze_id | TEXT PK | `snz:<uuid>` |
| alert_id | TEXT | FK to alerting.alert |
| tenant_id | TEXT | RLS enforced |
| expires_at | TIMESTAMPTZ | when suppression lifts |
| snoozed_by | TEXT | principal_id |
| reason | TEXT NULL | operator note |
| created_at | TIMESTAMPTZ | immutable |
| cancelled_at | TIMESTAMPTZ NULL | soft cancel (unsnooze); NULL = still active |

Only one active snooze per alert: `g21_snooze_alert` cancels any prior active
snooze before inserting a new one. Max duration: 10 080 minutes (7 days).

---

## 3. Functions

| Function | Caller | Purpose |
|----------|--------|---------|
| `g21_snooze_alert(tenant, alert_id, duration_minutes, snoozed_by, reason)` | app role | Create/replace snooze |
| `g21_unsnooze_alert(tenant, alert_id, actor)` | app role | Cancel active snooze |
| `g21_is_snoozed(tenant, alert_id)` | app + worker | Check if alert is currently snoozed |

All SECURITY DEFINER with schema-qualified search path.
Invoker roles: `jlmirror_g21_snooze_app_invoker`, `jlmirror_g21_snooze_worker_invoker`.

Additionally, `jlmirror_app` is granted `SELECT ON alerting.alert_snooze` so
the `list_alerts` correlated subquery resolves `snoozed_until` without routing
through a function.

---

## 4. API

```
POST /api/v1/alerting/alerts/{alert_id}/snooze
     body: { duration_minutes: int, reason?: str }

POST /api/v1/alerting/alerts/{alert_id}/unsnooze
     (no body)
```

`GET /api/v1/alerting/alerts` now also returns `snoozed_until: ISO timestamp | null`
on each alert (from a correlated subquery against `alerting.alert_snooze`).

Permission gate: inherits the existing `alerting:operate` gate (same as other
alert mutation endpoints).

---

## 5. Notification dispatch integration

`workers/notification_dispatch.py` adds a G21 check immediately after the G20
maintenance check. The worker fetches `ni.alert_id` from the intent-alert JOIN
(was already joining `alerting.alert`), then calls `g21_is_snoozed(tenant,
alert_id)`. If true, the dispatch is released (not failed) so a future cycle
retries when the snooze expires.

Order of suppression checks:
1. G20 maintenance window (source-level)
2. G21 snooze (alert-level)

---

## 6. Frontend

- `AlertsPage.tsx` — "Actions" column added to alert table:
  - Active unsnoozed alerts: **Snooze** button → inline duration picker
    (30 min / 1 h / 4 h / 8 h / 24 h)
  - Active snoozed alerts: orange **snoozed Nh** badge + **cancel** link
  - Resolved alerts: no snooze control shown
- `useQuery` for alert list already refetches every 30 s; mutations call
  `invalidateQueries` on success so the badge appears/disappears immediately.

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `sql/alerting/003_g21_alert_snooze.sql`
- [x] `api/routers/alerting.py` — snooze/unsnooze endpoints + `list_alerts` subquery
- [x] `workers/notification_dispatch.py` — G21 snooze check integrated
- [x] `frontend/src/pages/AlertsPage.tsx` — snooze button + snoozed badge
