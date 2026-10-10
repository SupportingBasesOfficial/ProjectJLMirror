# G26 — Billing Stub Adapter

**Record #82 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

G13 established usage metering — aggregating observable usage from monitoring
and alerting tables into `g1.usage_meters`. G26 adds the architectural seam
between local metering and external billing providers: a `BillingAdapter`
interface with a `StubBilling` implementation that logs submissions without
posting to any external service.

The stub adapter is the safe default for all environments. Connecting a real
provider (Stripe, Chargebee, etc.) requires only implementing `BillingAdapter`
and setting `BILLING_ADAPTER=<provider>`.

---

## 2. Adapter interface

```python
class BillingAdapter(ABC):
    def submit_usage(self, *, tenant_id, meter, quantity,
                     window_start, window_end, contract_id=None) -> dict:
        # Returns {"submitted": bool, "provider_ref": str | None}

    def billing_status(self, *, tenant_id) -> dict:
        # Returns {"adapter": str, "status": str, "detail": str | None}
```

### StubBilling

Logs each `submit_usage` call at INFO level. Returns `{"submitted": True, "provider_ref": None}`.
Never raises `BillingError`.

### Factory

```python
adapter = billing_adapter()
# Reads BILLING_ADAPTER env (default: "stub")
# Raises BillingError if unknown adapter
```

---

## 3. Worker integration

`workers/finops.py` calls `adapter.submit_usage(...)` after each local
`INSERT INTO g1.usage_meters` succeeds. Adapter failures are logged at WARNING
but do not roll back the local meter write — local metering is authoritative;
the adapter call is best-effort.

The adapter is initialized once per worker process and cached (module-level
`_adapter`); init failures fall back to StubBilling so the worker stays live.

---

## 4. API

```
GET /api/v1/billing/status
    → { adapter: str, status: str, detail: str | null }
```

Reads the `BILLING_ADAPTER` env at request time; no DB query.

---

## 5. Frontend

A "Billing adapter" card added to `FinOpsPage`:
- Shows adapter name (badge), status, detail text
- Notes the `BILLING_ADAPTER` env var for operator awareness

---

## 6. Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `BILLING_ADAPTER` | `stub` | Adapter to use. Currently only `stub` is supported |

---

## 7. Deliverables

- [x] Decision record (this document)
- [x] `providers/billing.py` — BillingAdapter + StubBilling + billing_adapter() factory
- [x] `workers/finops.py` — adapter.submit_usage() call after meter writes
- [x] `api/routers/billing.py` — GET /api/v1/billing/status
- [x] `api/main.py` — billing router registered
- [x] `frontend/src/pages/FinOpsPage.tsx` — billing adapter status card
