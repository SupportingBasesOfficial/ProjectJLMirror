# G25 — Tenant Self-Service Onboarding

**Record #81 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

Prior to G25, tenant provisioning was manual — a platform admin had to create
the tenant record and grant membership before any user could access the platform.
G25 enables authenticated principals with no tenant membership to create their
first workspace without platform-admin intervention.

The onboarding flow is gated by authentication (the user must have completed
the OIDC login) but does not require a pre-existing tenant membership. It is
the only API endpoint that accepts an authenticated principal with an empty
tenant_id in context.

---

## 2. Flow

```
Sign in → OIDC callback → session established
    ↓
/api/session → { state: "needs_tenant", memberships: [] }
    ↓
Shell shows OnboardingPage (not the tenant picker)
    ↓
User enters workspace name → POST /api/v1/onboarding/register
    ↓
g25_register_tenant() creates tenant + admin membership
    ↓
Frontend calls POST /api/tenant/select with new tenant_id
    ↓
Session bound → /api/session returns { state: "ready" }
    ↓
Shell loads NOC Dashboard
```

When `memberships` is non-empty, the existing tenant picker is shown unchanged.

---

## 3. Schema

### `g1.g25_register_tenant(principal_id, display_name)` — SECURITY DEFINER function

Returns `(tenant_id, membership_id)`.

1. Validates the principal is active
2. Creates a new tenant (`tnt:<uuid>`, state `active`, isolation_class `pooled`)
3. Grants the caller `admin` membership

Invoker role: `jlmirror_g25_onboarding_app_invoker` → granted to `jlmirror_app`.

No new tables — uses existing `g1.tenants` and `g1.tenant_memberships`.

---

## 4. API

```
POST /api/v1/onboarding/register
     body: { tenant_name: string }
     auth: authenticated principal (no tenant context required)
     → 201 { tenant_id, membership_id, role: "admin", tenant_name }
```

Validation:
- `tenant_name` must be non-empty and ≤ 120 chars
- Principal must be active (validated inside the SQL function)

The API middleware's permission gate is bypassed for this path because
`/api/v1/onboarding/` is not in the monitored domain prefix list, and the
permission check is only applied when `required` is not None AND `tenant_id`
is set.

---

## 5. Frontend

- `OnboardingPage.tsx` — new page
  - Shown when `state === "needs_tenant"` and `memberships.length === 0`
  - Single text input for workspace name + "Create workspace" button
  - On submit: POST register → POST tenant/select → invalidate session query
  - Loading states: "Creating workspace…" and "Setting up session…"
- `Shell.tsx` — updated `needs_tenant` branch to conditionally show
  `OnboardingPage` or the existing tenant picker

---

## 6. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/012_g25_onboarding.sql`
- [x] `api/routers/onboarding.py`
- [x] `api/main.py` — onboarding router registered
- [x] `frontend/src/pages/OnboardingPage.tsx`
- [x] `frontend/src/components/Shell.tsx` — onboarding branch in needs_tenant
