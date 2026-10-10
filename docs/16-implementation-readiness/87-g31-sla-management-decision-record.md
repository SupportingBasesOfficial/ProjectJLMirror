# G31 — SLA Management

**Record #87 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-25**

---

## 1. Context

JLMirror manages live infrastructure alerts. Enterprise operators need formal
SLA commitments — response time (time to acknowledge) and resolution time (time
to resolve) — with breach detection and an audit log. G31 implements the
SLA definition model, per-alert tracking, and breach recording.

SLA trackers are populated by external integration or direct DB write when an
alert is raised and a matching SLA policy exists (by severity or catch-all).
G31 provides the detection pipeline; the tracker population hook is left to the
alerting intake path.

---

## 2. Schema

### `g1.sla_policy`

| Column | Type | Notes |
|--------|------|-------|
| sla_id | TEXT PK | `sla:<uuid>` |
| tenant_id | TEXT FK | tenant isolation |
| name | TEXT | max 120 chars |
| severity_match | TEXT | NULL = match all severities |
| response_secs | INTEGER | time-to-acknowledge in seconds |
| resolve_secs | INTEGER | time-to-resolve in seconds |
| enabled | BOOLEAN | soft-disable via PUT |

### `g1.sla_alert_tracker`

One row per alert that is under SLA. Unique on `(tenant_id, alert_id)`.
Fields: `response_deadline`, `resolve_deadline`, `acknowledged_at`,
`resolved_at`, `response_breached`, `resolve_breached`.

### `g1.sla_breach`

Immutable breach event log. `breach_type`: `response` | `resolve`.
`deadline_was` captures the original deadline for audit.

---

## 3. Breach detection worker

`workers/sla_checker.py` — `_process_pending(conn) -> int` hooked into
`run_all.py` tick loop. On each tick:
1. Fetches all tenants with active trackers (`resolved_at IS NULL`).
2. For each: detects unguarded response and resolve breaches.
3. Inserts a `sla_breach` row and sets the `*_breached` flag atomically.
4. Each breach is committed immediately; failure rolls back only that breach.

---

## 4. API

Prefix: `/api/v1/sla`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/policies` | List all policies for tenant |
| POST | `/policies` | Create policy |
| PUT | `/policies/{sla_id}` | Update fields (including enabled=false) |
| DELETE | `/policies/{sla_id}` | Soft-disable (sets enabled=false) |
| GET | `/trackers` | Active trackers (unresolved), max 200 |
| GET | `/breaches` | Breach log, newest first, max 200 |

---

## 5. Frontend

`frontend/src/pages/SLAPage.tsx` — three-tab view:
- **Policies** — table with create form; disable action per policy
- **Active** — live tracker table with breach warning indicators; refreshes every 30s
- **Breaches** — immutable breach log with type badge

Shell nav item "SLA" shown to principals with `monitoring:operate`.

---

## 6. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/016_g31_sla.sql` — 3 tables + indexes + grants (app + worker)
- [x] `api/routers/sla.py` — policies/trackers/breaches API
- [x] `api/main.py` — sla router registered
- [x] `workers/sla_checker.py` — breach detection `_process_pending`
- [x] `workers/run_all.py` — sla_checker added to tick loop
- [x] `frontend/src/pages/SLAPage.tsx` — policies, active, breaches tabs
- [x] `frontend/src/components/Shell.tsx` — SLA nav item + SLAPage render
