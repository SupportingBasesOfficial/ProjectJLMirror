# G16 — Alert Policy Management

**Record #72 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

Alert policies drive the alerting pipeline. A policy defines *what conditions
create an alert* — minimum problem severity (for Zabbix problems) or health
class changes (for monitoring health projections). Without a policy management
UI, operators must call the API directly to create or adjust policies.

The alerting router already implements the full CRUD surface:
- `GET /api/v1/alerting/policies` — list all versions for the tenant
- `POST /api/v1/alerting/policies` — create a new policy / new version
- `POST /api/v1/alerting/policies/{id}/effective` — enable, disable, or switch version

G16 surfaces this in the frontend shell as a "Policies" nav item.

---

## 2. Data model summary

Policies are immutable and append-only (no delete, no edit).
A policy has:
- **Identity**: `policy_id` (operator-assigned slug), `source_kind`
- **Condition** (mutually exclusive by `source_kind`):
  - `monitoring_problem`: `problem_min_severity` — minimum severity threshold
  - `monitoring_health_projection`: `health_classes` — set of health classes that trigger
- **Scope** (optional): `monitoring_source_id`, `monitoring_resource_id`
- **Lifecycle**: each change creates a new `policy_version`; the effective pointer
  can be moved between non-superseded versions; `enabled` flag disables without
  creating a new version

---

## 3. UI behavior

The Policies page (`alerting:read` to view, `alerting:operate` to write):

- **Policy list**: grouped by `policy_id`. Each group shows the effective
  version and its condition, with enable/disable toggle. Superseded versions
  shown on expand.
- **Create / new version**: inline form. `policy_id` is free-text for new
  policies; for "new version" it carries the existing ID. On submit, calls
  `POST /policies` then invalidates the list.
- **Enable / disable**: calls `POST /policies/{id}/effective` with
  `{ policy_version, enabled: false/true }`. No version change — just the flag.

---

## 4. Deliverables

- [x] Decision record (this document)
- [x] `frontend/src/pages/AlertPoliciesPage.tsx`
- [x] `frontend/src/components/Shell.tsx` — Policies nav item added

---

## 5. Invariants

- Creating a policy version with `make_effective: true` (default) atomically
  supersedes the previous effective version at the DB layer.
- A superseded version cannot be re-selected as effective (returns 409).
- The UI never offers delete — policies are the audit trail of what conditions
  triggered alerts; they must be retained.
