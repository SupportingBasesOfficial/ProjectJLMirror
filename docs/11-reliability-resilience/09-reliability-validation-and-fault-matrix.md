# Phase 11 — Reliability Validation and Fault Matrix

Status: proposed baseline  
Authority: Phase 11 — Reliability & Resilience  
Normative terms: `SHALL`, `SHALL NOT`, `SHOULD`, `MAY`

## 1. Purpose

This document converts the Phase 11 reliability contracts into falsifiable fault vectors and release blockers. It defines what later implementation, release, and runtime evidence SHALL demonstrate; it does not claim that those demonstrations already exist.

## 2. Evidence levels

| Level | Meaning | Phase 11 result |
|---|---|---|
| `design_acceptance` | The invariant, expected behavior, owner, and required evidence are normatively defined. | Required now. |
| `implementation_conformance` | An implementation-specific test demonstrates conformance to the accepted contract. | Deferred to implementation. |
| `release_evidence` | A release candidate passes the applicable conformance, compatibility, security, and fault gates. | Deferred to Deployment and release governance. |
| `runtime_evidence` | Rehearsals and production-like observation demonstrate the property under realistic scale and failure. | Deferred to Operations and production eligibility. |

No `design_acceptance` result SHALL be represented as implementation, release, or runtime proof.

## 3. Fault-experiment contract

Every executable fault vector derived from this matrix SHALL declare:

- the capability, dependency, tenant/cell/generation scope, and affected workload class;
- the initial authoritative state and the observable evidence that proves it;
- the injected fault, duration control, maximum blast radius, abort condition, and cleanup path;
- the expected degradation mode, admission behavior, authority behavior, and convergence condition;
- forbidden outcomes, including cross-tenant impact, stale authority, duplicate external effects, and unbounded work;
- the evidence source, evidence owner, retention class, and reproducibility requirements;
- whether the vector is safe only in a dedicated environment or may later be admitted to a broader rehearsal;
- the OPEN decisions whose closure is necessary to execute the vector.

Fault injection SHALL NOT create new authority, bypass tenant isolation, expose secrets, or make production mutation permissible. Operational authorization for game days and production-like exercises belongs to Phase 15.

## 4. Canonical fault matrix

`Blocker` values refer to Section 7. A vector is not passed by absence of evidence.

