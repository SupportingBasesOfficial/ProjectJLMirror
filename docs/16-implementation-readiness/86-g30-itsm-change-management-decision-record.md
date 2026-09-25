# G30 — ITSM Change Management

**Record #86 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

JLMirror manages live infrastructure and must support a formal change process
alongside incident management. G30 introduces the RFC (Request for Change)
model: a change request passes through draft → review → approved → scheduled
→ implementing → complete, with tasks and approval records attached.

This complements G10 (Incident Management) — an RFC can be linked to an
incident via `incident_id`, and incident resolution can reference the
implementing RFC.

---

## 2. Schema

### `g1.change_request`

| Column | Type | Notes |
|--------|------|-------|
| rfc_id | TEXT PK | `rfc:<uuid>` |
| tenant_id | TEXT FK | tenant isolation |
| title | TEXT | max 200 chars |
| description | TEXT | free-form, rollback plan etc. |
| category | TEXT | `standard` / `normal` / `emergency` |
| risk | TEXT | `low` / `medium` / `high` / `critical` |
| state | TEXT | `draft` / `review` / `approved` / `scheduled` / `implementing` / `complete` / `cancelled` |
| planned_start | TIMESTAMPTZ | optional |
| planned_end | TIMESTAMPTZ | optional |
| incident_id | TEXT | optional link to alerting.alert or itsm incident |
| created_by | TEXT | principal_id of creator |

### `g1.change_task`

Checklist items within an RFC. States: `open` / `in_progress` / `done` / `skipped`.
`assignee_ref` is a free-text principal ID or display name.

### `g1.change_approval`

Immutable approval records. `decision`: `approved` / `rejected`.
Recording an `approved` decision on a `review`-state RFC automatically
advances it to `approved`.

No SECURITY DEFINER functions — tables accessed via tenant-scoped connection
(same pattern as G24, G28). GRANT SELECT, INSERT, UPDATE to `jlmirror_app`.

---

## 3. API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/itsm/changes` | List all RFCs for tenant, ordered by created_at DESC |
| POST | `/api/v1/itsm/changes` | Create RFC (returns rfc_id, state: draft) |
| GET | `/api/v1/itsm/changes/{rfc_id}` | RFC with tasks[] and approvals[] |
| PUT | `/api/v1/itsm/changes/{rfc_id}` | Partial update of fields + state |
| POST | `/api/v1/itsm/changes/{rfc_id}/tasks` | Add checklist task |
| PUT | `/api/v1/itsm/changes/{rfc_id}/tasks/{task_id}` | Update task state/title |
| POST | `/api/v1/itsm/changes/{rfc_id}/approvals` | Record approval decision |

Router registered in `api/main.py` as `changes.router` (file: `api/routers/changes.py`).
Prefix: `/api/v1/itsm`. Note: existing `api/routers/itsm.py` is the G10
incident management router on `/api/v1/alerting/` — different prefix, no conflict.

---

## 4. Frontend

`frontend/src/pages/ITSMPage.tsx` — Change Management view:
- RFC list table: state badge, title, category, risk badge, planned start, created
- "New RFC" form: title, description, category, risk dropdowns
- RFC detail panel (single-level navigation): description, "Submit for review"
  button (draft→review), task checklist with inline state dropdowns, approval
  recording form (shown when state=review)
- Wired into Shell.tsx as view `"changes"` — nav item "Changes" shown to
  principals with `monitoring:operate` permission

---

## 5. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/015_g30_itsm_changes.sql` — 3 tables + indexes + grants
- [x] `api/routers/changes.py` — full RFC/task/approval API
- [x] `api/main.py` — changes router registered
- [x] `frontend/src/pages/ITSMPage.tsx` — RFC list + detail + tasks + approvals
- [x] `frontend/src/components/Shell.tsx` — Changes nav item + ITSMPage render
