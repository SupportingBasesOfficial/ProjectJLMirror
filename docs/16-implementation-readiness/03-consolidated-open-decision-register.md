# Implementation Readiness — Consolidated OPEN Decision Register

**Status:** proposed gate baseline; post-D2 operational state reconciled by `18-d2-track-b-acceptance-propagation.md`

## Purpose

This readiness overlay does not rewrite source OPEN registries. It assigns the roadmap closure class used by the Implementation Readiness Gate and records whether a source OPEN has been semantically satisfied by a later accepted phase, remains open as a replaceable implementation choice, blocks production only, is Product-gated, or is intentionally deferred.

If a source OPEN ID or an explicitly split subdecision is missing, multiply classified or silently collapsed, the gate fails closed.

## Closure classes

```text
C1 must_close_before_implementation
C2 evidence_generating_implementation_decision
C3 must_close_before_production_eligibility
C4 product_gated
C5 intentionally_deferred_future_capability
```

A class is about the unresolved decision, not about the importance of the fixed invariant. C2 technology may be replaced only while preserving all fixed semantics.

Where a source OPEN contains subdecisions with different closure gates, this overlay splits them as `.A`, `.B`, etc. The source OPEN ID remains the lineage anchor; the suffix is readiness bookkeeping, not a new upstream authority.

## Phase 09 overlay — `OPEN-API-001..022`

| IDs | Class | Readiness disposition |
|---|---|---|
| `OPEN-API-001` | C1 | PROPOSED SATISFIED by IR-D-001 + IR-D-002 and the Phase 09 closure record; closes only if this gate is accepted |
| `OPEN-API-002` | C2 | cookie/CSRF/origin implementation profile under fixed Phase 09 browser security semantics |
| `OPEN-API-003` | C5 | realtime ticket presentation deferred with `impl.realtime@1` |
| `OPEN-API-004..006` | C3 | request/page/bulk limits, idempotency retention and support/deprecation durations require evidence before production |
| `OPEN-API-007..010` | C2 | content-processing, artifact optimization, tracing and contract-tooling mechanisms |
| `OPEN-API-011` | C4 | official public SDK scope requires Product authority |
| `OPEN-API-012..013` | C2 | rate-limit/problem representation profiles |
| `OPEN-API-014` | C4 | public projection resource families require Product authority |
| `OPEN-API-015` | C5 | privileged direct-query surface deferred from initial wave |
| `OPEN-API-016` | C4 | endpoint-specific contracts exist only for accepted Product/domain use cases |
| `OPEN-API-017` | C3 | cache freshness/tuning numerics before production of applicable surfaces |
| `OPEN-API-018` | C4 | active browser-inline artifact profile requires explicit Product need + threat-model acceptance |
| `OPEN-API-019` | C5 | protected cursor mechanism deferred until an authorized slice requires it; no protected URL-history default |
| `OPEN-API-020..021` | C2 | filename and concrete HTTP-ingress implementation under fixed canonicalization/security semantics |
| `OPEN-API-022` | C4 | provider callback trust profile closes per accepted provider/Product integration before that adapter is implemented |

## Phase 10 overlay — `OPEN-EVT-001..028`

| IDs | Class | Readiness disposition |
|---|---|---|
| `OPEN-EVT-001..005` | C2 | transport, serialization, catalog, version syntax and physical topology mechanisms |
| `OPEN-EVT-006..007` | C3 | partition/retry numeric profiles before production |
| `OPEN-EVT-008..015` | C2 | ack/lease, quarantine, bounds mechanism, equivalence store, outbox, producer-generation representation, replay/history and historical-reader mechanisms |
| `OPEN-EVT-016` | C2 | broker/service credential adaptation remains C2; IR-D-002 supplies the canonical internal workload-authentication baseline and vendor credentials remain derived |
| `OPEN-EVT-017..018` | C2 | message KMS/historical-verifier and trace propagation mechanisms |
| `OPEN-EVT-019` | C3 | realtime transport/buffer/session numerics before production |
| `OPEN-EVT-020` | C5 | realtime resume/cursor profile deferred with realtime slice |
| `OPEN-EVT-021` | C4 | outbound webhook Product scope |
| `OPEN-EVT-022` | C2 | webhook signature/auth mechanism after Product applicability exists |
| `OPEN-EVT-023` | C4 | Product-specific destination-generation cancel/fence/quarantine/reissue behavior before webhook implementation |
| `OPEN-EVT-024..025` | C2 | webhook egress and recovery-generation/reconciliation mechanisms |
| `OPEN-EVT-026..028` | C3 | retention/replay/quarantine, residency and deprecation production horizons |

## Phase 11 overlay — exact source rows `OPEN-REL-001..031`

Phase 11 already assigned a primary roadmap class. This gate preserves those classes and explicitly splits source rows whose own closure text gives different gates to mechanism vs numeric/Product subdecisions.

