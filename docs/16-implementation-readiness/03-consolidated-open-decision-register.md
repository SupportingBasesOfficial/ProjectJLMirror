# Implementation Readiness — Consolidated OPEN Decision Register

**Status:** proposed gate baseline

## Purpose

This readiness overlay does not rewrite source OPEN registries. It assigns the roadmap closure class used by the Implementation Readiness Gate and records whether a source OPEN has been semantically satisfied by a later accepted phase, remains open as a replaceable implementation choice, blocks production only, is Product-gated, or is intentionally deferred.

If a source OPEN ID is missing from this register, the gate fails closed.

## Closure classes

```text
C1 must_close_before_implementation
C2 evidence_generating_implementation_decision
C3 must_close_before_production_eligibility
C4 product_gated
C5 intentionally_deferred_future_capability
```

A class is about the unresolved decision, not about the importance of the fixed invariant. C2 technology may be replaced only while preserving all fixed semantics.

## Phase 09 overlay

| IDs | Class | Readiness disposition |
|---|---|---|
| `OPEN-API-001` | C1 | BLOCKER for `impl.identity-bff@1`; concrete human/machine authentication/token profile must be accepted before protected identity implementation |
| `OPEN-API-002` | C2 | cookie/CSRF/origin implementation profile chosen under Phase 09 fixed security semantics |
| `OPEN-API-003` | C5 | deferred with `impl.realtime@1`; cannot appear until that slice is separately activated |
| `OPEN-API-004` | C3 | numeric request/page/bulk limits require benchmark/abuse evidence before production |
| `OPEN-API-005` | C3 | numeric idempotency retention; recovery semantics already fixed |
| `OPEN-API-006` | C3 | support/deprecation duration requires Product/support evidence |
| `OPEN-API-007..010` | C2 | content-processing, artifact optimization, tracing and contract-tooling mechanisms |
| `OPEN-API-011` | C4 | official public SDK scope requires accepted Product need |
| `OPEN-API-012..013` | C2 | rate-limit/problem representation profiles |
| `OPEN-API-014` | C4 | public projection resource families require Product authority |
| `OPEN-API-015` | C5 | privileged direct-query surface deferred from initial implementation wave |
| `OPEN-API-016` | C4 | endpoint-specific contract exists only for accepted Product/domain use cases; no endpoint may be invented by implementation |
| `OPEN-API-017` | C3 | cache freshness numerics/tuning before production of applicable surfaces |
| `OPEN-API-018` | C4 | browser-active inline artifact rendering requires explicit Product need and threat-model acceptance |
| `OPEN-API-019` | C5 | protected cursor mechanism closes with the first authorized slice that needs such continuation; no address/history-visible protected token default |
| `OPEN-API-020..021` | C2 | filename and concrete HTTP ingress/profile implementation under fixed canonicalization/security semantics |
| `OPEN-API-022` | C4 | provider callback trust profile closes per accepted provider/Product integration before that adapter is implemented |

## Phase 10 overlay

| IDs | Class | Readiness disposition |
|---|---|---|
| `OPEN-EVT-001..005` | C2 | transport/serialization/catalog/version/topology mechanisms are replaceable under fixed event semantics |
| `OPEN-EVT-006..007` | C3 | partition/retry numerics require capacity/fault evidence |
| `OPEN-EVT-008..018` | C2 | ack, quarantine, equivalence store, outbox, generation representation, replay reader, service auth implementation, KMS and trace mechanism; fixed semantics remain authoritative |
| `OPEN-EVT-019` | C3 | realtime transport numerics before production |
| `OPEN-EVT-020` | C5 | resume/cursor capability deferred with realtime slice |
| `OPEN-EVT-021` | C4 | outbound webhook Product scope |
| `OPEN-EVT-022` | C2 | webhook signature/auth mechanism after Product applicability exists |
| `OPEN-EVT-023` | C4 | Product-specific destination change/cancel/reissue policy blocks webhook implementation until Product enablement |
| `OPEN-EVT-024..025` | C2 | egress and recovery-generation/reconciliation mechanisms |
| `OPEN-EVT-026..028` | C3 | retention/residency/deprecation production decisions |

## Phase 11 overlay

Phase 11 already assigned roadmap classes. This gate preserves them and records downstream closure:

