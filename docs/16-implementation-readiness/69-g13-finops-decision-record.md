# G13 FinOps — Usage Metering and Entitlement Visibility

**Record #69 | Class: Feature Gate | Status: Authorized**
**Gate authority: G13 FinOps | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-23**

---

## 1. Context

The commercial attribution structure (§10-12) was scaffolded in G1 Wave 4:
`g1.commercial_accounts`, `g1.contracts`, `g1.entitlements`, and
`g1.usage_meters` exist but are not yet populated by any live process.

G13 closes this gap:
- A worker aggregates observable usage from monitoring/alerting tables
  into `g1.usage_meters` on an hourly cadence.
- An API exposes the tenant's contract, entitlements, and usage meters
  to authenticated operators.
- A frontend page provides visibility into consumption against the plan.

---

## 2. Authority Scope

| What G13 does                                        | What G13 does NOT do             |
|------------------------------------------------------|----------------------------------|
| Read monitoring/alerting tables for usage counts     | Price or rate usage              |
| Write meter rows to `g1.usage_meters`                | Issue invoices or charge accounts|
| Expose `GET /api/v1/finops/*` read endpoints         | Modify contracts or entitlements |
| Show usage trends in the frontend                    | Enforce quota (gate separately)  |

Pricing, billing, and quota enforcement are out of scope for G13. This gate
provides **observation** — the data needed before those decisions can be made.

---

## 3. Meter Definitions

| Meter name                    | Source table                    | Aggregation  |
|-------------------------------|---------------------------------|--------------|
| `monitoring_sources_active`   | monitoring.monitoring_source    | COUNT        |
| `monitoring_resources_observed` | monitoring.monitoring_resource | COUNT (presence_state ≠ removed) |
| `alerting_alerts_active`      | alerting.alert                  | COUNT (lifecycle_state = active) |
| `aiops_findings_active`       | aiops.finding                   | COUNT (not expired, not dismissed) |
| `alert_transitions_24h`       | alerting.alert_transition       | COUNT (last 24 h)                |

Each meter row records `window_start`, `window_end` (typically 1 hour) and
`quantity`. The worker inserts one row per meter per tenant per run. Historical
rows are NOT pruned by G13 — retention is a separate operations concern.

---

## 4. Commercial Attribution

```
g1.tenants.organization_id
  → g1.commercial_accounts.organization_id
    → g1.contracts.account_id
      → g1.entitlements.contract_id
```

Usage meters carry `tenant_id` and `contract_id` for direct traceability.
The join chain is resolved at read time by the API.

---

## 5. API Contract

```
GET /api/v1/finops/summary      — contract + entitlements + latest meter snapshot
GET /api/v1/finops/usage        — meter history (default 7 days, limit 200)
```

Both require authenticated tenant session. No `finops:read` permission check —
any tenant member can see their own plan and usage (same model as AIOps).

---

## 6. Worker Cadence

- Runs every 3600 s (1 hour), tracked in memory
- One `g1.usage_meters` row per meter per tenant per run
- If `ANTHROPIC_API_KEY` is absent, `aiops_findings_active` returns 0
  (aiops schema may not have data; query handles gracefully)

---

## 7. Dev Seed

A dev commercial setup is seeded in `sql/g1/010_seed_commercial_dev.sql`:
- `acct:platform-dev` — commercial account for `org:platform`
- `contract:platform-dev` — active enterprise-dev plan
- Entitlements: `monitoring`, `alerting`, `itsm`, `aiops` (all active)
- No usage meter rows seeded — they are created by the worker at runtime.

---

## 8. Implementation Checklist

- [x] Decision record authored (this document)
- [x] `sql/g1/010_seed_commercial_dev.sql` — dev commercial seed
- [x] `workers/finops.py` — hourly metering worker
- [x] `api/routers/finops.py` — GET /finops/summary + /finops/usage
- [x] `api/main.py` — router registered, sandbox prefix added
- [x] `workers/run_all.py` — finops processor registered
- [x] `frontend/src/pages/FinOpsPage.tsx` — usage and entitlement visibility
- [x] `frontend/src/components/Shell.tsx` — FinOps nav item added

---

## 9. Open Questions

1. **Quota enforcement**: When should a tenant hitting a meter limit be blocked?
   Deferred to G13.1 — needs a policy definition.

2. **Retention policy**: `g1.usage_meters` grows unbounded. A rolling 90-day
   retention window should be added in G13.1.

3. **MSP attribution**: The delegated-admin scenario (MSP operator over
   tenant:a) needs cross-tenant meter aggregation for billing. The data model
   supports it (beneficiary_organization_id); the read path does not yet.
   Deferred to G13.2.
