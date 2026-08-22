# Phase 13 — Traceability and Evidence

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document binds Phase 13 runtime claims to accepted upstream authority and identifies downstream Phase 14/15/Implementation Readiness consumers and evidence obligations.

## Upstream traceability

| Accepted upstream authority | Phase 13 obligation |
|---|---|
| Architecture Overview | modular monolith + independent workers; Control Plane + cells; core runtime beyond edge-only limits; provider adapters; replaceable infrastructure products |
| ADR-015 | secret/key references, rotation/revocation, recovery-safe authority continuity |
| ADR-016 | general-purpose runtime for core execution; edge optional; workload/runtime specialization |
| ADR-017 / Phase 11 | failure/degradation, bulkheads, bounded retry/backlog, safe drain/resume, stable traffic under allowed Control Plane impairment |
| ADR-019 | multidimensional scaling, cell expansion and tenant relocation without logical contract rewrite |
| Control Plane and Cell Design | placement ownership, destination-cell admission, lifecycle/capacity/failure-boundary semantics |
| TenantContext / placement lifecycle | trusted logical tenant context, current placement, async re-resolution, relocation orchestrator authority |
| Security Requirements | network != trust, machine/human revocation, secret references, SSRF, isolated execution, admin privilege separation, recovery/governance continuity |
| Phase 09 API/BFF/realtime/provider contracts | public/internal ingress, general-purpose API boundary, current auth/placement, canonical callback semantics |
| Phase 10 async contracts | at-least-once delivery, durable responsibility, inbox/outbox/idempotency, replay/recovery, webhook obligations |
| Phase 11 reliability profiles | runtime failure/degradation and recovery behavior must be implementable without reinterpretation |
| Phase 12 observability profiles | runtime lifecycle/health/signals preserve accepted meanings; vendor health is adapter evidence only |
| Review and Assurance Governance | exact-state review, observer-only automation, separate merge authorization |

## Runtime role trace

The canonical role chain is:

```text
accepted capability/workload
 -> runtime profile
 -> workload principal
 -> isolation profile
 -> ingress/egress profile
 -> state ports
 -> Phase 11 failure/degradation profile
 -> Phase 12 health/signal evidence
 -> PRTV fault vectors
```

No runtime may omit a link by relying on vendor defaults.

## Cell lifecycle trace

```text
Control Plane placement authority
 -> cell lifecycle generation
 -> provisioning/validation/admission
 -> tenant + placement-version cell admission
 -> Phase 12 health/readiness/degradation/quarantine
 -> drain/replacement/relocation fences
 -> retirement
```

Health observes this chain but does not grant placement authority.

## Workload identity and secret trace

```text
runtime_profile_id
 -> service/workload principal
 -> allowed capability classes
 -> secret-reference classes
 -> state-port/network policy
 -> credential/config generation
 -> revocation/currentness evidence
 -> PRTV-002/003/013/014/015/016
```

A service identity proves the machine caller; tenant/application authorization remains independently owned where required.

## State-port trace

Each canonical `port.*@1` maps to:

- owning accepted data/security/reliability authority;
- allowed runtime profiles;
- durability/consistency/fencing meaning;
- Phase 11 failure/degradation behavior;
- Phase 12 health/diagnostic evidence;
- compatibility/portability tests.

Implementation-specific storage/broker/cache/object clients are below this port contract.

## Recovery continuity trace

```text
recovery point R
 -> current fence/evidence boundary F
 -> restored runtime/state ports
 -> current placement/security/governance/secret-key authority
 -> reliability/effect evidence reconciliation over (R,F]
 -> cell/runtime quarantine predicates satisfied
 -> destination admission restored
```

`process started`, `port reachable` or `orchestrator healthy` cannot skip this chain.

## Product applicability trace

Phase 13 inherits Product authority rather than deriving it from runtime deployment:

```text
accepted Product authority
 -> upstream applicability decision / OPEN
 -> prepared runtime capability where appropriate
 -> runtime does not mutate Product truth
```

In particular, `OPEN-OBS-037` cannot be closed because a webhook/artifact runtime exists or does not exist.

