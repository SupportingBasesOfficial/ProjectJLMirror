# OPEN-REL-031 Decision Record — BFF Session-Store Mechanism: PostgreSQL System of Record + Redis Acceleration Cache

**Status:** proposed — PostgreSQL is selected as the candidate **Identity/session** system of record and Redis as the candidate security-acceleration cache; `OPEN-REL-031.A` durable Identity/session-store topology/ownership and `OPEN-REL-031.B` durable-store production numerics remain OPEN; concrete cache topology/invalidation/admission-epoch implementation remains under existing `OPEN-REL-015`; C2 closure of the combined mechanism is NOT YET COMPLETE pending those conformance decisions
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` — "the... BFF session-store product... remain[s] a C2 choice"), joining `OPEN-REL-031.A`/`.B`, `OPEN-REL-015`, `OPEN-REL-008.A/B` and production convergence objectives under `OPEN-REL-023`
**Drivers:** `ADR-005`, `ADR-012`, `ADR-017`, `ADR-002`, `ADR-006`, `ADR-008`, `SEC-AUTHZ-*`, `SEC-AUD-003`, `TM-013`, `rel.security-session-authority@1`

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR and it does **not** collapse Identity, Membership, Authorization or Platform Management into one backing store. ADR-005 remains authoritative: Identity/session lifecycle, tenant Membership, authorization policy and tenant lifecycle/access denial are separate authorities even when Redis accelerates a composed protected-request decision. PostgreSQL in this record is the candidate durable authority for the Identity/BFF-session state this record owns; a membership, permission or tenant-lifecycle mutation remains durably owned by its existing bounded context and transactional authority.

This record also does not silently reassign upstream OPEN ownership: durable Identity/session-store topology remains `OPEN-REL-031.A`; cache topology/invalidation/epoch mechanics remain `OPEN-REL-015`; full-cache-miss bulkhead mechanics/numerics remain `OPEN-REL-008.A/B`; and production convergence/SLO numerics remain subject to `OPEN-REL-023` plus applicable production gates.

## Context and problem

The BFF-managed browser session needs a durable Identity/session system of record plus a fast authorization/session lookup layer. Redis may accelerate a **composed** security decision containing session and derived currentness generations from other owning authorities, but Redis never becomes business truth and the session PostgreSQL store never becomes a shadow owner of membership, permission or tenant-lifecycle state.

The earlier candidate direction also had a correctness hole: after a durable revocation commits, a process crash or Redis write failure could leave stale positive cache state usable by another BFF replica. This record fixes the semantic failure class before any concrete cache topology is allowed to become canonical.

## Requirements and invariants this selection must satisfy

- ADR-005 separates Identity, Membership and authorization policy; external cache design cannot merge those owners.
- ADR-012 classifies session/permission caching as a **security acceleration cache** requiring durable/current authority or explicit fail-closed behavior.
- ADR-017 gives uncertain security authority no stale-tolerant escape hatch analogous to ordinary Control Plane cached continuity.
- `SEC-AUTHZ-004..006` forbid recovery or stale generations from resurrecting revoked authority.
- `SEC-AUD-003` requires a mandatory audit record or durable audit intent to commit atomically with a relevant protected security mutation.
- `docs/09-api-contracts/browser-bff-and-realtime-admission.md` requires active invalidation and bounded revalidation for revocation.
- No security-cache mechanism may make a tenant-wide or membership-wide revocation O(number of active sessions).

## Decision

PostgreSQL is the candidate durable store for BFF Identity/session authority. Redis is the candidate fast-path security acceleration cache. Membership/permission/tenant-access generations cached in Redis are derived from their **own current authorities**, not copied into the session store as new canonical truth.

Canonical dependency on the concrete deployment remains gated by the joined C2 evidence for `OPEN-REL-031.A` and `OPEN-REL-015`. The semantic protocol below is binding on any candidate mechanism that wants to satisfy those OPENs for this use case.

### Closure condition 1 — durable Identity/session authority topology tracking (`OPEN-REL-031`, high severity)

`OPEN-REL-031` owns only the missing durable Identity/session-store question: `.A` is the C2 topology/ownership mechanism (for example an accepted global/region shape and whether the Identity/session SoR is Control-Plane-owned or its own tier); `.B` is the C3 RPO/RTO/failover numeric envelope. Redis cache topology, invalidation transport and cache/replay epoch implementation are **not** reclassified into `.A`; those remain `OPEN-REL-015` and must conform to the security semantics below.

### Closure condition 2 — failure-safe security-cache fencing without authority laundering (binding, high severity)

A committed deny/revocation from any owning authority must not be maskable by stale positive Redis state. At the same time, the cache protocol must not move the source mutation into the Identity/session database simply to gain local atomicity.

#### Security-cache admission read set

A healthy protected request obtains one logical Redis admission read set in **one network round trip** using a mechanism that preserves the selected topology's required currentness semantics. The bounded read set may contain:

```text
BFF session authority generation
principal / credential generation where applicable
membership / permission generation for the tenant membership being exercised
tenant access / suspension generation where applicable
cache-admission generation
```

Each generation remains owned by its source authority. Redis stores only generation-bound acceleration/projection evidence.

A plain client-side pipeline is acceptable only if the selected topology can prove the resulting read set meets the same currentness/ordering contract; network-round-trip count alone is not correctness evidence. If `OPEN-REL-015` requires a server-side script/transaction, co-location rule, version-validation scheme or equivalent mechanism to prevent a stale mixed read from being admitted as current, that mechanism must be materialized and fault-tested before canonical use.

The `cache-admission generation` is **not self-authenticating Redis data**. A BFF may trust positive Redis security state only while holding still-valid trusted expected admission evidence whose continuity does not depend solely on the Redis dataset being judged current. The physical cache-admission/epoch/invalidation mechanism belongs to `OPEN-REL-015`; `OPEN-REL-031.A` supplies only the joined durable Identity/session-store topology. Expected admission evidence MAY be refreshed/latching outside the per-request path for a bounded interval; expired, lost or ambiguous evidence disables positive Redis admission.

Fixed rules:

- a positive session/cache record is bound to the authority-generation values it observed when filled;
- positive admission requires those values to match current non-fenced generation evidence and the cache-admission generation to match the BFF's trusted expected admission evidence;
- a fence at any applicable scope denies; missing/ambiguous generation evidence is not current;
- broad revocation advances/fences the smallest applicable authority-scope generation in O(1) or another bounded constant number of cache writes relative to active-session count;
- healthy steady state performs zero PostgreSQL generation queries on a cache hit; "one Redis round trip" does not mean one physical key regardless of security scope.

#### Authority-preserving mutation protocol

A `security_cache_transition` below is a **logical reliability record**, not a new business authority. Its durable reservation and terminal outcome live under the same transactional authority that owns the security mutation being performed:

- BFF session/logout or Identity credential/session retirement → Identity/session authority;
- membership disable/revocation → Membership owner;
- permission/scope policy removal → Authorization-policy owner;
- tenant suspension/access denial → Platform/tenant-lifecycle authority;
- any future security owner → that owner's accepted transactional boundary.

If an owning authority cannot durably reserve/serialize the transition and atomically commit its own mutation plus required cache-reconciliation/audit responsibility, that path is not conformant. The session PostgreSQL store SHALL NOT be used as a surrogate business owner merely to make this protocol convenient.

For a security-critical transition, the owning authority applies:

1. **Durably reserve one transition under the owning authority.** In a short transaction at the owner, atomically create-or-observe a logical `security_cache_transition` keyed by stable `transition_id`, authority type/scope, expected owner generation and intended mutation fingerprint. The record enters `prepared` with bounded ownership/lease metadata. Reservation changes no business/security authority by itself. Idempotent retry observes the same compatible transition; fingerprint mismatch rejects.
2. **Fence before the owning authority mutation when Redis is admitted healthy.** Only the current owner of a live `prepared` transition may CAS the applicable Redis authority-scope generation to a non-authorizing `revocation_fence` carrying that exact `transition_id`. A session-only logout fences session scope; membership, permission or tenant-wide changes fence their own scope generation once rather than rewriting sessions.
3. **A fenced scope never grants and is not cache-filled around.** Admission observing the fence fails closed. Cache-fill uses expected-state/CAS or equivalent accepted logic so a fill started before the fence cannot overwrite/bypass it, including for session keys absent when a broader scope fence was installed.
4. **Commit source truth, transition outcome, reconciliation and mandatory audit responsibility together at the owner.** In a second short owner transaction, lock/claim the live `prepared` transition; revalidate ownership/lease, not-cancelled state and expected **owner** authority generation; and ensure the selected `OPEN-REL-015` mechanism still considers the cache fence/admission generation eligible for commit. Only then mutate the owner's canonical state. The same commit marks the transition `committed`, persists the durable security-cache reconciliation/invalidation obligation and includes any mandatory audit record/intent required by `SEC-AUD-003`. If a precondition fails, the source authority mutation does not commit.
5. **Finalize Redis after source commit.** The writer/dispatcher may replace the fence with the new current generation/non-authorizing state. Existing session cache entries bound to an older scope generation fail comparison automatically; no eager O(N) rewrite is required. Durable reconciliation remains responsible until the cache is proven at the committed owner generation/state.
6. **Cleanup cannot race a sleeping writer.** Expired `prepared` cleanup first durably wins `prepared -> cancelled` under the owning authority. Only after that cancellation commits may cleanup remove/reconcile the Redis fence. The source-commit transaction requires a still-live `prepared` transition, so a writer waking after cancellation cannot commit. If the writer already owns the live transition lock/claim in its short commit transaction, cleanup cannot concurrently cancel it.
7. **Abort/cancel is safe.** After durable cancellation, reconciliation reads the current **owning source authority** and restores/advances cache state only from that truth. Timeout alone never changes a fence into positive authority.
8. **Concurrent writers are fenced by source generation and transition identity.** Failure to reserve/claim the expected owner generation or install its corresponding scope fence loses the current-authority race. Retry keeps the same logical transition identity; there is no last-write-wins cache overwrite.

No ordinary database transaction is held open while Redis is called. For non-session authorities the durable intent/outbox patterns already accepted by ADR-008/Phase 10 remain the publication/reconciliation substrate; this record does not create a cross-database transaction between separate bounded contexts.

#### Redis outage, partial partition and recovery admission

Redis-only outage may bypass to the relevant durable authority under the accepted bulkhead, but a writer's **local** Redis failure is not proof that other BFFs stopped trusting the old cache generation.

If the applicable scope fence cannot be installed, a security mutation may continue only after a **shared cache-admission fence/generation** makes the old Redis generation ineligible for positive security admission across every serving BFF that could otherwise use it. The mechanism that advances/distributes shared cache-admission state is selected under `OPEN-REL-015` and must have continuity independent of the Redis contents it fences. Fleet-wide exclusion is a barrier: old expected-admission leases must be invalidated, acknowledged retired or allowed to expire past the accepted safety horizon before a mutation relies on the degraded owner-direct path. If that cannot be proven — including split reachability / partial partitions — the security mutation fails closed.

A security mutation committed while Redis is excluded still commits its transition/reconciliation/audit obligations under its **source owner**. Redis re-entry requires a recovery-admission barrier: the cache mechanism establishes a trusted new admission generation/epoch or equivalent invalidation of pre-outage positives, reconciles durable obligations from all applicable source owners through the recovery boundary, distributes current expected-admission evidence, and only then serves positive session/permission authority again. Redis restart, cluster failover, replica promotion or restore without proven fence continuity retires the old cache-admission generation before positive admission resumes.

If Redis is replicated, security-critical cache reads/writes use a primary or replica proven caught up through the relevant fence/finalization generation according to `OPEN-REL-015`. Numeric lease, convergence and reconciliation targets remain production objectives under `OPEN-REL-023` and applicable C3 gates, not incidental cache TTLs.

#### Positive cache fills and degraded owner reads

Any positive fill or Redis-bypass authorization decision must read each required security fact from that fact's **currently admitted durable owner/read path** under its accepted consistency/currentness profile. A stale asynchronous PostgreSQL replica, restored snapshot, provider/IdP native object or session-store copy of another domain's state cannot manufacture current membership, permission or tenant-access authority. If current owner evidence cannot be established safely, protected admission fails closed rather than populating Redis with a positive guess.

### Closure condition 3 — degradation/capacity joins (binding, medium severity)

`docs/07-system-design/failure-and-degradation-matrix.md` distinguishes durable security-authority failure from acceleration-cache-only failure. Redis-only loss may bypass only under an explicit bulkhead/concurrency budget and fleet-wide cache-admission fencing. `OPEN-REL-008.A` owns bulkhead mechanism, `.B` production sizing, `OPEN-REL-015` cache recovery/admission mechanism, and each source authority retains its own availability/failover profile. None is collapsed into `OPEN-REL-031`.

### Closure condition 4 — named residency/reversibility risk (binding, medium severity)

Whether the Identity/session PostgreSQL SoR needs future regional partitioning remains `OPEN-REL-031.A`. Redis/cache-admission topology stays a separate `OPEN-REL-015` concern. Membership, authorization-policy and tenant-lifecycle storage/residency continue to follow their own owners; this decision cannot force them into the Identity/session topology.

## Consequences

### Positive
- preserves ADR-005 authority separation while allowing a single fast security-cache decision;
- reuses PostgreSQL for Identity/session SoR without making it a membership/tenant super-database;
- preserves one Redis network round trip and zero PostgreSQL-generation queries for healthy protected cache hits;
- committed revocation cannot be intentionally masked by stale positive cache under a conforming `OPEN-REL-015` mechanism;
- broad revocations use bounded scope generations rather than O(active sessions) rewrites;
- durable transition ownership makes fence cleanup mutually exclusive with a later source-authority commit;
- cache-admission generation cannot self-certify from the Redis snapshot it validates;
- existing OPEN ownership remains unique: Identity/session SoR topology (`OPEN-REL-031.A`), cache topology/invalidation/epoch (`OPEN-REL-015`), bulkheads (`OPEN-REL-008`), production convergence numerics (`OPEN-REL-023`).

### Negative / cost
- the acceleration layer is a composite of generations from multiple security/business owners and therefore requires explicit cross-owner invalidation contracts;
- healthy protected admission may read multiple bounded Redis keys/fields using an accepted one-round-trip currentness mechanism rather than one physical key;
- BFFs need bounded trusted expected cache-admission evidence outside the per-request durable-owner path;
- security-critical writes require a prepare reservation plus a later short commit transaction at their owning authority and a cache fence between them;
- durable transition/reconciliation records, cleanup and shared cache-admission state become correctness infrastructure;
- partial partitions intentionally fail security mutations closed when fleet-wide old-generation exclusion cannot be proven.

## Validation

Before the combined session/security-cache mechanism becomes canonical/production-eligible as applicable, conformance evidence SHALL prove:
- ADR-005 ownership remains intact: changing membership, permission policy or tenant lifecycle does not write canonical business state into the Identity/session store, and a session mutation cannot change those authorities;
- a forced logout/permission revocation/tenant suspension is denied on the first protected request that begins after the **owning authority** transition commits, without a per-request PostgreSQL generation query on the healthy-cache path;
- healthy cache-hit admission uses one Redis network round trip for the bounded read set and zero durable-owner generation queries;
- the selected one-round-trip Redis read mechanism cannot admit a stale mixed-generation read as current under concurrent fencing/finalization;
- a stale Redis snapshot cannot self-certify its old cache-admission generation; expired/lost expected admission evidence disables positive Redis admission;
- membership/permission/tenant revocation uses O(1) or bounded-constant scope-generation cache writes relative to cached-session count;
- a `sub`/principal-wide session revocation can use a principal/session-authority generation rather than enumerating/re-writing every BFF session;
- positive cache fill from any authority uses a currently admitted owner read path; stale async replicas/restored snapshots cannot fill positive security state;
- crash/pause after `prepared` reservation and cache fence but before source commit cannot later commit after cleanup durably cancels the transition;
- cleanup versus waking writer has one durable winner at the **source owner**;
- cache continuity loss after fence installation but before source commit invalidates commit eligibility or fleet-wide positive cache admission before the source mutation relies on that fence; uncertainty fails closed;
- crash after source commit but before Redis finalization leaves the affected scope non-authorizing and durable reconciliation eventually converges the cache;
- local Redis failure cannot be followed by source commit while another BFF may still trust the old cache generation unless fleet-wide old-generation exclusion wins first;
- a fenced broad scope cannot be bypassed by a concurrent cache fill for a previously absent session key;
- concurrent source mutations using the same expected owner generation produce one winning transition and stable retry identity;
- Redis-only outage does not exceed accepted `OPEN-REL-008` bulkheads on owner-direct fallback;
- Redis recovery/failover/restore with stale contents does not serve positives before the `OPEN-REL-015` recovery-admission barrier completes;
- PITR/failover/restore cannot resurrect revoked session, membership, permission or tenant-access authority; each source owner is reconciled forward before positive cache admission resumes;
- `SEC-AUD-003` mandatory audit responsibility is not lost in any crash window;
- `OPEN-REL-031.A`, `OPEN-REL-015`, `OPEN-REL-008` and `OPEN-REL-023` remain independently tracked and conformed rather than silently collapsed.

## Exit / revisit conditions

Revisit if `OPEN-REL-031.A` shows PostgreSQL cannot meet Identity/session topology needs, if `OPEN-REL-015` cannot provide the required fleet-wide admission/fencing continuity at acceptable cost, if cross-owner invalidation cannot meet the accepted security propagation bound, or if future residency requirements require Identity/session repartitioning.
