# OPEN-REL-031 Decision Record — BFF Session-Store Mechanism: PostgreSQL System of Record + Redis Acceleration Cache

**Status:** proposed — Tier 1 (PostgreSQL SoR) and Tier 2 (Redis acceleration) mechanism selected; `OPEN-REL-031.A` durable-store topology/ownership and `OPEN-REL-031.B` durable-store production numerics remain OPEN; concrete cache invalidation/admission-epoch implementation remains under existing `OPEN-REL-015`; C2 closure of the combined mechanism is NOT YET COMPLETE pending those conformance decisions
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` — "the... BFF session-store product... remain[s] a C2 choice"), joining `OPEN-REL-031.A`/`.B`, `OPEN-REL-015`, `OPEN-REL-008.A/B` and production convergence objectives under `OPEN-REL-023`
**Drivers:** `ADR-005`, `ADR-012`, `ADR-017`, `ADR-002`, `ADR-006`, `TM-013`, `rel.security-session-authority@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:18,45`)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: it selects a physical session-store direction for the BFF C2 residual named by IR-D-001, inside architecture already accepted by ADR-005 (BFF-managed confidential session), ADR-012 (cache/ephemeral-state classification) and ADR-017 (dependency failure categories). It does not silently reassign upstream OPEN ownership: durable identity/session-store topology remains `OPEN-REL-031.A`, cache topology/invalidation/epoch mechanics remain `OPEN-REL-015`, full-cache-miss bulkhead mechanics/numerics remain `OPEN-REL-008.A/B`, and production convergence/SLO numerics remain subject to `OPEN-REL-023` plus applicable production gates.

## Context and problem

The BFF-managed browser session (ADR-005) needs a durable system of record plus a fast-path lookup layer. This record selects PostgreSQL as the system of record and Redis as the fast-path acceleration cache, subject to the still-OPEN mechanism/topology joins above. The adversarial review found the direction sound but identified previously-unaddressed correctness gaps that this record fixes semantically before any concrete cache topology is allowed to become canonical.

## Requirements and invariants this selection must satisfy

- ADR-005 line 47: "credential revocation behavior survives multiple API replicas" is an explicit validation criterion.
- ADR-012 line 19-21: session/permission caching is classified as a **security acceleration cache** — a stricter category than ordinary performance cache — which "SHALL have a durable/current authority or explicit fail-closed policy."
- ADR-017 line 22 vs. line 28: security authority gets **no** stale-tolerant escape hatch, unlike control-plane data, which explicitly gets one — a deliberate asymmetry, not an oversight.
- ADR-002 (cell containment): identity/session data is global-by-design (ADR-005), so its durable authority needs explicitly tracked topology/HA rather than inheriting cell HA by default.
- `docs/09-api-contracts/browser-bff-and-realtime-admission.md:230-244`: active invalidation and bounded revalidation are required for session revocation even on long-lived connections.

## Decision

PostgreSQL is the candidate session/identity system of record; Redis is the candidate fast-path acceleration cache for session/permission/revocation lookups. Canonical dependency on the concrete deployment remains gated by the joined C2 evidence for `OPEN-REL-031.A` and `OPEN-REL-015`. The semantic protocol below is binding on any candidate mechanism that wants to satisfy those OPENs for this session-authority use case.

### Closure condition 1 — durable authority topology tracking (`OPEN-REL-031`, high severity)

Unlike `rel.cell-transactional-store` (tracked by `OPEN-REL-003`/`004`) or `rel.control-plane-placement` (tracked by `OPEN-REL-001`/`002`/`004`), `rel.security-session-authority` previously had no OPEN item tracking its own durable backing-store HA/topology despite its stricter no-stale-tolerance failure category. `OPEN-REL-031` owns that missing durable-store question: `.A` is the C2 topology/ownership mechanism (for example single global primary vs. an accepted region/cell-group shape and whether the SoR is Control-Plane-owned or its own tier); `.B` is the C3 RPO/RTO/failover numeric envelope. Redis cache topology, invalidation transport and cache/replay epoch implementation are **not** reclassified into `.A`; those stay under `OPEN-REL-015` and must conform to this record's fixed security semantics.

### Closure condition 2 — failure-safe revocation fencing, durable transition ownership and one-round-trip fast path (binding, high severity)

ADR-012's "durable/current authority or explicit fail-closed policy" requirement prohibits a PostgreSQL-committed revocation from being masked by stale positive Redis state. A two-system sequence of "commit PostgreSQL, then update Redis" is insufficient: a process crash or Redis write failure after the PostgreSQL commit could leave durable authority revoked while another BFF replica still authorizes from an older cache value. Retrying the API cannot undo the committed revocation, so this partial-write outcome must be safe by construction.

The cache also cannot require O(number of active sessions) rewrites for broader authority transitions such as membership disable, permission-policy change or tenant suspension. Those operations use an **authority-scope generation/fence**, not fanout invalidation of every session entry.

#### Security-cache admission read set

A healthy protected request obtains one logical Redis admission read set in **one network round trip** using a mechanism that preserves the candidate topology's required currentness semantics. The bounded read set contains the session record plus the current generation/fence records required by the request's authority scope, such as:

```text
session authority generation
principal / credential generation where applicable
membership / permission generation for the tenant membership being exercised
tenant access generation / suspension fence where applicable
cache-admission generation
```

A plain client-side pipeline is acceptable only if the selected topology can prove the resulting read set meets the same currentness/ordering contract; network-round-trip count by itself is not a correctness proof. If the selected Redis topology requires a server-side script/transaction, co-location rule, version-validation scheme or another mechanism to prevent a stale mixed read from being admitted as current, `OPEN-REL-015` conformance must materialize and fault-test it.

The `cache-admission generation` is **not self-authenticating Redis data**. A BFF may trust Redis positive security state only while it holds a still-valid trusted expected admission generation/lease established by the selected cache-admission mechanism. That expected value/lease must have continuity that does not depend solely on reading the same Redis dataset being judged current; otherwise a restored stale Redis snapshot could simply attest to its own stale generation. The physical cache-admission/epoch/invalidation mechanism belongs to `OPEN-REL-015`, while `OPEN-REL-031.A` supplies the joined durable-authority topology it must reconcile against. The BFF MAY refresh/latch expected admission evidence outside the per-request path for a bounded validity interval; it SHALL NOT continue positive Redis admission after that trusted lease/currentness evidence expires or becomes ambiguous.

The exact key decomposition remains replaceable C2 implementation detail, but these semantics are fixed:

- a positive session cache record is bound to the authority-generation values it observed when admitted/filled;
- positive admission succeeds only when those observed values equal the current non-fenced generation records returned by the accepted Redis read mechanism **and** the Redis cache-admission generation equals the BFF's trusted expected admission generation/lease;
- a fence at any applicable scope denies; missing/ambiguous required generation evidence or missing/expired expected cache-admission evidence is not treated as current;
- broad revocation advances/fences the smallest applicable authority-scope generation in O(1) or another bounded constant number of cache writes relative to active-session count; it does **not** scan/rewrite every cached session;
- healthy steady-state admission performs zero PostgreSQL generation queries. "One Redis round trip" never means "one physical key regardless of security scope."

#### Failure-safe mutation protocol

For a security-critical transition — session/logout revocation, principal/credential retirement, membership/permission revocation, tenant suspension, MFA/step-up authority change — the writer applies the same protocol at the **smallest authority scope that covers the effect**. The protocol deliberately uses short PostgreSQL transactions around durable state and does **not** keep a database transaction open while waiting on Redis.

1. **Durably reserve one transition before touching Redis.** In a short PostgreSQL transaction, atomically create-or-observe a `security_cache_transition` (logical name; exact storage schema remains replaceable implementation detail) keyed by stable `transition_id`, authority scope, expected durable authority generation and intended mutation fingerprint. The record enters `prepared` with bounded ownership/lease metadata. Creating this reservation changes no session/membership/tenant authority by itself. An idempotent retry observes the same compatible transition; a mismatched fingerprint is rejection, not a second transition.
2. **Fence before durable authority change when the cache is admitted healthy.** Only the current owner of a still-live `prepared` transition may atomically compare-and-set the applicable Redis authority-scope generation from the expected generation to a non-authorizing `revocation_fence` carrying that exact `transition_id`. A session-only logout may fence the session scope; membership or tenant-wide changes fence their scope generation once rather than rewriting all sessions.
3. **A fenced scope never grants and is not cache-filled around.** Any BFF whose admission evidence observes the fence fails closed for that affected authority scope while the transition is unresolved. Cache-fill writes use expected-state/CAS or an equivalent accepted mechanism so a stale fill that began before the fence cannot overwrite or bypass a newer scope fence, including for session keys that did not exist when a broader scope fence was installed.
4. **Commit durable truth, transition outcome and repair responsibility together.** In a second short PostgreSQL transaction, the writer locks/claims the `prepared` transition and revalidates that its ownership/lease is still current, that it has not been `cancelled`, and that the expected durable authority generation is still current. The selected `OPEN-REL-015` mechanism must additionally ensure that a cache fence whose continuity has become uncertain (Redis restart/failover/restore/partition) cannot still qualify the transition to commit; such uncertainty first invalidates positive cache admission or the security mutation fails closed. Only after these preconditions may the transaction mutate the session/authorization authority. The same commit marks the transition `committed` and persists the durable cache-reconciliation obligation. If any precondition fails, the authority mutation does not commit.
5. **Finalize the cache after commit.** After PostgreSQL commits, the writer may replace the fence with the new current generation/non-authorizing state. Existing session cache entries bound to the old scope generation automatically fail the generation comparison; they do not need eager O(N) rewrite. The durable reconciliation worker remains responsible until the selected cache mechanism proves Redis at the exact committed generation/state.
6. **Cleanup cannot race a sleeping writer.** When a `prepared` transition lease expires, cleanup first atomically changes the durable transition from `prepared` to `cancelled` (or claims an equivalent terminal-abort state) in PostgreSQL. Only **after** that durable cancellation commits may cleanup remove/reconcile the Redis fence. The writer's commit transaction requires the transition still be live `prepared`; therefore a writer that wakes after cleanup cancellation is unable to commit the security mutation. Conversely, once the writer has locked/claimed the live transition inside its short commit transaction, cleanup cannot concurrently cancel it. Timeout alone never turns a fence into positive authority.
7. **Abort/cancel is safe.** After durable cancellation, reconciliation reads current PostgreSQL authority and restores/advances cache state only from that durable truth. If Redis fence evidence disappears because the cache is lost, no durable authority mutation has been authorized by that cancelled transition; Redis recovery is still governed by the cache-admission recovery barrier below.
8. **Concurrent writers are fenced by expected durable generation and transition identity.** Failure to reserve/claim against the expected authority generation or failure to install the corresponding cache fence means the mutation lost a current-authority race and must re-resolve rather than overwrite another transition. Retry never invents a second logical revocation for the same idempotent mutation.

This protocol preserves the D0 performance correction while removing both the partial-write race and an O(N) invalidation trap: healthy requests use one Redis network round trip and zero PostgreSQL generation reads; broad security transitions use bounded generation/fence updates rather than per-session cache fanout; and fence cleanup cannot restore old positive authority while the original writer still retains the right to commit.

#### Redis outage, partial partition and recovery admission

The accepted failure matrix allows Redis-only outage to bypass to PostgreSQL under a bulkhead, so security mutations are not required to make Redis available in order to change durable authority. That does **not** permit stale pre-outage Redis contents to become authoritative when Redis returns, and a writer's **local** inability to reach Redis is not enough to prove that every other BFF has stopped trusting an older cache generation.

When the Redis security-cache tier is unavailable or the writer cannot install the applicable pre-commit fence, the mutation may continue through PostgreSQL only after a **shared cache-admission fence/generation** has made the affected Redis cache generation ineligible for positive security admission across every BFF replica that could otherwise serve it. The authority/mechanism that advances and distributes this shared cache-admission state is selected under `OPEN-REL-015` and must provide continuity independent of the Redis contents it fences. Fleet-wide exclusion is a barrier: old expected-admission leases must be invalidated, explicitly acknowledged as retired, or allowed to expire past their accepted safety horizon before a mutation relies on the degraded PostgreSQL-only path. If the system cannot prove that old positive cache authority has been fenced across the serving fleet — for example during a partial network partition with split reachability — the security-critical mutation fails closed rather than committing a durable revocation that some replica could still mask with stale Redis state.

A security-critical mutation committed while Redis is excluded still uses the durable transition protocol above and commits its cache-reconciliation obligation with the authority mutation. Redis re-entry is gated by an explicit recovery-admission barrier: the cache mechanism advances/re-establishes a trusted cache recovery generation/epoch or equivalently invalidates the pre-outage positive namespace, replays/reconciles every durable security-cache obligation through the recovery boundary, updates trusted expected admission evidence distributed to BFFs, and only then becomes eligible to serve positive session/permission authority again. Redis process restart, cluster failover, replica promotion or restore that cannot prove preservation through the last admitted fence/finalization generation similarly retires the old cache-admission generation before positive admission resumes. Stale pre-outage or pre-failover cache state is never trusted merely because Redis is reachable again.

If Redis itself is replicated, security-critical cache reads/writes use the primary or a replica proven caught up through the relevant fence/finalization generation according to the selected `OPEN-REL-015` profile. Arbitrary lagging replicas cannot serve positive authority past the accepted bound. Numeric lease, convergence and reconciliation targets remain evidence-driven production objectives under `OPEN-REL-023` and applicable C3 gates, not incidental cache TTLs.

### Closure condition 3 — degradation-matrix row split and capacity join (binding, medium severity)

`docs/07-system-design/failure-and-degradation-matrix.md` distinguishes durable session authority failure from acceleration-cache-only failure. Redis-only loss may bypass to PostgreSQL only under an explicit per-cell bulkhead/concurrency budget and the fleet-wide cache-admission fencing rules above. The PostgreSQL connection-pool/bulkhead mechanism is joined to `OPEN-REL-008.A`, its production sizing to `OPEN-REL-008.B`, and Redis recovery admission to `OPEN-REL-015`. No one of these OPENs may be treated as closing the others.

### Closure condition 4 — named residency/reversibility risk (binding, medium severity; recorded, not resolved)

`docs/07-system-design/cross-cell-and-global-operations.md:49` anticipates a future region hierarchy above cells; ADR-006 revisits the transactional store choice if PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements. No current invariant requires this store to be region-partitioned today, but the risk of a disruptive future migration is real and must remain named. Whether the session PostgreSQL SoR shards/replicates per future region boundary stays in `OPEN-REL-031.A`; Redis/cache-admission topology remains a separate `OPEN-REL-015` concern joined by conformance, not merged into the durable-store OPEN.

## Consequences

### Positive
- reuses PostgreSQL, already the platform's accepted transactional pattern, for the session SoR rather than introducing a new durability model;
- preserves one Redis network round trip and zero PostgreSQL-generation queries for healthy protected admission;
- makes the PostgreSQL→Redis partial-write window fail closed instead of allowing a committed revocation to be hidden by stale positive cache state;
- broad membership/permission/tenant revocations advance bounded scope generations instead of requiring O(active sessions) cache rewrites;
- durable transition reservation makes cache-fence cleanup mutually exclusive with a later authority commit from the old writer;
- cache-admission generation cannot be self-certified by the same Redis snapshot it is meant to validate;
- existing OPEN ownership stays unique: durable SoR topology (`OPEN-REL-031.A`), cache topology/invalidation/epoch (`OPEN-REL-015`), bypass bulkheads (`OPEN-REL-008`), production convergence numerics (`OPEN-REL-023`);
- durable reconciliation guarantees repair responsibility survives writer crash;
- abandoned pre-commit fences degrade availability only and cannot manufacture positive authority;
- Redis outage remains a performance/degradation event when PostgreSQL is healthy, while Redis recovery/failover cannot silently reintroduce stale authority;
- partial Redis partitions cannot let one BFF commit a revocation while another continues trusting an old cache generation.

### Negative / cost
- healthy protected admission may read multiple bounded Redis keys/fields using an accepted one-round-trip currentness mechanism rather than one physical key;
- BFFs need bounded trusted expected cache-admission evidence whose refresh/continuity is outside the per-request PostgreSQL path;
- security-critical mutations require a durable prepare reservation plus a later short authority-commit transaction, adding one extra PostgreSQL round trip/state record to those comparatively rare writes;
- security-critical writes gain a cache fence operation when the cache tier is healthy and may temporarily deny the affected session/scope while a transition is in flight;
- durable transition/reconciliation records, abandoned-fence cleanup and shared cache-admission state become correctness/security infrastructure rather than optional cache hygiene;
- Redis recovery/failover requires explicit reconciliation/epoch admission before positive cache traffic resumes;
- a partial Redis partition may intentionally make security-critical mutations fail closed until fleet-wide old-generation exclusion can be proven;
- `OPEN-REL-031.A`, `OPEN-REL-015` and their joined conformance evidence are real C2 work, not hidden defaults.

## Validation

Before the combined session-store mechanism becomes canonical/production-eligible as applicable, conformance evidence SHALL prove:
- a forced logout/permission revocation/tenant suspension is honored on the first protected request that begins after the revocation transition commits, without any BFF needing a PostgreSQL generation query on the healthy-cache fast path;
- an ordinary authenticated request under normal operation issues zero PostgreSQL queries for session/generation validation and uses one Redis network round trip for the bounded admission read set at any cache-hit rate up to and including 100%;
- the selected one-round-trip Redis read mechanism cannot admit a stale mixed-generation read as current under concurrent fencing/finalization; a plain non-atomic pipeline is insufficient if the selected topology cannot prove equivalent currentness;
- Redis returning a stale snapshot whose internal cache-admission generation agrees with its own stale session data is still rejected when it does not match independently trusted expected admission evidence;
- expiry/loss/ambiguity of BFF expected cache-admission evidence disables positive Redis admission until currentness is re-established; it is never silently extended by Redis reachability alone;
- membership/permission revocation and tenant suspension remain O(1) or another bounded constant number of Redis generation/fence writes with respect to cached-session count; pre-existing session entries bound to the retired scope generation cannot continue authorizing;
- crash/pause after durable `prepared` reservation and cache fence installation but **before** the authority-commit transaction cannot later commit after cleanup has durably cancelled the transition;
- cleanup racing an expired `prepared` transition and a waking writer has exactly one durable winner: either cleanup commits `cancelled` first and the writer's authority transaction fails, or the writer locks/claims the live transition first and cleanup cannot cancel until that transaction completes;
- Redis continuity loss after fence installation but before the PostgreSQL authority commit invalidates the fence's commit eligibility or fleet-wide positive cache admission before the durable security mutation can rely on it; uncertainty is fail-closed;
- crash after PostgreSQL authority commit but before Redis finalization leaves the affected scope non-authorizing and the durable reconciliation obligation eventually converges the cache to the committed generation/state;
- Redis failure while attempting the pre-commit fence cannot be followed by a PostgreSQL authority commit while stale Redis remains admitted for positive security reads; fleet-wide old-generation exclusion wins first or the mutation fails closed;
- a partial Redis partition in which BFF A cannot reach the cache but BFF B can still reach an older positive generation does not permit A to commit the security mutation unless the old cache generation is fenced from positive admission across the serving fleet;
- a fenced scope cannot be treated as an ordinary miss and cannot be overwritten/bypassed by a concurrent stale cache-fill, including fills for session keys absent when a broader membership/tenant scope fence was installed;
- concurrent revocations/permission changes using the same expected durable generation produce one winning transition and stable retry identity rather than last-write-wins cache corruption;
- Redis-only outage with PostgreSQL healthy does not cause an uncontrolled PostgreSQL thundering herd beyond the accepted `OPEN-REL-008` bulkhead;
- Redis recovery, failover or restore with deliberately stale cache contents does not serve those positives before the new recovery-admission generation/reconciliation barrier completes and current expected-admission evidence is distributed;
- PostgreSQL SoR outage still fails closed for security-sensitive operations when current durable authority cannot be established;
- a lagging Redis replica cannot serve pre-revocation authority past the accepted currentness bound;
- PITR/failover/restore of either store cannot resurrect an already-retired session merely because cache state rolled back farther than durable authority; recovery re-establishes a new admitted cache generation and reconciles from current durable authority before positive admission resumes;
- `OPEN-REL-031.A` durable topology/ownership, `OPEN-REL-015` cache topology/invalidation/epoch mechanism and `OPEN-REL-008` bypass bulkhead mechanics are selected/conformed under their own source ownership rather than collapsed into this record.

## Exit / revisit conditions

Revisit if `OPEN-REL-031.A` evidence shows the selected PostgreSQL ownership/topology is untenable, if `OPEN-REL-015` cannot provide the required fleet-wide admission/fencing continuity without unacceptable cost, if measured transition/fence/reconciliation cost violates the accepted security/latency envelope, or if future residency requirements force session-store repartitioning.