| Vector | Trigger and scope | Required behavior | Explicit forbidden outcomes | Isolation and convergence evidence | Blocker |
|---|---|---|---|---|---|
| `FV-CP-001` | Control Plane unavailable while a cell serves previously admitted traffic. | Continue only within an unexpired, generation-bound authority lease; topology/authority expansion stops. | Unbounded autonomy; new placement; stale deny override; cross-cell reroute without authority. | Tenant-scoped stable traffic; lease expiry fences uncertainty; reconciliation precedes control mutations. | `RB-REL-001` |
| `FV-CP-002` | Control Plane data is stale, partial, or contradictory. | Expose staleness, reject incompatible generations and fail closed for authority-sensitive operations. | Treating newest arrival as authoritative; stale writer/placement admission; contradiction collapsed to absence. | Source generation/time recorded; stale placement and writer attempts rejected. | `RB-REL-001` |
| `FV-CELL-001` | Cell system of record is unavailable or read-only. | Stop truth-dependent mutation or use an explicitly safe bounded queued mode; never invent success. | Acknowledged uncommitted mutation; cache-as-truth; unbounded queue; spill across cells/tenants. | Tenant boundaries intact; admission bounded; queued work reconciles before resume. | `RB-REL-002` |
| `FV-CELL-002` | Database failover or replacement overlaps an old writer. | Preserve exactly one valid writer generation and fence the old writer before authority resumes. | Dual write authority; last-write-wins split-brain repair; generation regression; ledger discontinuity. | Split-brain attempts rejected; generation monotonicity and ledgers proven. | `RB-REL-003` |
| `FV-SEC-001` | Authentication, authorization or revocation authority cannot be reached or verified. | Fail closed for privilege expansion and uncertain sensitive access; use bounded local evidence only under its accepted contract. | Missing evidence as permission; stale positive override of deny/revocation; tenant/scope widening. | Revocation and tenant scope preserved or access denied; cache cannot grant authority. | `RB-REL-004` |
| `FV-CACHE-001` | Shared/local cache is unavailable, inconsistent or simultaneously cold. | Preserve correctness, bound refill and prevent stampede; retain negative/authorization semantics. | Stale authority expansion; origin collapse; cross-tenant key collision; cache presence as truth. | Origin pressure bounded; tenant/version keys and fallback concurrency verified. | `RB-REL-005` |
| `FV-SECRET-001` | Secret/key authority is unavailable during bootstrap or rotation. | Reject unverified startup; continue existing use only within accepted lease/rotation semantics; no plaintext fallback. | Default/plaintext secret; simultaneous unintended key generations; secret in logs/payloads/state; revocation bypass. | Namespace/identity isolation and current rotation/crypto-erasure state proven. | `RB-REL-006` |
| `FV-CONFIG-001` | Configuration is malformed, contradictory, untrusted or partially rolled out. | Validate schema/authority/scope/generation; admit only declared compatible combinations; stop unsafe affected behavior. | Partial rollout treated as globally complete; unknown/invalid field accepted; tenant/cell scope crossover; old generation silently winning. | Per-target generation and validation evidence; incompatible targets fenced; one accepted disposition established. | `RB-REL-023` |
| `FV-CONFIG-002` | Restart, failover or restore presents older/missing configuration while later governance facts exist. | Use verified last-known-good only where permitted; otherwise quarantine and reconcile configuration through `(R,F]`. | Rollback resurrecting revoked authority, retired source, erased access or unsafe retry; missing config as permissive default. | Restore boundary, config generations, target coverage and later governance facts reconciled before admission. | `RB-REL-023` |
| `FV-EXT-001` | External provider is slow, unavailable or rate-limiting. | Bound consumption with deadlines, concurrency isolation, circuits and backpressure. | Retry storm; shared-pool exhaustion; cross-provider/tenant propagation; provider identity becoming domain identity. | Retry/original demand attributed; recovery gradual; unrelated scopes remain serviceable. | `RB-REL-007` |
| `FV-EXT-002` | Provider may have accepted an effect but response is lost/indeterminate. | Enter `ambiguous`; prohibit blind retry unless semantic safety is proven. | Ambiguity converted to absence/success; new operation identity; duplicate protected effect; evidence overwrite. | Stable operation identity drives inquiry/reconciliation and detects/prevents duplicates. | `RB-REL-008` |
| `FV-ASYNC-001` | Broker unavailable while durable local commits continue. | Preserve outbox work; bound publication admission; do not report external delivery. | Lost accepted intent; unbounded outbox; fabricated delivery; message identity rewrite during drain. | Tenant/cell ordering and identity stable; drain preserves live/recovery reservations. | `RB-REL-009` |
| `FV-ASYNC-002` | Consumer crashes after effect commit and before acknowledgement. | Redelivery converges through inbox/effect identity; acknowledgement remains after durable completion. | Duplicate semantic effect; acknowledgement before durability; stale lease executor; second identity. | Re-execution deduplicated; stale consumers fenced; outcome remains attributable. | `RB-REL-010` |
| `FV-ASYNC-003` | Same message identity arrives with conflicting content/authority context. | Stop that item and record immutable conflict without overwriting first-seen evidence. | Last-write-wins content; processing either variant; cross-tenant evidence disclosure; automatic identity reassignment. | Both observations preserved safely; unrelated work continues. | `RB-REL-010` |
| `FV-ASYNC-004` | Poison or permanently invalid message repeatedly fails. | Terminate retry at classified boundary and quarantine with bounded redrive authority. | Infinite retry; partition-wide stall; identity mutation; unaudited/bulk redrive bypass. | Tenant/partition impact bounded; correction/redrive preserves identity and audit. | `RB-REL-011` |
| `FV-OVER-001` | Dependency outage induces retry amplification. | Enforce aggregate attempts, jitter, circuits and admission control. | Multiplicative nested retries; synchronized probes; retry priority over original/critical work; unbounded elapsed work. | Original/retry demand separate; recovery probes bounded and gradual. | `RB-REL-012` |
| `FV-OVER-002` | One tenant/workload consumes disproportionate capacity. | Protect other tenants and critical work through fairness/bulkheads; throttle/defer/reject excess explicitly. | Global pool bypass; starvation; silent acceptance into unbounded backlog; tenant identity loss. | Per-tenant/cell queues and concurrency demonstrate containment. | `RB-REL-013` |
| `FV-OVER-003` | Replay, backfill or migration competes with live traffic. | Preserve live/recovery-critical reservations; yield/pause maintenance with checkpoint intact. | Live starvation; lost checkpoint; replay using ordinary priority; drain storm. | Work-class attribution, bounded interference and resumability proven. | `RB-REL-013` |
| `FV-RT-001` | Realtime transport disconnects, duplicates or reorders. | Reconnect using accepted cursors and resynchronize from authoritative state; realtime remains advisory. | Notification as business truth; unbounded replay; stale cursor accepted as authority; cross-tenant topic delivery. | Tenant/subject/placement generations revalidated; authoritative resync converges. | `RB-REL-014` |
| `FV-RT-002` | Realtime session retains stale authorization or placement. | Stop or reauthorize at boundary; reject stale sessions across tenant/cell generations. | Revoked session continuing; old cell delivery after relocation; resume token restoring authority. | Revocation/relocation fences old session and deterministic resync succeeds. | `RB-REL-014` |
| `FV-WH-001` | Product-approved webhook destination is slow/unavailable. | Isolate by destination concurrency, retry eligibility and backlog bounds. | Cross-destination/tenant starvation; business rollback; unbounded attempts; secret/egress bypass. | Other scopes serviceable; attempts immutable and auditable. | `RB-REL-015` |
| `FV-WH-002` | Webhook response lost while destination generation changes. | Preserve immutable delivery identity and target generation; retain uncertainty. | Retargeting old obligation; ambiguity erased; retry against new destination; attempt history rewrite. | Inquiry/redrive follows Product contract; generations remain distinct. | `RB-REL-015` |
| `FV-ART-001` | Object storage unavailable or returns mismatched metadata/content. | Do not claim completion; verify hash, length, tenant and generation before authority. | Object presence as ready state; inline bypass of policy/size/revocation; guessed content; cross-tenant object use. | Metadata/object integrity and governance fence evidence agree. | `RB-REL-016` |
| `FV-ART-002` | Erasure/revocation/quarantine races with upload/download/stream. | Governance state wins; reject stale capabilities and continuations at accepted boundaries. | Revoked/erased content re-exposed; stale stream admitted; false erasure success; audit loss. | In-flight leases fenced/reconciled; governance and audit continuity proven. | `RB-REL-016` |
| `FV-TEL-001` | Telemetry path saturated or unavailable. | Keep telemetry non-authoritative; buffer/shed by class and fail closed at mandatory audit boundaries. | Fabricated completeness; business failure caused by optional telemetry; unbounded buffer/cardinality; secret/tenant leak. | Loss explicit/bounded; core isolation and data classification proven. | `RB-REL-017` |
| `FV-REC-001` | Tenant PITR restores an earlier snapshot. | Keep scope non-authoritative until `(R,F]`, revocation, erasure, hold and generation reconciliation. | Restored writer admission; later facts presumed absent; cross-tenant recovery impact; governance regression. | Other tenants isolated; writers fenced until scope-complete evidence. | `RB-REL-018` |
| `FV-REC-002` | Whole-cell recovery restores state behind external facts. | Start quarantined/non-authoritative; reconcile ledgers and Control Plane placement before admission. | Automatic serving after restore; old generation write; blind replay/redrive; later authority erased. | Old runtime/cell generations fenced; evidence covers complete cell scope. | `RB-REL-018` |
| `FV-REC-003` | Recovery fact set `F` is incomplete or contradictory. | Preserve uncertainty and block/quarantine affected operations until authoritative evidence/decision. | Missing as absence; guessed convergence; blind retry; partial evidence marked complete. | Evidence source/owner and unresolved scope remain explicit. | `RB-REL-018` |
| `FV-REL-001` | Tenant/cell relocation overlaps writes, jobs, streams and events. | Fence source generations; hand off/reconcile durable work; preserve topology-independent identities. | Dual authority; identity rewrite; lost work; stale source publication/session; target admission before readiness. | Target readiness and source fence proven across all active work classes. | `RB-REL-019` |
| `FV-PRIV-001` | Privileged/parser/automation/admin/migration runtime saturates or loses containment. | Contain through dedicated trust envelope and capacity; ordinary workers never inherit privileges. | Unrestricted credential/egress/filesystem; cross-tenant scope; shared-pool collapse; timeout assumed effect absence. | Privilege, egress, filesystem, secret and tenant-scope tests prove separation. | `RB-REL-020` |
| `FV-COMP-001` | Mixed reliability-profile versions coexist. | Admit only declared compatible combinations; never silently weaken stricter safety semantics. | Schema-only compatibility claim; unknown profile admitted; unsafe rollback; mixed writer/ack/retry semantics. | Producer/consumer/runtime combinations and rollback/forward recovery covered. | `RB-REL-021` |
| `FV-EVID-001` | Evidence is missing, misattributed, irreproducible, contradictory or claimed at a stronger level. | Reject the gate result; preserve negative/missing records and require correct profile/artifact/scope provenance. | Missing evidence as pass/N/A; level inflation; aggregate green hiding failed scope; mutable/unowned result. | Independent reproduction and exact version/scope attribution demonstrate honest disposition. | `RB-REL-022` |

