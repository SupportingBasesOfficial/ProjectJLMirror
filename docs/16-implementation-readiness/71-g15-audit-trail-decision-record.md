# G15 — Audit Trail

**Record #71 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-23**

---

## 1. Context

The `audit.audit_event` table has been append-only and RLS-scoped since G1.
20+ call sites across 8 API files write events for every mutation: identity,
tenant membership, human operations, monitoring requeue, alerting, notifications,
platform admin mutations, and session lifecycle (login, tenant switch).

G15 surfaces this data in the frontend shell for operators and auditors.
No new backend work is required — the read endpoint already exists:

```
GET /api/v1/observability/audit-events
```

Parameters: `action`, `subject_type`, `subject_id`, `limit` (max 200).
Returns events newest-first.

---

## 2. Access control

`audit:read` is included in roles: `admin`, `tenant_admin`, `operator`,
`member`, `auditor`. Roles that do NOT receive it: `viewer`, `display`
principals (service accounts).

The Audit tab is conditionally rendered in the shell only when the active
session's `permissions` array includes `audit:read`.

---

## 3. Event vocabulary

| action | actor_kind | subject_type |
|--------|-----------|--------------|
| `login`, `tenant_select` | `principal` | `session` |
| `membership.create`, `membership.remove` | `principal`, `platform_admin` | `membership` |
| `alert.acknowledge`, `alert.resolve` | `principal` | `alert` |
| `monitoring.requeue` | `principal` | `monitoring_source` |
| `notification_channel.*` | `principal` | `notification_channel` |
| `platform.*` | `platform_admin` | `organization`, `grant`, `relationship` |
| … and more | |

---

## 4. Deliverables

- [x] Decision record (this document)
- [x] `frontend/src/pages/AuditPage.tsx` — filterable audit event table
- [x] `frontend/src/components/Shell.tsx` — Audit tab gated on `audit:read`

---

## 5. What G15 does NOT cover

- Cross-tenant audit aggregation (platform admin view) — separate operator surface
- Audit event export / CSV download — deferred
- Real-time streaming of audit events — not required for initial delivery
- Server-side enforcement of `audit:read` vs `observability:read` — the
  endpoint is correctly behind `observability:read`; `audit:read` is a
  frontend-gating signal only in this version
