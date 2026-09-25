# G27 — API Keys / Public API

**Record #83 | Class: Feature | Status: Authorized**
**Gate authority: G14 Production Release | Authorized by: Mauricio Reuter Neto**
**Date: 2026-09-24**

---

## 1. Context

Prior to G27, the only access path was the browser BFF (OIDC session + signed
context headers). G27 adds a programmatic access path: API keys with bearer
token authentication, enabling CI pipelines, monitoring dashboards, and
integrations to read platform data without a browser session.

---

## 2. Key model

- Raw key format: `jlm_<base64url(32 random bytes)>` — 47-character opaque string
- Only the SHA-256 digest is stored; raw key is shown once on creation
- Keys are independently attributable (principal_id + tenant_id stored)
- Revocation is durable (`state = 'revoked'`, `revoked_at` timestamp)
- Optional expiry (`expires_at`)
- Scopes: `read`, `monitoring:read`, `alerting:read` (read-only access in v1)
- Per-key `last_used_at` updated on each authenticated request

---

## 3. Schema

### `g1.api_keys`

| Column | Notes |
|--------|-------|
| key_id | PK `apikey:<uuid>` |
| tenant_id | FK, which tenant this key authorizes |
| principal_id | FK, which principal created the key |
| key_digest | SHA-256 hex of raw key (UNIQUE) |
| label | human-readable name |
| scopes | TEXT[] of permission scopes |
| state | active \| revoked |
| created_at | immutable |
| expires_at | optional; NULL = no expiry |
| last_used_at | updated on use |
| revoked_at | set when state → revoked |

### Functions

| Function | Purpose |
|----------|---------|
| `g27_create_api_key(tenant, principal, digest, label, scopes, expires_at)` | Insert key row |
| `g27_revoke_api_key(tenant, key_id)` | Set state=revoked |
| `g27_record_key_use(digest)` | Update last_used_at |

Invoker role: `jlmirror_g27_apikey_app_invoker` → granted to `jlmirror_app`.

---

## 4. Authentication path

The API middleware resolves contexts in order:

1. BFF signed context (HMAC headers) — browser sessions
2. `Authorization: Bearer jlm_...` — API keys (G27, new)
3. `X-Display-Token` — display principals (G9)
4. Anonymous dev sandbox

API key resolution:
- Extracts raw key from `Authorization: Bearer` header
- Computes SHA-256 digest
- Checks rate limit (in-memory token bucket, 60 req/min per key digest)
- Queries `g1.api_keys` for active, non-expired row
- Returns context `{principal_id, tenant_id, api_key: true, scopes}`

API key contexts bypass the session currentness check (no `g1.browser_sessions` row).

---

## 5. Rate limiting

In-memory token bucket: 60 requests per minute per key (keyed by digest).
Window resets on the minute boundary. Stale windows pruned at 10,000 entries.

Returns HTTP 429 with `{"state": "rate_limited"}` on excess. This is
process-local — horizontally scaled deployments have independent buckets.
Production: move to Redis or a shared store if stricter limits are needed.

---

## 6. API

```
GET    /api/v1/api-keys              → list keys (active + revoked) for tenant
POST   /api/v1/api-keys              body: { label, scopes }
                                     → 201 { key_id, raw_key (once), label, scopes, state }
DELETE /api/v1/api-keys/{key_id}     → revoke key
```

All management endpoints require a valid BFF session with `tenant:admin` permission.
The bearer token auth path can use any read endpoint the key's scopes allow.

---

## 7. Frontend

- `ApiKeysPage.tsx` — new page, gated on `tenant:admin`
  - Create form (label input) → `NewKeyModal` showing raw key with copy button
  - Table: label, scopes, last used, created, state, Revoke button
  - Warning: key shown only once
- `Shell.tsx` — "API Keys" nav item for tenant admins

---

## 8. Deliverables

- [x] Decision record (this document)
- [x] `sql/g1/013_g27_api_keys.sql`
- [x] `api/main.py` — bearer token middleware + rate limiter
- [x] `api/routers/api_keys.py`
- [x] `frontend/src/pages/ApiKeysPage.tsx`
- [x] `frontend/src/components/Shell.tsx` — API Keys nav item