## 5. Cross-cutting adversarial suites

### 5.1 Security and privacy

Every applicable vector SHALL be repeated with:

- forged tenant, subject, placement, source, and generation identities;
- stale authorization, revocation, and secret material;
- cross-tenant queue, cache, artifact, and reconciliation probes;
- log/payload inspection for secret or sensitive-data leakage;
- privilege-boundary checks for admin, migration, parser, automation, and recovery roles.

### 5.2 Capacity, performance, and cost

Every overload-sensitive vector SHALL measure multiple dimensions, not only request count: concurrency, queue age, bytes, storage growth, provider quota, fan-out, tenant skew, retry amplification, recovery work, and cost-attributable consumption. Numeric pass thresholds remain OPEN until accepted evidence and Product/business authority exist.

### 5.3 Verification and assurance

Evidence SHALL be reproducible, attributable to the exact artifact/configuration/profile versions, and negative-test missing or contradictory evidence. A green aggregate result SHALL NOT hide a failed tenant, cell, generation, workload class, or dependency dimension.

## 6. Required coverage records

Each future implementation SHALL maintain a machine-checkable mapping:

```text
fault_vector
  -> normative_invariants
  -> component_and_owner
  -> implementation_test
  -> environment_and_fault_mechanism
  -> artifact_profile_versions
  -> evidence_location_and_retention
  -> result_by_tenant/cell/generation/workload_class
  -> release_blocker_disposition
```

