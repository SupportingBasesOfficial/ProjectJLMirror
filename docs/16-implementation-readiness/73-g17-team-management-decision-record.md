# G17 — Team Management

**Record #73 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

Tenant admins had no self-service surface to manage team membership from
the shell. The API surface has been complete since G1:

- `GET /api/v1/tenant/members` — list all memberships (active + revoked)
- `POST /api/v1/tenant/members` — add or reactivate a member with a role
- `POST /api/v1/tenant/members/{id}/revoke` — revoke access
- `GET /api/v1/tenant/roles` — list custom roles
- `POST /api/v1/tenant/roles` — create a custom role with named permissions
- `POST /api/v1/tenant/roles/{name}/retire` — retire a custom role

G17 surfaces this as a "Team" nav item in the frontend shell.

---

## 2. Access control

The Team nav item is conditionally rendered only when the active session's
`permissions` array includes `tenant:admin`. This matches the router's
documented requirement. No backend enforcement change — the middleware gate
was already in place.

---

## 3. UI behavior

**Members section** (`tenant:admin`):
- Active members shown in a table: principal ID, role badge, join date, Revoke link
- Add Member inline form: free-text principal ID input + role select
  (built-in: admin, operator, viewer, auditor). Upserts — re-adding an
  existing revoked principal reactivates them with the new role.
- Revoked members collapsed in `<details>` below the table

**Custom roles section** (`tenant:admin`):
- Built-in roles shown as reference badges (not editable)
- Active custom roles listed with their permission set; Retire button per role
- Create Role inline form: slug name + permission checkbox grid
  (all 8 permissions from `shared.access.PERMISSIONS`)
- Retired roles collapsed in `<details>`

---

## 4. Permission vocabulary

The 8 permissions surfaced in the role creation form:

| Permission | Domain |
|---|---|
| `tenant:read` | Tenant membership reads |
| `tenant:admin` | Tenant admin mutations |
| `monitoring:read` | Monitoring source/resource reads |
| `monitoring:operate` | Monitoring requeue and operate |
| `alerting:read` | Alert and policy reads |
| `alerting:operate` | Alert acknowledge/resolve, policy mutations |
| `observability:read` | NOC, metrics, audit reads |
| `audit:read` | Audit trail read (also gates Audit nav) |

---

## 5. Deliverables

- [x] Decision record (this document)
- [x] `frontend/src/pages/TeamPage.tsx`
- [x] `frontend/src/components/Shell.tsx` — Team nav item gated on `tenant:admin`
