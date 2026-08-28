# OPEN-REL-031 Decision Record — BFF Session-Store Mechanism: PostgreSQL System of Record + Redis Acceleration Cache

**Status:** proposed — Tier 1 (PostgreSQL SoR) and Tier 2 (Redis acceleration) mechanism selected; `OPEN-REL-031.A` topology/ownership and `OPEN-REL-031.B` numerics remain OPEN per this record's own findings; C2 closure of the mechanism NOT YET COMPLETE pending the topology decision below
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` — "the... BFF session-store product... remain[s] a C2 choice"), opening `OPEN-REL-031.A`/`.B` (`docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md`)
**Drivers:** `ADR-005`, `ADR-012`, `ADR-017`, `ADR-002`, `ADR-006`, `TM-013`, `rel.security-session-authority@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:18,45`)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: it selects a physical mechanism for the BFF session-store C2 residual named by IR-D-001, inside architecture already accepted by ADR-005 (BFF-managed confidential session), ADR-012 (cache/ephemeral-state classification) and ADR-017 (dependency failure categories). It was produced from an adversarial multi-round red/blue-team review; all confirmed findings below are closed here or in companion edits to already-accepted documents.

## Context and problem

The BFF-managed browser session (ADR-005) needs a durable system of record plus a fast-path lookup layer. This record selects PostgreSQL as the system of record and Redis as the fast-path acceleration cache. The adversarial review found the direction sound but identified previously-unaddressed gaps that this record closes or explicitly leaves tracked as OPEN.

## Requirements and invariants this selection must satisfy

- ADR-005 line 47: "credential revocation behavior survives multiple API replicas" is an explicit validation criterion.
- ADR-012 line 19-21: session/permission caching is classified as a **security acceleration cache** — a stricter category than ordinary performance cache — which "SHALL have a durable/current authority or explicit fail-closed policy."
- ADR-017 line 22 vs. line 28: security authority gets **no** stale-tolerant escape hatch, unlike control-plane data, which explicitly gets one — a deliberate asymmetry, not an oversight, that this record must respect rather than paper over.
- ADR-002 (cell containment): "tenant A failure/load in one cell does not materially affect unrelated cell" — identity/session data is global-by-design (ADR-005), so it sits structurally above the cell-containment boundary and needs its own, explicitly tracked HA discipline rather than inheriting cell HA by default.
- `docs/09-api-contracts/browser-bff-and-realtime-admission.md:230-244`: active invalidation and bounded revalidation are required for session revocation even on long-lived connections.

## Decision

PostgreSQL is the session/identity system of record; Redis is a fast-path acceleration cache for session/permission/revocation lookups. Selection is conditioned on the closure requirements below.

### Closure condition 1 — HA/topology tracking (opens `OPEN-REL-031`, high severity)

Unlike `rel.cell-transactional-store` (tracked by `OPEN-REL-003`/`004`) or `rel.control-plane-placement` (tracked by `OPEN-REL-001`/`002`/`004`), `rel.security-session-authority`'s own backing-store HA/topology had no OPEN item tracking it at all, despite its stricter (no-stale-tolerance) failure category making its blast radius *less* tolerable, not more. This record opens `OPEN-REL-031` (`docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md`) with the mechanism/ownership question as `.A` (C2) and RPO/RTO/failover numerics as `.B` (C3), mirroring `OPEN-REL-003`'s own mechanism-vs-numerics split. This record does **not** itself select single-global-primary vs. per-region/per-cell-group primaries — that is `OPEN-REL-031.A`'s open question — but it requires the decision to be made explicitly rather than defaulted, and requires a stated ownership answer (control-plane-owned vs. its own tier) so it inherits the correct existing OPEN-REL lineage.

### Closure condition 2 — failure-safe revocation fencing, durable transition ownership and one-round-trip fast path (binding, high severity)

ADR-012's "durable/current authority or explicit fail-closed policy" requirement for this cache class prohibits a PostgreSQL-committed revocation from being masked by stale positive Redis state. A two-system sequence of "commit PostgreSQL, then update Redis" is insufficient: a process crash or Redis write failure after the PostgreSQL commit could leave durable authority revoked while another BFF replica still authorizes from an older cache value. Retrying the API cannot undo the committed revocation, so this partial-write outcome must be safe by construction.

The cache also cannot require O(number of active sessions) rewrites for broader authority transitions such as membership disable, permission-policy change or tenant suspension. Those operations use an **authority-scope generation/fence**, not fanout invalidation of every session entry.

#### Security-cache admission read set

A healthy protected request obtains one logical Redis admission read set in **one network round trip** (for example one transaction/script/MGET/pipeline, depending on the selected Redis client/topology). The read set contains the session record plus the current generation/fence records required by the request's authority scope, such as:

```text
session authority generation
principal / credential generation where applicable
membership / permission generation for the tenant membership being exercised
tenant access generation / suspension fence where applicable
cache-admission generation
```

The `cache-admission generation` is **not self-authenticating Redis data**. A BFF may trust Redis positive security state only while it holds a still-valid trusted expected admission generation/lease established by the selected cache-admission authority. That expected value/lease must have continuity that does not depend solely on reading the same Redis dataset being judged current; otherwise a restored stale Redis snapshot could simply attest to its own stale generation. The selected physical authority/lease distribution mechanism is part of `OPEN-REL-031.A`, but the non-circularity requirement is fixed here. The BFF MAY refresh/latch this expected admission generation outside the per-request path for a bounded validity interval; it SHALL NOT continue positive Redis admission after that trusted lease/currentness evidence expires or becomes ambiguous.

The exact key decomposition remains replaceable C2 implementation detail, but these semantics are fixed:

- a positive session cache record is bound to the authority-generation values it observed when admitted/filled;
- positive admission succeeds only when those observed values equal the current non-fenced generation records returned in the same Redis read set **and** the Redis cache-admission generation equals the BFF's trusted expected admission generation/lease;
- a fence at any applicable scope denies; missing/ambiguous required generation evidence or missing/expired expected cache-admission evidence is not treated as current;
- broad revocation advances/fences the smallest applicable authority-scope generation in O(1) or another bounded constant number of cache writes relative to active-session count; it does **not** scan/rewrite every cached session;
- healthy steady-state admission performs zero PostgreSQL generation queries. One Redis network round trip may read multiple bounded keys/fields; "one round trip" never means "one Redis key regardless of security scope."

#### Failure-safe mutation protocol

For a security-critical transition — session/logout revocation, principal/credential retirement, membership/permission revocation, tenant suspension, MFA/step-up authority change — the writer applies the same protocol at the **smallest authority scope that covers the effect**. The protocol deliberately uses short PostgreSQL transactions around durable state and does **not** keep a database transaction open while waiting on Redis.

1. **Durably reserve one transition before touching Redis.** In a short PostgreSQL transaction, atomically create-or-observe a `security_cache_transition` (logical name; exact table/mechanism remains C2) keyed by stable `transition_id`, authority scope, expected durable authority generation and intended mutation fingerprint. The record enters `prepared` with bounded ownership/lease metadata. Creating this reservation changes no session/membership/tenant authority by itself. An idempotent retry observes the same compatible transition; a mismatched fingerprint is rejection, not a second transition.
2. **Fence before durable authority change when Redis is admitted healthy.** Only the current owner of a still-live `prepared` transition may atomically compare-and-set the applicable Redis generation record from the expected generation to a non-authorizing `revocation_fence` carrying that exact `transition_id`. A session-only logout may fence the session authority scope; membership or tenant-wide changes fence their scope generation once rather than rewriting all sessions.
3. **A fenced scope never grants and is not cache-filled around.** Any BFF whose admission read set contains the fence fails closed for that affected authority scope while the transition is unresolved. Cache-fill writes use expected-state/CAS semantics so a stale fill that began before the fence cannot overwrite or bypass a newer scope fence.
4. **Commit durable truth, transition outcome and repair responsibility together.** In a second short PostgreSQL transaction, the writer locks/claims the `prepared` transition and revalidates that its ownership/lease is still current, that it has not been `cancelled`, and that the expected durable authority generation is still current. Only then may the transaction mutate the session/authorization authority. The same commit marks the transition `committed` and persists the durable cache-reconciliation obligation. If any precondition fails, the authority mutation does not commit.
5. **Finalize the cache after commit.** After PostgreSQL commits, the writer may replace the fence with the new current generation/non-authorizing state. Existing session cache entries bound to the old scope generation automatically fail the generation comparison; they do not need eager O(N) rewrite. The durable reconciliation worker remains responsible until Redis is observed at the exact committed generation/state.
6. **Cleanup cannot race a sleeping writer.** When a `prepared` transition lease expires, cleanup first atomically changes the durable transition from `prepared` to `cancelled` (or claims an equivalent terminal-abort state) in PostgreSQL. Only **after** that durable cancellation commits may cleanup remove/reconcile the Redis fence. The writer's commit transaction requires the transition still be live `prepared`; therefore a writer that wakes after cleanup cancellation is unable to commit the security mutation. Conversely, once the writer has locked/claimed the live transition inside its short commit transaction, cleanup cannot concurrently cancel it. Timeout alone never turns a fence into positive authority.
7. **Abort/cancel is safe.** After durable cancellation, reconciliation reads current PostgreSQL authority and restores/advances cache state only from that durable truth. If Redis fence evidence disappears first because Redis itself is lost, no durable authority mutation has been authorized by that cancelled transition; Redis recovery is still governed by the cache-admission recovery barrier below.
8. **Concurrent writers are fenced by expected durable generation and transition identity.** Failure to reserve/claim against the expected authority generation or failure to install the corresponding cache fence means the mutation lost a current-authority race and must re-resolve rather than overwrite another transition. Retry never invents a second logical revocation for the same idempotent mutation.

This protocol preserves the D0 performance correction while removing both the partial-write race and an O(N) invalidation trap: healthy requests use one Redis network round trip and zero PostgreSQL generation reads; broad security transitions use bounded generation/fence updates rather than per-session cache fanout; and fence cleanup cannot restore old positive authority while the original writer still retains the right to commit.

#### Redis outage, partial partition and recovery admission

The accepted failure matrix allows Redis-only outage to bypass to PostgreSQL under a bulkhead, so security mutations are not required to make Redis available in order to change durable authority. That does **not** permit stale pre-outage Redis contents to become authoritative when Redis returns, and a writer's **local** inability to reach Redis is not enough to prove that every other BFF has stopped trusting an older cache generation.

When the Redis security-cache tier is unavailable or the writer cannot install the applicable pre-commit fence, the mutation may continue through PostgreSQL only after a **shared cache-admission fence/generation** has made the affected Redis cache generation ineligible for positive security admission across every BFF replica that could otherwise serve it. The authority that advances/distributes this shared admission state must itself provide continuity independent of the Redis contents being fenced; copying an epoch solely from the same Redis snapshot is insufficient. While that shared degraded state is current, reads bypass to PostgreSQL under the accepted bulkhead. If the system cannot prove that old positive cache authority has been fenced across the serving fleet — for example during a partial network partition with split reachability — the security-critical mutation fails closed rather than committing a durable revocation that some replica could still mask with stale Redis state. The exact coordination/topology mechanism for this shared admission generation is part of `OPEN-REL-031.A`; the invariant is fixed here.

A security-critical mutation committed while Redis is excluded still uses the durable transition protocol above and commits its cache-reconciliation obligation with the authority mutation. Redis re-entry is gated by an explicit recovery-admission barrier: the recovered tier advances/re-establishes a trusted cache recovery generation/epoch or equivalently invalidates the pre-outage positive namespace, replays/reconciles every durable security-cache obligation through the recovery boundary, updates the trusted expected admission generation/lease distributed to BFFs, and only then becomes eligible to serve positive session/permission authority again. Redis process restart, cluster failover, replica promotion or restore that cannot prove preservation through the last admitted fence/finalization generation similarly invalidates the old cache-admission generation until this barrier completes. Stale pre-outage or pre-failover cache state is never trusted merely because Redis is reachable again.

If Redis itself is replicated, security-critical cache reads/writes use the primary or a replica proven caught up through the relevant fence/finalization generation. Arbitrary lagging replicas cannot serve positive authority past the accepted bound. The resulting maximum staleness/reconciliation bound is published as an explicit security SLO, not left as an incidental cache TTL.

### Closure condition 3 — degradation-matrix row split (binding, medium severity; companion edit applied)

`docs/07-system-design/failure-and-degradation-matrix.md` previously merged "Redis fast-path down" and "Postgres SoR down" into one ambiguous "Security/session authority unavailable" row, even though ADR-012 deliberately created a distinct "security acceleration cache" category specifically because its failure semantics differ from the SoR. This is split into two explicit rows in that document: a durable-store-unavailable row (unchanged fail-closed, no permissive fallback) and an acceleration-cache-only-unavailable row (bypass to PostgreSQL under an explicit per-cell bulkhead/concurrency budget sized for full-cache-miss load; does not fail closed platform-wide). The cache-only recovery row also requires the shared degraded admission state and recovery-admission barrier above before Redis may again serve positive security authority. The PostgreSQL connection pool/bulkhead for the 100%-cache-miss scenario is sized and load-tested before production, tracked under `OPEN-REL-008.A/B`.

### Closure condition 4 — named residency/reversibility risk (binding, medium severity; recorded, not resolved)

`docs/07-system-design/cross-cell-and-global-operations.md:49` anticipates "a future region hierarchy may sit above cells" for residency; ADR-006 revisits the transactional store choice "with evidence that PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements." ADR-005 is tagged "Reversibility: costly" and its exit clause names only browser-session-transport changes, not storage-topology/residency repartitioning. No current invariant requires this store to be region-partitioned today, but the risk of a disruptive future migration is real and previously unnamed.

**Requirement:** this record names the risk explicitly rather than silently assuming a single global store is fine indefinitely: whether the session PostgreSQL SoR is expected to shard/replicate per future region boundary is an open question deferred to `OPEN-REL-031.A`'s topology decision, cross-referenced to `cross-cell-and-global-operations.md`'s residency section, so a future region-above-cells decision is not blocked by an unanticipated identity-plane migration.

## Consequences

### Positive
- reuses PostgreSQL, already the platform's accepted transactional pattern, for the session SoR rather than introducing a new durability model;
- preserves one Redis network round trip and zero PostgreSQL-generation queries for healthy protected admission;
- makes the PostgreSQL→Redis partial-write window fail closed instead of allowing a committed revocation to be hidden by stale positive cache state;
- broad membership/permission/tenant revocations advance bounded scope generations instead of requiring O(active sessions) cache rewrites;
- durable transition reservation makes cache-fence cleanup mutually exclusive with a later authority commit from the old writer;
- cache-admission generation cannot be self-certified by the same Redis snapshot it is meant to validate;
- durable reconciliation guarantees repair responsibility survives writer crash;
- abandoned pre-commit fences degrade availability only and cannot manufacture positive authority;
- Redis outage remains a performance/degradation event when PostgreSQL is healthy, while Redis recovery/failover cannot silently reintroduce stale authority;
- partial Redis partitions cannot let one BFF commit a revocation while another continues trusting an old cache generation;
- the degradation-matrix split prevents both a false platform-wide login outage on a Redis-only blip and an uncontrolled thundering herd against PostgreSQL.

### Negative / cost
- healthy protected admission may read multiple bounded Redis keys/fields in one pipeline/script/transaction rather than one physical key;
- BFFs need bounded trusted expected cache-admission generation/lease state whose refresh/continuity is outside the per-request PostgreSQL path;
- security-critical mutations require a durable prepare reservation plus a later short authority-commit transaction, adding one extra PostgreSQL round trip/state record to those comparatively rare writes;
- security-critical writes gain an additional Redis fence operation when the cache tier is healthy and may temporarily deny the affected session/scope while a transition is in flight;
- durable transition/reconciliation records, abandoned-fence cleanup and shared cache-admission state become correctness/security infrastructure rather than optional cache hygiene;
- Redis recovery/failover requires explicit reconciliation/epoch admission before positive cache traffic resumes;
- a partial Redis partition may intentionally make security-critical mutations fail closed until a shared degraded/admission fence can be proven;
- security-critical cache reads must be pinned to a Redis primary (or a provably caught-up replica) if Redis replication is used, which forecloses routing those specific reads to an arbitrary nearest replica for latency;
- `OPEN-REL-031.A`'s topology/coordination decision is now a tracked, must-close item before production, not an implicit default.

## Validation

Before production eligibility, conformance evidence SHALL prove:
- a forced logout/permission revocation/tenant suspension is honored on the very next request after the revocation transition commits, without any BFF replica needing to separately query PostgreSQL during the healthy-cache fast path;
- an ordinary authenticated request under normal operation issues zero PostgreSQL queries for session/generation validation and uses one Redis network round trip for the bounded admission read set at any cache-hit rate up to and including 100%;
- Redis returning a stale snapshot whose internal `cache-admission generation` agrees with its own stale session data is still rejected when it does not match the BFF's independently trusted expected admission generation/lease;
- expiry/loss/ambiguity of the BFF's expected cache-admission lease disables positive Redis admission until currentness is re-established; it is never silently extended by Redis reachability alone;
- membership/permission revocation and tenant suspension remain O(1) or another bounded constant number of Redis generation/fence writes with respect to the number of cached sessions; pre-existing session entries bound to the retired scope generation cannot continue authorizing;
- crash/pause after durable `prepared` reservation and Redis fence installation but **before** the authority-commit transaction cannot later commit after cleanup has durably cancelled the transition;
- cleanup racing an expired `prepared` transition and a waking writer has exactly one durable winner: either cleanup commits `cancelled` first and the writer's authority transaction fails, or the writer locks/claims the live transition first and cleanup cannot cancel until that transaction completes;
- crash or process kill **after** PostgreSQL authority commit but before Redis finalization leaves the affected scope non-authorizing and the durable reconciliation obligation eventually converges Redis to the committed generation/state;
- Redis failure while attempting the pre-commit fence cannot be followed by a PostgreSQL authority commit while stale Redis remains admitted for positive security reads; a shared cache-admission fence excludes the old generation first or the mutation fails closed;
- a partial Redis partition in which BFF A cannot reach the cache but BFF B can still reach an older positive generation does not permit A to commit the security mutation unless the old cache generation is globally fenced from positive admission;
- a fenced scope cannot be treated as an ordinary miss and cannot be overwritten/bypassed by a concurrent stale cache-fill, including fills for session keys that were absent when a broader membership/tenant scope fence was installed;
- concurrent revocations/permission changes using the same expected durable generation produce one winning transition and stable retry identity rather than last-write-wins cache corruption;
- Redis-only outage (PostgreSQL healthy) does not trigger platform-wide fail-closed login denial and does not thundering-herd PostgreSQL past its sized bulkhead;
- Redis recovery, failover or restore with deliberately preserved stale cache contents does not serve those positives before the new recovery-admission generation/reconciliation barrier completes and BFF expected-admission evidence is updated;
- a PostgreSQL SoR outage still fails closed for security-sensitive operations, unchanged from today;
- a request routed to a lagging Redis replica (if replication is used) does not observe a pre-revocation generation past the accepted replica-lag/currentness bound;
- PITR/failover/restore of either store cannot resurrect an already-retired session merely because cache state rolled back farther than durable authority; recovery re-establishes a new admitted cache generation and reconciles from current durable authority before positive admission resumes;
- the topology/coordination decision under `OPEN-REL-031.A` is made explicit and its failover/admission mechanism is fault-tested per the project's existing reliability evidence bar.

## Exit / revisit conditions

Revisit if `OPEN-REL-031.A`'s topology evidence shows the selected PostgreSQL/Redis ownership shape is untenable at production scale, if measured transition/fence/reconciliation cost violates the accepted security/latency envelope, or if a future region-above-cells decision requires session-store residency repartitioning.