`not_applicable` SHALL NOT be used to omit a mandatory artifact or overlay. A vector MAY be out of scope for a component only when the common artifact remains present and records a reviewed, evidence-backed non-applicability decision without weakening the phase gate.

## 7. Reliability release blockers

| Blocker | Condition that blocks conformance or release eligibility |
|---|---|
| `RB-REL-001` | Control-plane loss or staleness can broaden authority, bypass generations, or make cell behavior undefined. |
| `RB-REL-002` | Loss of transactional truth can produce acknowledged-but-uncommitted mutation or unbounded queued work. |
| `RB-REL-003` | Writer fencing and failover monotonicity are not demonstrated. |
| `RB-REL-004` | Missing or stale security evidence can grant access or hide revocation. |
| `RB-REL-005` | Cache loss can violate correctness, overload origins without bounds, or broaden authority. |
| `RB-REL-006` | Bootstrap/rotation can use missing, stale, leaked, or simultaneously authoritative secret/key generations. |
| `RB-REL-007` | Provider failure can exhaust shared resources or propagate across provider/tenant boundaries. |
| `RB-REL-008` | Ambiguous external effects can be blindly retried, silently treated as success/failure, or lose stable identity. |
| `RB-REL-009` | Broker outage can lose durable accepted work or allow unbounded local backlog. |
| `RB-REL-010` | Consumer redelivery can duplicate semantic effects, acknowledge before durability, or overwrite identity conflicts. |
| `RB-REL-011` | Poison work can retry forever or be redriven without bounded authority and immutable audit. |
| `RB-REL-012` | Retry amplification is not bounded across layers and callers. |
| `RB-REL-013` | Tenant skew or maintenance/recovery work can starve unrelated tenants or critical live work. |
| `RB-REL-014` | Realtime failure can establish business truth, retain stale authority, or prevent deterministic resync. |
| `RB-REL-015` | Webhook destination failure can cause cross-destination starvation, identity mutation, or unsafe retry. |
| `RB-REL-016` | Artifact unavailability or governance races can grant authority without verified content or resurrect revoked/erased data. |
| `RB-REL-017` | Telemetry failure can become business authority, leak data, hide mandatory audit loss, or consume unbounded capacity. |
| `RB-REL-018` | Recovered state can become authoritative before `(R,F]` reconciliation and governance continuity. |
| `RB-REL-019` | Relocation can create dual authority, stale writers, lost durable work, or topology-dependent public identity. |
| `RB-REL-020` | Privileged/specialized workloads are not isolated by authority, runtime envelope, egress, and capacity. |
| `RB-REL-021` | Mixed reliability-profile versions lack an explicit compatibility and recovery classification. |
| `RB-REL-022` | Required fault evidence is missing, irreproducible, unattributed, or represented at a stronger evidence level than it proves. |
| `RB-REL-023` | Configuration loss, corruption, contradiction, partial rollout, failover or restore can admit an untrusted/incompatible generation or resurrect later-withdrawn authority and policy. |

## 8. Phase 11 acceptance use

Phase 11 may pass design acceptance only when every vector has a normative expected outcome, explicit forbidden outcomes, isolation boundary, convergence condition, evidence requirement, and blocker mapping. Execution results remain future evidence and SHALL be tracked by the appropriate implementation, release, and Operations gates.
