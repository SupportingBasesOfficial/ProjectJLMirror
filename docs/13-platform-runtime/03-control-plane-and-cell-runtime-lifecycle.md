# Phase 13 — Control Plane and Cell Runtime Lifecycle

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines the portable runtime lifecycle for Control Plane and data-plane cells while preserving accepted tenant-placement, failure-containment and recovery semantics.

Cell lifecycle is distinct from workload health. A lifecycle state controls admission and topology intent; Phase 12 health profiles expose runtime condition without becoming placement authority.

## Cell lifecycle states

The canonical lifecycle model is:

```text
provisioning
  -> validating
  -> admitted
  -> active
  -> draining
  -> retired

exception paths:
  any pre-retired state -> quarantined
  provisioning/validating -> failed
  active/draining -> replacing
  replacing -> validating/admitted OR quarantined/failed
```

These names describe Phase 13 runtime lifecycle, not Product tenant lifecycle and not Phase 12 health values.

### `provisioning`

Runtime/data dependencies are being created or attached. No normal tenant traffic is admitted. Bootstrap uses only accepted configuration, secret references, identity and placement authority.

### `validating`

The candidate cell proves runtime conformance, dependency reachability/trust, state-port authority, observability bindings and required generation/fence state. Validation does not itself assign tenants.

### `admitted`

The Control Plane may place eligible tenant workloads into the cell according to accepted placement/capacity policy. Admission does not imply every workload is presently healthy.

### `active`

The cell may serve tenants whose trusted placement and placement generation are admitted locally.

### `draining`

No new tenant placement/admission beyond narrowly accepted drain/recovery work. Existing requests, sockets and durable jobs follow class-specific drain rules. Draining never deletes durable obligations or proves external-effect absence.

### `replacing`

A successor runtime/cell generation is being prepared while the predecessor is fenced/drained according to workload semantics. Replacement is not tenant relocation unless placement authority changes.

### `quarantined`

Normal protected/effectful admission is blocked because current placement, security, recovery, governance or reliability continuity cannot be proven. Reachability alone cannot clear quarantine.

### `retired`

No tenant workload is authoritative in the cell. Retirement requires placement/lease/generation fences sufficient to reject stale work and defined handling of residual durable state.

### `failed`

Provisioning/runtime conformance failed before safe admission or requires explicit recovery/replacement path. `failed` does not authorize destructive cleanup.

## Runtime generation

Each concrete cell/runtime generation has a non-business `runtime_generation` or equivalent fencing identity. It is used to distinguish stale runtime instances/configuration and support replacement/recovery evidence.

Rules:

- runtime generation never appears as canonical tenant/resource identity;
- increasing runtime generation does not itself move tenant placement;
- restoring an older runtime generation cannot override current placement/security/governance generations;
- stale instances SHALL be unable to regain protected admission merely because they can reach shared dependencies.

## Placement admission join

For tenant-scoped work, destination admission requires at least:

```text
tenant_id
trusted cell assignment
placement_version
placement state eligible for operation
cell admission record recognizing tenant/version
current authority checks required by operation
runtime lifecycle allowing workload class
```

Caller/provider/message physical routing metadata is non-authoritative. Async work re-resolves placement or uses an accepted relocation-orchestrator pin/fence.

## Control Plane impairment

Stable already-admitted traffic MAY continue only through the accepted Phase 11 last-known-good placement profile. Phase 13 must provide the runtime capability for:

- trusted versioned cache/distribution of placement evidence;
- bounded expiry/currentness policy;
- destination-cell independent admission check;
- immediate rejection after observing newer incompatible placement/security state;
- topology-changing operations to fail closed without current Control Plane authority.

The implementation must not convert a cached placement hit into global authorization.

## Draining semantics by workload

### Synchronous API/BFF

Stop new admission for the draining scope, allow bounded in-flight work to finish where safe, and reject/retry through routing according to API semantics. No ordinary transaction is abandoned after commit ambiguity as if absent.

### Workers

Stop claiming new work for the draining ownership scope, complete or safely release/expire leases according to Phase 10/11 semantics, and preserve durable outcome/reconciliation evidence.

### Realtime

Stop new protected socket admission; existing connections are terminated/resynced according to accepted revocation/relocation/drain policy. Socket existence never pins tenant placement permanently.

### Automation/parser/privileged jobs

No new jobs after drain begins unless explicitly recovery-authorized. In-flight jobs reach a defined safe checkpoint or terminate into discoverable reconciliation state.

## Cell replacement

Replacement SHALL prove:

- successor runtime uses accepted semantic/profile versions;
- state ports point to the intended authoritative data/reliability/governance state;
- secret/workload identity generations are current;
- stale predecessor admission is fenced;
- Phase 12 health/diagnostic profile identities remain semantically compatible;
- durable async/realtime work can resume/reconcile without duplicate protected effects.

## Tenant relocation support

Phase 13 provides runtime capabilities for accepted relocation, but does not redefine the relocation authority/state machine.

Required capabilities:

- source/target cell generation and admission fencing;
- target validation before write authority moves;
- source drain without caller-controlled target selection;
- async/realtime re-resolution/resync;
- `(R,F]` evidence and ambiguous-effect reconciliation across cutover;
- rejection of stale source-cell workers/requests after authority moves;
- physical location changes without tenant/resource identity rewrite.

## Recovery continuity

After restore/replacement, cell runtime remains quarantined until applicable current authority is proven for:

- placement/admission generation;
- authorization/session/revocation state;
- reliability inbox/outbox/replay/effect evidence;
- audit/accountability continuity;
- governance/erasure/legal-hold state;
- secret/key authority required to interpret retained protected evidence.

`runtime started` and `database reachable` are insufficient recovery completion predicates.

## Observability join

Lifecycle emits Phase 12-compatible evidence for:

- lifecycle state and runtime generation;
- cell admission/readiness/degradation/drain/quarantine;
- placement/configuration currentness gaps;
- durable-progress and recovery reconciliation;
- capacity/saturation.

Telemetry observes lifecycle; it does not transition authoritative placement or clear quarantine by itself.