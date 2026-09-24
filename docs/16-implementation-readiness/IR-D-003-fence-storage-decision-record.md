# IR-D-003 Decision Record — BFF Session Fence Store

**Status:** proposed — mechanism selected; closure condition below is binding before this record satisfies the session-store C2 residual
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md` — "the exact IdP product, BFF session-store product… remain C2 choices under their existing fixed semantics")
**Drivers:** `OPEN-REL-031`, `OPEN-REL-015`, `IR-D-001`, `ADR-005`, `ADR-013`, `ADR-017`

This document is **not** a new ADR. It proposes PostgreSQL as the candidate canonical BFF session fence store and proposes the cache/invalidation semantics required by IR-D-001 and OPEN-REL-015. It grants no implementation authority until accepted.

## Context and problem

IR-D-001 fixes that "logout/revocation/session retirement invalidates server-side session authority even if a browser cookie remains present" and that "the actual security-cache propagation/fencing must conform to `OPEN-REL-031-session-store-decision-record.md` and the canonical `OPEN-REL-015` cache invalidation/epoch ownership." This record proposes a resolution for OPEN-REL-031. OPEN-REL-031 remains open until this record is accepted and its binding closure evidence is satisfied.

## Requirements and invariants this selection must satisfy

- IR-D-001: session retirement must propagate to BFF session authority within an accepted bound; a retired handle cannot admit protected operations.
- OPEN-REL-015: cache invalidation/epoch ownership must be explicit and traceable; no replica-local check-then-act that could admit a retired session.
- ADR-005: the fence store is Security authority; it does not mix business or tenant-data concerns.
- ADR-013: the store is accessed through an accepted adapter; no raw SQL outside the SessionAuthorityPort implementation.
- ADR-017: Security authority unavailability fails closed; the fence store being unreachable does not default to "session valid."

## Decision

### Proposed canonical fence store — PostgreSQL

If accepted, the BFF session fence store would be PostgreSQL, using a dedicated `auth` schema with restricted roles. This proposal does not authorize deployment topology or production use.

Session records hold:
- `session_digest` (SHA-256 of the opaque handle value; handle itself never stored)
- `principal_id` (platform principal, not Keycloak sub)
- `tenant_id` (tenant authority binding at issue time)
- `created_at`, `expires_at`
- `retired_at` (NULL = active; non-NULL = retired)
- `generation` (monotone integer; rotations increment; stale-generation retire is rejected)

Write operations (`create`, `retire`, `rotate`) go to PostgreSQL; the `SessionAuthorityPort` implementation is `PsycopgSessionAuthority`.

### In-process cache — 30 s TTL

A positive session-resolution result (active, not-expired record) may be cached in-process for up to 30 seconds to reduce DB round-trips on hot paths. The cache entry is keyed by `session_digest`.

Rules:
- cache entries are **never** used to admit a session that has been retired: `retire` and `rotate` operations MUST synchronously invalidate the in-process cache entry for the affected digest before returning success.
- On `rotate`, the predecessor digest is invalidated and the successor digest is inserted; no window exists where neither digest is valid for the live session.
- Cache TTL is 30 seconds; this is the maximum staleness for a session retirement to be observable from the cache perspective. The proposed cache-staleness bound is therefore 30 seconds in the current single-process monolith profile. Acceptance of this record is required before that bound becomes canonical.
- When session authority is unavailable (DB unreachable), the BFF fails closed: no cached positive result is extended beyond its last-verified TTL if the DB is not reachable to refresh it.

### Invalidation protocol

```
retire(digest):
    1. UPDATE session SET retired_at = now() WHERE digest = $1 AND retired_at IS NULL
    2. evict digest from in-process cache
    3. return success only if row was updated (idempotent: already-retired = no-op success)

rotate(old_digest, new_digest):
    1. BEGIN
    2. UPDATE session SET retired_at = now(), generation = generation + 1 WHERE digest = old_digest AND retired_at IS NULL
    3. INSERT new session record for new_digest with generation = old.generation + 1
    4. COMMIT
    5. evict old_digest from in-process cache
    6. insert new_digest into in-process cache
```

This ordering ensures the cache is never left in a state where a retired handle appears valid.

### Multi-instance propagation (future)

When the BFF is scaled to multiple instances (outside current monolith scope), in-process cache invalidation must be replaced by a distributed invalidation mechanism (e.g., Redis pub/sub or PostgreSQL LISTEN/NOTIFY). That mechanism requires a separate IR-D record before multi-instance deployment. Until then, all BFF session traffic routes to a single process.

### Closure condition — fence round-trip evidence (binding)

Before this record is treated as canonical:
- retire a session; attempt resolution within 30 s; confirm the attempt fails closed (retired session not re-admitted from cache);
- rotate a session; confirm the predecessor digest cannot be resolved after rotation and the successor digest resolves correctly;
- disconnect the DB; confirm a cached positive result is not extended for a new request that arrives after TTL expiry.

## Consequences

### Positive
- PostgreSQL provides durable ACID fencing; crashed process restores consistent session state on restart;
- 30 s TTL bounds cache-induced staleness to a concrete measurable window;
- explicit eviction on retire/rotate closes the classic TOCTOU window for session admission.

### Negative / cost
- a single PostgreSQL instance is a single point of failure for session authority; HA PostgreSQL (streaming replication + automated failover) is required before production;
- multi-instance BFF scaling requires a distributed invalidation mechanism not yet authorized.

## Validation

- a correctly retired session handle is rejected within 1 second (immediate eviction);
- a rotated predecessor handle is rejected and the successor handle is admitted;
- in the monolith boundary, retirement is visible to all request handlers in the same process without clock-skew risk;
- a crash and restart produces consistent session state from PostgreSQL without re-admitting retired sessions.

## Exit / revisit conditions

Revisit if BFF is scaled to multiple instances (requires distributed invalidation IR-D), if PostgreSQL is replaced or sharded in a way that complicates single-writer ACID semantics, or if session volume requires a dedicated session-store product (Redis Cluster + fencing protocol).
