# G33 — Scheduled Reports

**Record #89 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-25**

---

## 1. Context

JLMirror operators and their clients need periodic visibility into platform
health without logging in. G33 implements scheduled email reports generated
directly from the DB: alert summaries, SLA breach summaries, and incident
summaries are delivered on configurable intervals via the same SMTP adapter
as G22 notification emails.

---

## 2. Report types

| type | Content |
|------|---------|
| `alert_summary` | Alerts by severity, count, and resolved count |
| `sla_summary` | SLA breach count by breach_type (response/resolve) |
| `incident_summary` | Incident count by state |

---

## 3. Schema

### `g1.report_template`
Definition: name, report_type, delivery_email, enabled.

### `g1.report_schedule`
One row per scheduled delivery. Worker checks `next_send_at <= now()` and
advances by `interval_secs`. Minimum interval: 3600 (1 hour).

### `g1.report_delivery`
Immutable delivery record: outcome (pending/sent/failed), period_start,
period_end, row_count, error_detail.

---

## 4. Worker

`workers/report_sender.py` — `_process_pending(conn) -> int` in the tick loop.
Data is collected per report_type from the existing schema tables.
Email body is rendered as plain text + HTML (sent as multipart/alternative).
Dev mode (no SMTP_HOST): logs the would-be send to stderr — no real email.

---

## 5. API

Prefix: `/api/v1/reports`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/templates` | List templates |
| POST | `/templates` | Create (validates email, report_type) |
| DELETE | `/templates/{id}` | Soft-disable |
| GET | `/schedules` | List with template name/email |
| POST | `/schedules` | Create (interval_secs ≥ 3600) |
| DELETE | `/schedules/{id}` | Soft-disable |
| GET | `/deliveries` | Delivery history, newest first, max 100 |

---

## 6. Frontend

`frontend/src/pages/ReportsPage.tsx` — three-tab layout:
- **Templates** — create, list, disable
- **Schedules** — schedule a template, list with next send time
- **Delivery history** — outcome badge, period, row count, sent timestamp

Shell nav item "Reports" shown to principals with `monitoring:operate`.

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/018_g33_reports.sql` — report_template, _schedule, _delivery tables
- [x] `api/routers/reports.py` — templates/schedules/deliveries CRUD
- [x] `api/main.py` — reports router registered
- [x] `workers/report_sender.py` — data collection + email send + _process_pending
- [x] `workers/run_all.py` — report_sender added to tick loop
- [x] `frontend/src/pages/ReportsPage.tsx` — templates/schedules/history tabs
- [x] `frontend/src/components/Shell.tsx` — Reports nav item + render