| ID/subdecision | Class | Readiness disposition |
|---|---|---|
| `OPEN-REL-001` | C2 | Control Plane continuity mechanism/lease distribution/cached-authority implementation |
| `OPEN-REL-002` | C3 | staleness/lease horizons and availability topology before production |
| `OPEN-REL-003.A` | C2 | database HA/election/fencing mechanism selection |
| `OPEN-REL-003.B` | C3 | replica counts and production HA/topology numerics |
| `OPEN-REL-004` | C3 | region topology/failover geography/capacity before production |
| `OPEN-REL-005..006` | C3 | deadline/retry numeric profiles before production |
| `OPEN-REL-007` | C2 | circuit algorithm only for profiles whose accepted circuit selector is applicable |
| `OPEN-REL-008.A` | C2 | bulkhead/pool/adaptive-control mechanism |
| `OPEN-REL-008.B` | C3 | concurrency/reservation numeric sizes before production |
| `OPEN-REL-009` | C3 | backlog size/age/storage thresholds before production |
| `OPEN-REL-010.A` | C2 | scheduling/fairness mechanism and non-Product differentiation implementation |
| `OPEN-REL-010.B` | C4 | premium/differentiated Product tiers, if any, require Product authority before differentiated behavior |
| `OPEN-REL-011` | C3 | provider-specific timeout/retry/concurrency/reconciliation numerics/capability evidence before provider production eligibility |
| `OPEN-REL-012.A` | C2 | broker/outbox/drain product and mechanism selection |
| `OPEN-REL-012.B` | C3 | partition/retention/lag production numerics |
| `OPEN-REL-013` | C1 | semantic requirement satisfied by accepted Phase 13; concrete mechanism closes through proposed IR-D-003/`OPEN-PRT-039` closure on this gate |
| `OPEN-REL-014..015` | C2 | reconciliation tooling and cache/replay implementation mechanisms |
| `OPEN-REL-016.A` | C2 | secret/KMS/bootstrap/rotation/historical-verifier mechanism |
| `OPEN-REL-016.B` | C3 | lease/rotation-overlap numeric horizons before production |
| `OPEN-REL-017` | C3 | realtime session/buffer/reconnect production numerics |
| `OPEN-REL-018` | C4 | outbound webhook capability/families Product-gated |
| `OPEN-REL-019.A` | C2 | object/artifact store/capability/streaming mechanism |
| `OPEN-REL-019.B` | C3 | availability/production sizing objectives where numeric |
| `OPEN-REL-020` | C3 | telemetry buffer/loss/checkpoint/retention/cardinality/cost production envelopes; customer durable mechanism owned separately by `OPEN-REL-030` |
| `OPEN-REL-021` | C2 | fault/chaos tooling and safe execution environment |
| `OPEN-REL-022..023` | C3 | capacity/availability/recovery objectives and rearchitecture numerics before production |
| `OPEN-REL-024` | C2 | specialized/privileged runtime isolation mapping/extraction mechanism |
| `OPEN-REL-025` | C3 | idempotency/inbox/outbox/equivalence/recovery evidence retention horizons before production |
| `OPEN-REL-026` | C1 | SATISFIED by accepted Phase 12 signal/health/SLI/alert semantics |
| `OPEN-REL-027.A` | C1 | SATISFIED by accepted Phase 15 logical operational ownership/runbook/escalation semantics |
| `OPEN-REL-027.B` | C3 | physical staffing/on-call coverage before production |
| `OPEN-REL-028` | C2 | deployment/rollout/recovery mechanism satisfied semantically by Phase 14; concrete product remains replaceable C2 |
| `OPEN-REL-029.A` | C2 | configuration store/distribution/schema/rollout mechanism |
| `OPEN-REL-029.B` | C3 | last-known-good/convergence numeric horizons before production |
| `OPEN-REL-030` | C2 | **ACCEPTED / selected + conformed for the Track B profile merged by PR #40 at `main@2ffec007d7dff32e0a45116b0bc875d5c2743b12`; no longer blocks `impl.customer-telemetry@1` eligibility. Production capacity/numerics remain separately owned by `OPEN-REL-020`.** |
| `OPEN-REL-031.A` | C2 | identity/session-authority durable-store topology and ownership (control-plane-owned vs. its own tier), mechanism selection |
| `OPEN-REL-031.B` | C3 | identity/session-authority RPO/RTO and failover numerics before production eligibility |

No Phase 11 source row is implicitly covered by “all C2/C3 rows”; every ID is enumerated here.

### Post-D2 `OPEN-REL-030` authority boundary

The `OPEN-REL-030` row remains class C2 as lineage/classification history, but its first-Monitoring-vertical decision state is now accepted rather than unresolved. The accepted profile is exactly the bounded profile recorded under `implementation/d2-open-rel-030/*`; this propagation does not authorize arbitrary Timescale/PostgreSQL mechanisms outside that profile and does not close C3 production envelopes.

## Phase 12 overlay — `OPEN-OBS-001..037`

