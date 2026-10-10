# G32 — Automation Runtime

**Record #88 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-25**

---

## 1. Context

JLMirror operators need to trigger external systems (webhooks) on schedule or
on-demand in response to platform events. G32 implements a safe, production-ready
automation runtime: webhook and no-op script definitions, interval-based
schedules, manual triggers, and an immutable run history.

Arbitrary shell execution is deliberately excluded from the initial scope —
webhook callbacks cover the most common automation pattern (calling PagerDuty,
OpsGenie, custom tooling) without sandbox isolation complexity.

---

## 2. Script types

| type | Behavior |
|------|----------|
| `noop` | Logs the run; no external call. Used for testing the pipeline. |
| `webhook` | HTTP POST to a configured `https://` URL. Headers, method, and a body template with `{{tenant_id}}`, `{{script_id}}`, `{{run_id}}`, `{{timestamp}}` substitutions. |

---

## 3. Schema

### `g1.automation_script`
Definition table. `config` (JSONB) holds type-specific params (webhook URL, headers, body_template).

### `g1.automation_schedule`
One row per active schedule per script. Worker reads `next_run_at <= now()` and advances to `now() + interval_secs`.

### `g1.automation_run`
Immutable run record per execution. `trigger_type`: `manual` | `schedule`.
`outcome`: `pending` → `success` | `failed` | `skipped`.
`http_status` records the HTTP response code for webhook runs.

---

## 4. Worker

`workers/automation_runner.py` — `_process_pending(conn) -> int` in the tick loop:
1. Execute pending manual runs (queued by trigger API).
2. Claim due schedules (`next_run_at <= now()`), advance `next_run_at`,
   create run record, execute script.

Both paths call `_execute_run()` which fetches the script config and dispatches.

---

## 5. API

Prefix: `/api/v1/automation`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/scripts` | List scripts |
| POST | `/scripts` | Create (validates webhook URL) |
| PUT | `/scripts/{id}` | Update fields |
| POST | `/scripts/{id}/trigger` | Queue manual run → 202 Accepted |
| GET | `/schedules` | List schedules with script name |
| POST | `/schedules` | Create (interval_secs ≥ 60) |
| DELETE | `/schedules/{id}` | Soft-disable |
| GET | `/runs` | Run history, newest first, max 100 |

---

## 6. Frontend

`frontend/src/pages/AutomationPage.tsx` — three-tab layout:
- **Scripts** — table with "Run now" manual trigger; create form (type, webhook URL)
- **Schedules** — interval + next/last run times; add/disable
- **Run history** — outcome badge, trigger type, HTTP status, error detail; auto-refresh 15s

Shell nav item "Automation" shown to principals with `monitoring:operate`.

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/017_g32_automation.sql` — 3 tables + indexes + grants
- [x] `api/routers/automation.py` — scripts/schedules/runs/trigger API
- [x] `api/main.py` — automation router registered
- [x] `workers/automation_runner.py` — webhook executor + _process_pending
- [x] `workers/run_all.py` — automation_runner added to tick loop
- [x] `frontend/src/pages/AutomationPage.tsx` — scripts/schedules/runs tabs
- [x] `frontend/src/components/Shell.tsx` — Automation nav item + render
