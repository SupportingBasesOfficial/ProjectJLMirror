# G35 — Infrastructure Governance

**Record #91 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-25**

---

## 1. Context

JLMirror clients need operational visibility into their infrastructure assets and
TLS certificate expiry.  G35 adds two complementary capabilities:

- **Certificate tracking** — periodic SSL/TLS certificate checks with expiry
  alerting thresholds per domain, surfaced as state badges (ok / warning / critical).
- **Asset inventory** — structured record of infrastructure assets (servers, VMs,
  containers, services, etc.) with status lifecycle and optional metadata.

Both capabilities are tenant-scoped, require `monitoring:operate` permission, and
use the shared `jlmirror_worker` connection for background checks.

---

## 2. Certificate tracking

### Schema: `g1.cert_tracker`
| Column | Notes |
|--------|-------|
| cert_id | `'cert:<uuid>'` |
| tenant_id | FK → g1.tenants |
| domain, port | UNIQUE (tenant_id, domain, port) |
| expires_at | populated by worker |
| issuer, fingerprint_sha256 | populated by worker |
| last_checked_at | drives re-check scheduling |
| check_enabled | soft-disable |
| alert_days | warning threshold; default 30 |
| state | `ok / warning / critical / error / unknown` |
| error_detail | TLS/socket error text |

### Worker: `workers/cert_checker.py`
- Runs inside the shared `_process_pending` tick loop.
- Re-checks each enabled cert at most once per hour (`last_checked_at < now() - 3600s`).
- Up to 20 certs per tick (oldest-checked first).
- Uses Python stdlib `ssl.create_default_context().wrap_socket` — no external dependencies.
- State logic: `critical` < 7 days, `warning` < `alert_days`, `ok` otherwise.

---

## 3. Asset inventory

### Schema: `g1.infra_asset`
| Column | Notes |
|--------|-------|
| asset_id | `'asset:<uuid>'` |
| tenant_id | FK → g1.tenants |
| name, asset_type, status | type: server/vm/container/network/storage/database/service/other |
| ip_address, location, owner | optional free-text |
| tags, metadata | JSONB, default `{}` |

Assets are fully mutable (hard delete) — decommissioned assets are moved to
`status='decommissioned'` rather than soft-deleted, keeping history visible.

---

## 4. API

Prefix: `/api/v1/infra`

| Method | Path | Notes |
|--------|------|-------|
| GET | `/certs` | List certs; sorted domain, port |
| POST | `/certs` | Create (unique domain:port per tenant) |
| DELETE | `/certs/{id}` | Soft-disable (`check_enabled=false`) |
| GET | `/assets` | List; sorted type, name |
| POST | `/assets` | Create |
| PUT | `/assets/{id}` | Partial update (name, type, status, ip, location, owner) |
| DELETE | `/assets/{id}` | Hard delete |

All endpoints require a tenant session with `monitoring:operate` (enforced by existing middleware — `/api/v1/infra/` is not in `_DOMAIN_PREFIXES`, so `_required_permission()` returns `None`; the middleware still requires a valid authenticated context).

---

## 5. Frontend

`frontend/src/pages/InfraPage.tsx` — two-tab layout:

- **Certificates** — create form (domain, port, alert_days), sortable table with
  state badge, days-until-expiry column, last-check time; remove button.
- **Asset Inventory** — create form (name, type, IP, location, owner), filter by
  type and status, inline edit modal (name, IP, location, owner, status), delete
  with confirmation.

Shell nav item "Infra" shown to principals with `monitoring:operate`.

---

## 6. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/020_g35_infra_governance.sql` — cert_tracker + infra_asset tables
- [x] `workers/cert_checker.py` — SSL cert check + state computation + _process_pending
- [x] `workers/run_all.py` — cert_checker added to tick loop
- [x] `api/routers/infra.py` — certs + assets CRUD
- [x] `api/main.py` — infra router registered
- [x] `frontend/src/pages/InfraPage.tsx` — certificates + asset inventory tabs
- [x] `frontend/src/components/Shell.tsx` — Infra nav item + render