| IDs | Class |
|---|---|
| `OPEN-OBS-001..005`, `OPEN-OBS-010`, `OPEN-OBS-020`, `OPEN-OBS-022..023`, `OPEN-OBS-025`, `OPEN-OBS-028..029`, `OPEN-OBS-031..032`, `OPEN-OBS-034`, `OPEN-OBS-036` | C2 |
| `OPEN-OBS-006..009`, `OPEN-OBS-011..019`, `OPEN-OBS-021`, `OPEN-OBS-026..027`, `OPEN-OBS-030`, `OPEN-OBS-033` | C3 |
| `OPEN-OBS-024`, `OPEN-OBS-035`, `OPEN-OBS-037` | C4 |

`OPEN-OBS-037` remains upstream Product authority. Runtime/config/catalog presence cannot close it.

## Phase 13 overlay — `OPEN-PRT-001..040`

| IDs/subdecision | Class | Readiness disposition |
|---|---|---|
| `OPEN-PRT-008.A` | C1 | protocol/trust-shape PROPOSED SATISFIED by IR-D-002 and Phase 13 closure record; closes only if this gate is accepted |
| `OPEN-PRT-008.B` | C2 | concrete workload-identity issuer/attestation backend remains OPEN and replaceable |
| `OPEN-PRT-011` | C1 | service-authentication protocol PROPOSED SATISFIED by IR-D-002; closes only if this gate is accepted |
| `OPEN-PRT-039` | C1 | concrete fence storage/propagation PROPOSED SATISFIED by IR-D-003; closes only if this gate is accepted |
| `OPEN-PRT-001`, `OPEN-PRT-003..007`, `OPEN-PRT-009..010`, `OPEN-PRT-012..020`, `OPEN-PRT-027..028`, `OPEN-PRT-030..038`, `OPEN-PRT-040` | C2 | replaceable runtime/platform mechanisms under fixed profiles |
| `OPEN-PRT-002`, `OPEN-PRT-021..026`, `OPEN-PRT-029` | C3 | physical topology/count/sizing/scaling/freshness numerics before production |

The C2 range intentionally excludes `OPEN-PRT-011`; no source decision has two active readiness classes after the explicit `OPEN-PRT-008` split.

## Phase 14 overlay — `OPEN-RLS-001..039`

| IDs | Class |
|---|---|
| `OPEN-RLS-001..020`, `OPEN-RLS-025..029`, `OPEN-RLS-031..039` | C2 |
| `OPEN-RLS-021..024`, `OPEN-RLS-030` | C3 |

No Phase 14 tool choice may weaken source trust, one-artifact promotion, release-target fencing, config-equivalence, runtime artifact verification or rollback/forward-recovery semantics.

## Phase 15 overlay — `OPEN-OPS-001..040`

| IDs | Class |
|---|---|
| `OPEN-OPS-001..002`, `OPEN-OPS-006`, `OPEN-OPS-008..013`, `OPEN-OPS-016`, `OPEN-OPS-019..030`, `OPEN-OPS-034`, `OPEN-OPS-036`, `OPEN-OPS-038..040` | C2 |
| `OPEN-OPS-003..005`, `OPEN-OPS-007`, `OPEN-OPS-014..015`, `OPEN-OPS-017..018`, `OPEN-OPS-031..033`, `OPEN-OPS-035`, `OPEN-OPS-037` | C3 |

Phase 15 logical ownership, runbook semantics, dual-control applicability selector, recovery admission and residual-obligation semantics are already fixed and are not OPEN implementation discretion.

## C1 closure gate

The source C1 decisions not already satisfied by accepted downstream phases reduce to these exact subdecisions:

```text
OPEN-API-001
OPEN-PRT-008.A
OPEN-PRT-011
OPEN-PRT-039
```

This gate proposes explicit closures through IR-D-001/002/003 and the owning Phase 09/13 closure records.

```text
before this gate is accepted -> C1 closure status = PROPOSED / implementation remains blocked
after this exact gate is accepted -> remaining C1 count = 0
```

`OPEN-PRT-008.B` remains C2 and is **not** represented as closed by the C1 result.

Any material change to a C1 profile reopens the owning C1 subdecision through compatibility governance.

## Completeness / uniqueness invariant

For each source registry range:

```text
Phase 09  OPEN-API-001..022
Phase 10  OPEN-EVT-001..028
Phase 11  OPEN-REL-001..031
Phase 12  OPEN-OBS-001..037
Phase 13  OPEN-PRT-001..040
Phase 14  OPEN-RLS-001..039
Phase 15  OPEN-OPS-001..040
```

every source ID has exactly one active readiness disposition, except where the source decision is explicitly split into separately named subdecisions whose union covers the whole source question.

## Closure evidence rule

A C1 closure updates this register and the owning source authority where necessary. A C2 selection produces a bounded decision/spike record and conformance evidence before becoming canonical. A C3 remains a production blocker. C4/C5 capabilities stay absent from implementation unless their governing authority deliberately changes their class/state.

For the first Monitoring vertical, `OPEN-REL-030` now has that bounded C2 selection/conformance evidence through PR #40. Its accepted state does not imply Wave 4 implementation authorization; `18-d2-track-b-acceptance-propagation.md` owns that transition boundary.