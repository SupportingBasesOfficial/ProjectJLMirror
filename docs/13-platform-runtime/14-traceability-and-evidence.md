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
 -> runtime_profile_id
 -> worker_specialization_id when runtime.worker@1
 -> workload principal
 -> isolation profile
 -> ingress/egress profile
 -> state ports
 -> exact Phase 11 reliability binding
 -> exact Phase 12 health/signal/SLI binding
 -> PRTV fault vectors
```

No runtime may omit a link by relying on vendor defaults. Generic `runtime.worker@1` without a selected `worker.*@1` specialization is incomplete conformance evidence.

## Worker specialization trace

The prepared worker set is:

```text
worker.outbox-publication@1
worker.async-consumer@1
worker.provider-integration@1
worker.webhook-delivery@1
worker.reporting-export@1
worker.customer-telemetry@1
worker.artifact-lifecycle@1
worker.reconciliation@1
```

For each selected specialization, evidence binds:

```text
worker specialization
 -> exact reliability owner(s)
 -> exact Phase 12 health/SLI evidence
 -> queue/transport + state-port set
 -> secret/egress set
 -> concurrency/bulkhead budget
 -> specialization PRTV vectors
 -> PRTV-037 when co-located with another specialization
```

Implementation cannot use a shared process name to erase those bindings.

## Cell lifecycle trace

```text
Control Plane placement authority
 -> runtime_generation lifecycle
 -> provisioning/validation/admission
 -> tenant + placement-version cell admission
 -> Phase 12 health/readiness/degradation/quarantine
 -> predecessor/successor replacement operation with distinct generations
 -> drain/relocation/recovery fences
 -> terminal retirement of old generation
```

A quarantined generation can return to normal protected admission only through `validating` after owning authority predicates are satisfied. `PRTV-038` falsifies direct quarantine bypass.

Health observes this chain but does not grant placement authority.

## Generation/currentness trace

Canonical Phase 13 generations are:

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

The evidence chain preserves the owner of each dimension. Upstream authorization/revocation, schema, replay, artifact-delivery, governance and cryptographic/verifier generations remain under their accepted owners.

`PRTV-042` proves that one current/green generation cannot substitute for another currentness authority.

## Workload identity and secret trace

```text
runtime_profile_id / worker_specialization_id
 -> service/workload principal
 -> allowed capability classes
 -> secret-reference classes
 -> state-port/network policy
 -> workload_credential_generation + configuration_generation
 -> revocation/currentness evidence
 -> PRTV-002/003/013/014/015/016/041/042 as applicable
```

A service identity proves the machine caller; tenant/application authorization remains independently owned where required.

Secret materialization evidence explicitly includes `PRTV-041`: receiving a secret at runtime does not make that value admissible in ordinary config snapshots, logs, traces, metrics, events/jobs, artifacts, crash/export evidence or ordinary audit snapshots.

## State-port trace

Each canonical `port.*@1` maps to:

- owning accepted data/security/reliability authority;
- allowed runtime/worker profiles;
- durability/consistency/fencing meaning;
- Phase 11 failure/degradation behavior;
- Phase 12 health/diagnostic evidence;
- compatibility/portability tests.

Physical backend co-location does not merge logical port authority. `PRTV-039` falsifies authority collapse among transactional, reliability, audit, customer-telemetry, observability and other state ports.

Implementation-specific storage/broker/cache/object clients are below this port contract.

## Artifact release trace

```text
runtime/worker artifact capability
 -> port.artifact@1 / object staging where applicable
 -> authoritative artifact lifecycle metadata
 -> current delivery generation / lease / governance authority
 -> protected release
```

Object bytes, upload success, a storage URL or raw object capability cannot skip the owning artifact lifecycle. `PRTV-040` is the mandatory release-bypass vector for mappings that can serve protected artifact bytes.

## Co-location trace

Whenever runtime profiles or worker specializations share a physical process/runtime, evidence records:

```text
selected profiles/specializations
 -> effective principal union
 -> secret-reference union
 -> state-port union
 -> egress/network union
 -> resource/bulkhead coupling
 -> lifecycle/failure coupling
 -> PRTV-037 result
```

If the resulting effective authority exceeds accepted profile unions, co-location fails rather than silently expanding the trust envelope.

## Recovery continuity trace

```text
recovery point R
 -> current fence/evidence boundary F
 -> restored runtime/state ports
 -> current placement/security/governance/secret-key authority
 -> reliability/effect evidence reconciliation over (R,F]
 -> cell/runtime quarantine predicates satisfied
 -> validating
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
 -> worker/runtime specialization bulkheads
 -> saturation evidence
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

- runtime and worker-specialization profile IDs and compatible implementation mappings;
- lifecycle/admission/draining/quarantine/retirement semantics;
- workload identity and least-privilege boundaries;
- `runtime_generation`, `configuration_generation`, `workload_credential_generation`, `placement_version` and `network_policy_generation` semantics;
- state-port compatibility and logical-authority separation requirements;
- migration/admin runtime profile;
- cell-aware rollout and replacement capabilities;
- rollback restrictions against stale authority;
- runtime conformance/fault evidence, including `PRTV-037..042`.

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
| edge independence | overview/runtime profile | `PRTV-001` core-flow execution with edge removed/replaced |
| network != trust | network/identity contracts | `PRTV-002`, `PRTV-003` denial tests |
| workload least privilege | identity + manifest | principal/secret/state-port denial + `PRTV-037` co-location tests |
| worker specialization | roles + manifest | exact worker profile/queue/port/egress/bulkhead conformance |
| secret/config currentness | identity/config contract | rotation/revocation/stale-config + `PRTV-041`, `PRTV-042` |
| cell lifecycle | lifecycle contract | provision/validate/admit/drain/quarantine/replace rehearsal + `PRTV-038` |
| placement fencing | lifecycle + manifest | stale source/placement generation tests |
| durable drain semantics | runtime roles + Phase 11 join | worker/API/realtime scale-down fault tests |
| state-port authority | port contract | semantic conformance/restore/failure + `PRTV-039` |
| artifact release authority | port/manifest/security | `PRTV-040` object-presence/capability bypass test |
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
- runtime profile and `worker_specialization_id` set;
- runtime implementation/version/image/artifact identity when later available;
- runtime/cell/config/network/workload-credential/placement generations as applicable;
- separately owned upstream generation identities where material to the test;
- environment/cell/workload profile;
- state-port/profile versions;
- test/fault/capacity scenario and result;
- timestamp/order and evidence class;
- whether evidence is design, conformance, release or production evidence.

Evidence from one runtime/profile/specialization/generation is not silently reused for a materially different one.

## Native Assurance integration

Deterministic GitHub Actions and vendor/platform checks are bounded evidence. They do not accept Phase 13 or authorize merge.

Any material correction creates a new HEAD and requires applicable exact-HEAD checks and panoramic Native Assurance again.

## Traceability blockers

Acceptance is blocked when an accepted upstream property has no Phase 13 runtime owner/mapping, when a runtime or selected worker specialization lacks a complete identity/isolation/network/port/failure/observability/vector chain, when co-location/quarantine/state-port/artifact/secret/generation claims lack the applicable `PRTV-037..042` evidence path, when a later phase would need to invent authority meaning, or when Product/vendor/runtime state is used to bypass an upstream OPEN/owner.