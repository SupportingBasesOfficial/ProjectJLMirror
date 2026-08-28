# OPEN-REL-031 Decision Record — BFF Session-Store Mechanism: PostgreSQL System of Record + Redis Acceleration Cache

**Status:** proposed — Tier 1 (PostgreSQL SoR) and Tier 2 (Redis acceleration) mechanism selected; `OPEN-REL-031.A` topology/ownership and `OPEN-REL-031.B` numerics remain OPEN per this record's own findings; C2 closure of the mechanism NOT YET COMPLETE pending the topology decision below
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` — "the... BFF session-store product... remain[s] a C2 choice"), opening `OPEN-REL-031.A`/`.B` (`docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md`)
**Drivers:** `ADR-005`, `ADR-012`, `ADR-017`, `ADR-002`, `ADR-006`, `TM-013`, `rel.security-session-authority@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:18,45`)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: it selects a physical mechanism for the BFF session-store C2 residual named by IR-D-001, inside architecture already accepted by ADR-005 (BFF-managed confidential session), ADR-012 (cache/ephemeral-state classification) and ADR-017 (dependency failure categories). It was produced from an adversarial multi-round red/blue-team review; all four confirmed findings below are closed here or in companion edits to already-accepted documents.

## Context and problem

The BFF-managed browser session (ADR-005) needs a durable system of record plus a fast-path lookup layer. This record selects PostgreSQL as the system of record and Redis as the fast-path acceleration cache. The adversarial review found the direction sound but identified four real, previously-unaddressed gaps, all confirmed by independent re-verification against the repository with no refutations.

## Requirements and invariants this selection must satisfy

- ADR-005 line 47: "credential revocation behavior survives multiple API replicas" is an explicit validation criterion.
- ADR-012 line 19-21: session/permission caching is classified as a **security acceleration cache** — a stricter category than ordinary performance cache — which "SHALL have a durable/current authority or explicit fail-closed policy."
- ADR-017 line 22 vs. line 28: security authority gets **no** stale-tolerant escape hatch, unlike control-plane data, which explicitly gets one — a deliberate asymmetry, not an oversight, that this record must respect rather than paper over.
- ADR-002 (cell containment): "tenant A failure/load in one cell does not materially affect unrelated cell" — identity/session data is global-by-design (ADR-005), so it sits structurally above the cell-containment boundary and needs its own, explicitly tracked HA discipline rather than inheriting cell HA by default.
- `docs/09-api-contracts/browser-bff-and-realtime-admission.md:230-244`: active invalidation and bounded revalidation are required for session revocation even on long-lived connections.

## Decision

PostgreSQL is the session/identity system of record; Redis is a fast-path acceleration cache for session/permission/revocation lookups. Selection is conditioned on the four closure requirements below.

### Closure condition 1 — HA/topology tracking (opens `OPEN-REL-031`, high severity)

Unlike `rel.cell-transactional-store` (tracked by `OPEN-REL-003`/`004`) or `rel.control-plane-placement` (tracked by `OPEN-REL-001`/`002`/`004`), `rel.security-session-authority`'s own backing-store HA/topology had no OPEN item tracking it at all, despite its stricter (no-stale-tolerance) failure category making its blast radius *less* tolerable, not more. This record opens `OPEN-REL-031` (`docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md`) with the mechanism/ownership question as `.A` (C2) and RPO/RTO/failover numerics as `.B` (C3), mirroring `OPEN-REL-003`'s own mechanism-vs-numerics split. This record does **not** itself select single-global-primary vs. per-region/per-cell-group primaries — that is `OPEN-REL-031.A`'s open question — but it requires the decision to be made explicitly rather than defaulted, and requires a stated ownership answer (control-plane-owned vs. its own tier) so it inherits the correct existing OPEN-REL lineage.

### Closure condition 2 — synchronous revocation invalidation + generation counter (binding, high severity)

ADR-012's "durable/current authority or explicit fail-closed policy" requirement for this cache class was unmet as originally stated — the candidate decision specified no synchronous-invalidation guarantee and no staleness bound, and a pub/sub-based invalidation is best-effort and drops messages during partitions, leaving only Redis's TTL (chosen for performance, not security) as the real bound.

**Requirement:** security-critical writes — logout-all-devices, membership/permission revocation, tenant suspension, MFA/step-up state change — SHALL (1) commit to PostgreSQL, (2) synchronously invalidate/tombstone the Redis entry (or write a tombstone with the same TTL as the max acceptable staleness) before the revoking API call returns success, and (3) additionally advance a per-identity monotonic generation counter stored durably in PostgreSQL and carried as a cheap version check on every cache hit, so a partition-isolated replica serving a stale positive cache entry still fails the generation compare and re-fetches from PostgreSQL. The resulting maximum staleness bound is published as an explicit security SLO, not left as an incidental cache TTL.

### Closure condition 3 — degradation-matrix row split (binding, medium severity; companion edit applied)

`docs/07-system-design/failure-and-degradation-matrix.md` previously merged "Redis fast-path down" and "Postgres SoR down" into one ambiguous "Security/session authority unavailable" row, even though ADR-012 deliberately created a distinct "security acceleration cache" category specifically because its failure semantics differ from the SoR. This is now split into two explicit rows in that document: a durable-store-unavailable row (unchanged fail-closed, no permissive fallback) and a new acceleration-cache-only-unavailable row (bypass to PostgreSQL under an explicit per-cell bulkhead/concurrency budget sized for full-cache-miss load; does not fail closed platform-wide). The PostgreSQL connection pool/bulkhead for the 100%-cache-miss scenario is sized and load-tested before production, tracked under `OPEN-REL-008.A/B`.

### Closure condition 4 — named residency/reversibility risk (binding, medium severity; recorded, not resolved)

`docs/07-system-design/cross-cell-and-global-operations.md:49` anticipates "a future region hierarchy may sit above cells" for residency; ADR-006 revisits the transactional store choice "with evidence that PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements." ADR-005 is tagged "Reversibility: costly" and its exit clause names only browser-session-transport changes, not storage-topology/residency repartitioning. No current invariant requires this store to be region-partitioned today, but the risk of a disruptive future migration is real and previously unnamed.

**Requirement:** this record names the risk explicitly rather than silently assuming a single global store is fine indefinitely: whether the session PostgreSQL SoR is expected to shard/replicate per future region boundary is an open question deferred to `OPEN-REL-031.A`'s topology decision, cross-referenced to `cross-cell-and-global-operations.md`'s residency section, so a future region-above-cells decision is not blocked by an unanticipated identity-plane migration.

## Consequences

### Positive
- reuses PostgreSQL, already the platform's accepted transactional pattern, for the session SoR rather than introducing a new durability model;
- the generation-counter + synchronous-tombstone requirement closes the one revocation-consistency gap ADR-012 already demanded but the candidate decision left open;
- the degradation-matrix split prevents both a false platform-wide login outage on a Redis-only blip and a thundering herd against Postgres on a cache miss.

### Negative / cost
- synchronous invalidation adds latency to every security-critical write;
- the generation-counter check adds a cheap but non-zero read on every cache hit;
- `OPEN-REL-031.A`'s topology decision is now a tracked, must-close item before production, not an implicit default.

## Validation

Before production eligibility, conformance evidence SHALL prove:
- a forced logout/permission revocation/tenant suspension is honored on every BFF replica within the published staleness SLO, including a replica that missed the pub/sub invalidation message;
- a Redis-only outage (Postgres healthy) does not trigger platform-wide fail-closed login denial, and does not thundering-herd Postgres past its sized bulkhead;
- a Postgres SoR outage does fail closed for security-sensitive operations, unchanged from today;
- the topology decision under `OPEN-REL-031.A` is made explicit and its failover mechanism is fault-tested per `OPEN-REL-003.A/B`'s evidence bar.

## Exit / revisit conditions

Revisit if `OPEN-REL-031.A`'s topology evidence shows single-global-primary is untenable at production scale, or if a future region-above-cells decision requires session-store residency repartitioning.