## Capacity and relocation trace

```text
accepted workload + tenant skew
 -> multidimensional runtime capacity profile
 -> saturation/bulkhead evidence
 -> scale class (replica / pool / state port / cell)
 -> if tenant relocation: Control Plane placement operation
 -> source/target admission fences
 -> transfer/reconciliation capacity
 -> current placement cutover
 -> stale source rejection
```

Scaling mechanism cannot bypass relocation authority.

## Downstream consumer: Phase 14

Phase 14 consumes:

- runtime profile IDs and compatible implementation mappings;
- lifecycle/admission/draining/retirement semantics;
- workload identity and least-privilege boundaries;
- configuration/credential/network generation semantics;
- state-port compatibility requirements;
- migration/admin runtime profile;
- cell-aware rollout and replacement capabilities;
- rollback restrictions against stale authority;
- runtime conformance/fault evidence requirements.

Phase 14 decides build/promotion/deployment mechanisms but cannot redefine Phase 13 runtime semantics.

## Downstream consumer: Phase 15

Phase 15 consumes:

- recovery runtime and quarantine/resumption predicates;
- privileged operational access boundaries;
- cell drain/replacement/relocation controls;
- observable lifecycle/capacity/security state;
- secret/credential rotation operational requirements;
- runtime fault/game-day vectors.

Phase 15 defines human process/incident authority, not new runtime privilege.

## Downstream consumer: Implementation Readiness

Implementation Readiness must prove that Product/Security/API/Event/Reliability/Observability/Platform/Release/Operations layers leave no runtime decision that code would need to invent silently.

## Evidence matrix

| Claim | Design evidence now | Future conformance/runtime evidence |
|---|---|---|
| edge independence | overview/runtime profile | core-flow execution with edge removed/replaced |
| network != trust | network/identity contracts | unauthorized reachable workload denial |
| workload least privilege | identity + manifest | principal/secret/state-port denial tests |
| secret/config currentness | identity/config contract | rotation/revocation/stale-config tests |
| cell lifecycle | lifecycle contract | provision/validate/admit/drain/replace rehearsal |
| placement fencing | lifecycle + manifest | stale source/placement generation tests |
| durable drain semantics | runtime roles + Phase 11 join | worker/API/realtime scale-down fault tests |
| state-port authority | port contract | semantic conformance/restore/failure tests |
| parser/automation isolation | privileged execution | sandbox/egress/secret/resource tests |
| migration/admin separation | privileged execution | application-principal denial + migration rehearsal |
| recovery continuity | lifecycle/recovery trace | restore `(R,F]` reconciliation rehearsal |
| multidimensional capacity | capacity model | load/skew/saturation/cost benchmarks |
| second-cell portability | capacity/lifecycle | second-cell provisioning + wrong-placement rejection |
| tenant relocation | capacity/lifecycle | source/target cutover/fence/reconciliation tests |
| vendor portability | manifest + compatibility | alternative mapping rehearsal without semantic rewrite |

## Permanent evidence requirements

Implementation/release/runtime evidence preserves enough provenance to identify:

- repository/source and Phase 13 profile state;
- runtime implementation/version/image/artifact identity when later available;
- runtime/cell/config/network/credential generations as applicable;
- environment/cell/workload profile;
- state-port/profile versions;
- test/fault/capacity scenario and result;
- timestamp/order and evidence class;
- whether evidence is design, conformance, release or production evidence.

Evidence from one runtime/profile/generation is not silently reused for a materially different one.

## Native Assurance integration

Deterministic GitHub Actions and vendor/platform checks are bounded evidence. They do not accept Phase 13 or authorize merge.

Any material correction creates a new HEAD and requires applicable exact-HEAD checks and panoramic Native Assurance again.

## Traceability blockers

Acceptance is blocked when an accepted upstream property has no Phase 13 runtime owner/mapping, when a runtime profile lacks a complete identity/isolation/network/port/failure/observability chain, when a later phase would need to invent authority meaning, or when Product/vendor/runtime state is used to bypass an upstream OPEN/owner.