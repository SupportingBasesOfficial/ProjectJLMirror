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

| Vector | Trigger and scope | Required behavior | Isolation and convergence evidence | Blocker |
|---|---|---|---|---|
| `FV-CP-001` | Control Plane unavailable while a cell serves previously admitted traffic. | The cell MAY continue only within an unexpired, generation-bound authority lease; new placement, authority expansion, and policy relaxation SHALL stop. | Stable traffic remains tenant-scoped; lease expiry fences uncertain authority; reconciliation precedes resumed control mutations. | `RB-REL-001` |
| `FV-CP-002` | Control Plane data is stale, partial, or contradictory. | Staleness SHALL be explicit; consumers SHALL reject incompatible generations and fail closed for authority-sensitive operations. | No stale writer or stale placement becomes authoritative; evidence identifies source generation and observation time. | `RB-REL-001` |
| `FV-CELL-001` | Cell system of record is unavailable or read-only. | Truth-dependent mutations SHALL stop or enter an explicitly safe queued mode; cached or derived state SHALL NOT invent success. | Tenant boundaries remain intact; queued work has bounded admission and resumes through reconciliation. | `RB-REL-002` |
| `FV-CELL-002` | Database failover or replacement overlaps an old writer. | Exactly one valid writer generation SHALL remain; old writers SHALL be fenced before authority resumes. | Split-brain attempts are rejected; recovery proves generation monotonicity and ledger continuity. | `RB-REL-003` |
| `FV-SEC-001` | Authentication, authorization, revocation, or key authority cannot be reached or verified. | Privilege expansion and uncertain sensitive access SHALL fail closed; previously accepted bounded evidence MAY be used only under its contract. | Revocations and tenant scope are preserved or the operation is denied; no cache converts missing evidence into permission. | `RB-REL-004` |
| `FV-CACHE-001` | Shared or local cache becomes unavailable, inconsistent, or simultaneously cold. | Correctness SHALL survive cache loss; refill SHALL be bounded and stampede-resistant; negative and authorization caches SHALL preserve their semantics. | Origin pressure stays within declared envelopes; stale entries never broaden authority. | `RB-REL-005` |
| `FV-SECRET-001` | Secret/configuration source is unavailable during bootstrap or rotation. | New workloads SHALL NOT start with missing or unverified material; existing workloads MAY continue only within accepted lease and rotation semantics. | Old and new generations cannot both grant unintended authority; secrets remain absent from payloads, logs, and ordinary state. | `RB-REL-006` |
| `FV-EXT-001` | External provider is slow, unavailable, or rate-limiting. | Deadlines, concurrency isolation, circuit state, and backpressure SHALL bound consumption; unrelated providers and tenants SHALL remain serviceable. | Retry demand does not amplify the outage; recovery is gradual and observable. | `RB-REL-007` |
| `FV-EXT-002` | Provider may have accepted an effect but the response is lost or indeterminate. | The operation SHALL enter `ambiguous`; blind retry is forbidden unless the accepted contract proves semantic safety. | Stable operation identity drives inquiry or reconciliation; duplicate external effects are detected or prevented. | `RB-REL-008` |
| `FV-ASYNC-001` | Broker is unavailable while durable local commits continue. | Outbox-backed work remains durable; publication admission is bounded by backlog capacity and SHALL NOT be reported as externally delivered. | Tenant/cell ordering and identity remain stable; drain does not starve live recovery-critical work. | `RB-REL-009` |
| `FV-ASYNC-002` | Consumer crashes after committing an effect and before acknowledgement. | Redelivery SHALL converge through inbox/effect identity; acknowledgement SHALL NOT precede the durable completion boundary. | Re-execution does not duplicate semantic effects; lease recovery fences stale consumers. | `RB-REL-010` |
| `FV-ASYNC-003` | Same message identity arrives with conflicting content or authority context. | Processing SHALL stop for that item and record a conflict; first-seen content SHALL NOT be silently overwritten. | Quarantine evidence preserves both observations without leaking tenant data; unrelated work proceeds. | `RB-REL-010` |
| `FV-ASYNC-004` | Poison or permanently invalid message repeatedly fails. | Retry SHALL terminate at a classified boundary; the item enters quarantine with bounded redrive authority. | Partition/tenant impact is bounded; correction or redrive retains immutable identity and audit. | `RB-REL-011` |
| `FV-OVER-001` | A dependency outage induces retry amplification. | Aggregate attempt budgets, jitter, circuits, and admission control SHALL prevent a retry storm. | Recovery probes are bounded; original and retry demand are separately attributable. | `RB-REL-012` |
| `FV-OVER-002` | One tenant or workload class consumes disproportionate capacity. | Fairness and bulkhead contracts SHALL protect other tenants and critical work; excess work is throttled, deferred, or rejected explicitly. | Per-tenant/cell queues and concurrency expose containment; no global pool bypass exists. | `RB-REL-013` |
| `FV-OVER-003` | Replay, backfill, or migration competes with live traffic. | Live and recovery-critical reservations SHALL be preserved; maintenance work SHALL yield or pause without losing its checkpoint. | Work class attribution and checkpoint evidence prove bounded interference and resumability. | `RB-REL-013` |
| `FV-RT-001` | Realtime transport disconnects, duplicates, or reorders delivery. | Clients SHALL reconnect using accepted cursors and resynchronize from authoritative state; realtime SHALL remain a notification optimization. | No notification establishes business truth; tenant, subject, and placement generations are revalidated. | `RB-REL-014` |
| `FV-RT-002` | Realtime session retains stale authorization or placement. | Delivery SHALL stop or reauthorize at the defined boundary; stale sessions SHALL NOT cross tenant/cell generations. | Revocation/relocation evidence fences the old session and permits deterministic resync. | `RB-REL-014` |
| `FV-WH-001` | A webhook destination is slow or unavailable. | Destination-scoped concurrency, retry eligibility, and backlog limits SHALL isolate the failure. | Other destinations and tenants remain serviceable; attempts remain immutable and auditable. | `RB-REL-015` |
| `FV-WH-002` | Webhook response is lost while destination generation changes. | Delivery SHALL preserve immutable identity and target generation; uncertainty SHALL NOT be erased by retargeting. | Inquiry/redrive follows Product-approved semantics; old and new destinations are not conflated. | `RB-REL-015` |
| `FV-ART-001` | Object/artifact storage is unavailable or returns mismatched metadata. | Artifact-dependent completion SHALL not be claimed; hash, length, tenant, and generation SHALL be verified before authority is granted. | Inline fallbacks SHALL NOT bypass size, policy, or revocation constraints. | `RB-REL-016` |
| `FV-ART-002` | Erasure, revocation, or quarantine races with upload/download/streaming. | Governance state SHALL win; stale capabilities and in-flight continuations SHALL be rejected at accepted boundaries. | Recovery cannot resurrect revoked authority or erased content; audit remains continuous. | `RB-REL-016` |
| `FV-TEL-001` | Telemetry path is saturated or unavailable. | Business correctness SHALL continue without telemetry as authority; local buffering, shedding, and fail-closed audit boundaries follow accepted classifications. | Telemetry loss is explicit and bounded; tenant data and secrets are not exposed by fallback paths. | `RB-REL-017` |
| `FV-REC-001` | Tenant-scoped point-in-time recovery restores an earlier snapshot. | The scope remains non-authoritative until `(R,F]` reconciliation, revocation, erasure, hold, and generation checks complete. | Other tenants remain isolated; restored writers are fenced until convergence evidence is accepted. | `RB-REL-018` |
| `FV-REC-002` | Whole-cell recovery restores state behind external facts. | The cell SHALL start quarantined and non-authoritative; source/effect ledgers and control-plane placement are reconciled before admission. | Old cell/runtime generations cannot write; recovery evidence is scope-complete. | `RB-REL-018` |
| `FV-REC-003` | The recovery fact set `F` is incomplete or contradictory. | Missing evidence SHALL produce uncertainty, not presumed absence; affected operations stay blocked or quarantined. | Completion requires authoritative evidence or an explicitly accepted compensating decision. | `RB-REL-018` |
| `FV-REL-001` | Tenant/cell relocation overlaps active writes, jobs, streams, and events. | Source generations are fenced, durable work is handed off or reconciled, and identities remain topology-independent. | No dual authority or cross-cell identity rewrite occurs; new placement proves readiness before admission. | `RB-REL-019` |
| `FV-PRIV-001` | Privileged, parser, automation, admin, or migration runtime is saturated or fails containment. | Its dedicated trust envelope and concurrency budget SHALL contain the failure; ordinary API/worker authority SHALL not inherit its privileges. | Egress, filesystem, secret, and tenant-scope tests prove separation. | `RB-REL-020` |
| `FV-COMP-001` | Mixed reliability-profile versions coexist during a rolling change. | The combination SHALL be classified and declared compatible before rollout; stricter safety semantics SHALL not be silently weakened. | Evidence covers producer/consumer/runtime combinations and rollback or forward-recovery behavior. | `RB-REL-021` |

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
| `RB-REL-006` | Bootstrap/rotation can use missing, stale, leaked, or simultaneously authoritative secret/config generations. |
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

## 8. Phase 11 acceptance use

Phase 11 may pass design acceptance only when every vector has a normative expected outcome, isolation boundary, convergence condition, evidence requirement, and blocker mapping. Execution results remain future evidence and SHALL be tracked by the appropriate implementation, release, and Operations gates.