| ID | Source class | Readiness disposition |
|---|---|---|
| `OPEN-REL-013` | C1 | SATISFIED SEMANTICALLY by accepted Phase 13 generation/fence contracts; concrete storage/propagation mechanism remains `OPEN-PRT-039` and is treated below |
| `OPEN-REL-026` | C1 | SATISFIED by accepted Phase 12 signal/health/SLI/alert semantics |
| `OPEN-REL-027` ownership-semantic portion | C1 | SATISFIED by accepted Phase 15 exact ownership/runbook/escalation catalog; staffing remains C3 |
| `OPEN-REL-018` | C4 | webhook Product-gated |
| all Phase 11 C2 rows | C2 | mechanism/spike choices remain subordinate to accepted reliability profile |
| all Phase 11 C3 rows | C3 | production numerics/evidence remain production blockers, not implementation-readiness claims |

`OPEN-REL-030` is C2 but specifically blocks implementation of `impl.customer-telemetry@1` until the durable acceptance/projection mechanism is selected and conformed.

## Phase 12 overlay

| IDs | Class |
|---|---|
| `OPEN-OBS-001..005`, `OPEN-OBS-010`, `OPEN-OBS-020`, `OPEN-OBS-022..023`, `OPEN-OBS-025`, `OPEN-OBS-028..029`, `OPEN-OBS-031..032`, `OPEN-OBS-034`, `OPEN-OBS-036` | C2 |
| `OPEN-OBS-006..009`, `OPEN-OBS-011..019`, `OPEN-OBS-021`, `OPEN-OBS-026..027`, `OPEN-OBS-030`, `OPEN-OBS-033` | C3 |
| `OPEN-OBS-024`, `OPEN-OBS-035`, `OPEN-OBS-037` | C4 |

`OPEN-OBS-037` remains upstream Product authority. Runtime/config/catalog presence cannot close it.

## Phase 13 overlay

| IDs | Class | Notes |
|---|---|---|
| `OPEN-PRT-008`, `OPEN-PRT-011` | C1 | workload/service authentication protocol/issuer details are trust-boundary decisions required before protected internal service implementation |
| `OPEN-PRT-039` | C1 | concrete runtime generation/fence storage/propagation is required before authoritative failover/replacement paths are implemented |
| `OPEN-PRT-001`, `OPEN-PRT-003..007`, `OPEN-PRT-009..020`, `OPEN-PRT-027..028`, `OPEN-PRT-030..038`, `OPEN-PRT-040` | C2 | replaceable runtime/platform mechanisms under fixed profiles |
| `OPEN-PRT-002`, `OPEN-PRT-021..026`, `OPEN-PRT-029` | C3 | physical topology/count/sizing/scaling/freshness numerics before production |

## Phase 14 overlay

| IDs | Class |
|---|---|
| `OPEN-RLS-001..020`, `OPEN-RLS-025..029`, `OPEN-RLS-031..039` | C2 |
| `OPEN-RLS-021..024`, `OPEN-RLS-030` | C3 |

No Phase 14 tool choice may weaken source trust, one-artifact promotion, release-target fencing, config-equivalence, runtime artifact verification or rollback/forward-recovery semantics.

## Phase 15 overlay

| IDs | Class |
|---|---|
| `OPEN-OPS-001..002`, `OPEN-OPS-006`, `OPEN-OPS-008..013`, `OPEN-OPS-016`, `OPEN-OPS-019..030`, `OPEN-OPS-034`, `OPEN-OPS-036`, `OPEN-OPS-038..040` | C2 |
| `OPEN-OPS-003..005`, `OPEN-OPS-007`, `OPEN-OPS-014..015`, `OPEN-OPS-017..018`, `OPEN-OPS-031..033`, `OPEN-OPS-035`, `OPEN-OPS-037` | C3 |

Phase 15 logical ownership, runbook semantics, dual-control applicability selector, recovery admission and residual-obligation semantics are already fixed and are not OPEN implementation discretion.

## Current C1 readiness blockers

At this gate baseline, exactly these unresolved class-1 implementation decisions remain:

```text
OPEN-API-001
OPEN-PRT-008
OPEN-PRT-011
OPEN-PRT-039
```

The gate SHALL NOT become `READY_TO_IMPLEMENT` until these are closed through accepted decision records or their target implementation slices are removed from the authorized initial implementation scope by accepted Product/architecture authority.

## Closure evidence rule

A C1 closure must update this register and the owning source authority where necessary. A C2 selection must produce a bounded decision/spike record and conformance evidence before becoming canonical. A C3 remains a production blocker. C4/C5 capabilities stay absent from implementation unless their governing authority deliberately changes their class/state.
