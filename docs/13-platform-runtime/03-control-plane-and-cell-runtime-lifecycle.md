# Phase 13 — Control Plane and Cell Runtime Lifecycle

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines the portable runtime lifecycle for Control Plane and data-plane cells while preserving accepted tenant-placement, environment-isolation, failure-containment and recovery semantics.

Cell/runtime-generation lifecycle is distinct from workload health, logical environment class, tenant Product lifecycle and replacement/relocation operation state. A lifecycle state controls admission for one runtime/cell generation; Phase 12 health profiles expose runtime condition without becoming placement or environment authority.

## Cell/runtime-generation record

Every concrete cell/runtime generation records at least:

```text
runtime_generation
environment_class
cell identity where applicable
lifecycle state
configuration_generation
workload_credential_generation
network_policy_generation
accepted runtime/profile versions
admission/fence evidence
```

`environment_class` must be one of the canonical Phase 13 classes allowed by the runtime profile. Changing the physical account/project/cluster mapping does not change the logical class by itself; changing the logical class is a semantic compatibility event, not a relabel.

## Cell/runtime-generation lifecycle

The canonical per-generation lifecycle is:

```text
provisioning
  -> validating
  -> admitted
  -> active
  -> draining
  -> retired

exception paths:
  any non-retired state -> quarantined
  provisioning/validating -> failed
  quarantined -> validating OR draining/retired
  failed -> provisioning only through a new explicit lifecycle attempt/generation
```

`retired` is terminal for that `runtime_generation`. A retired generation SHALL NOT return to `active`; replacement creates or admits a successor generation.

These names describe Phase 13 runtime lifecycle, not Product tenant lifecycle, environment class or Phase 12 health values.

### `provisioning`

Runtime/data dependencies are being created or attached. No normal tenant traffic is admitted. Bootstrap uses only accepted environment-scoped configuration, secret references, identity and placement authority.

### `validating`

The candidate generation proves runtime conformance, environment binding, dependency reachability/trust, state-port authority, observability bindings and required generation/fence state. Validation does not itself assign tenants or grant production authority.

### `admitted`

The Control Plane may place eligible tenant workloads into the cell/generation according to accepted placement/capacity policy only when the environment class is compatible with the workload. Admission does not imply every workload is presently healthy.

A development/validation generation cannot be admitted as production tenant-serving authority merely because it is healthy or physically colocated with production.

### `active`

The generation may serve only workloads permitted by its runtime profile + environment class and, for production tenant work, only tenants whose trusted placement and placement generation are admitted locally.

### `draining`

No new tenant/workload admission beyond narrowly accepted drain/recovery work. Existing requests, sockets and durable jobs follow class-specific drain rules. Draining never deletes durable obligations, changes environment authority or proves external-effect absence.

### `quarantined`

Normal protected/effectful admission is blocked because current environment binding, placement, security, recovery, governance or reliability continuity cannot be proven. Reachability alone cannot clear quarantine.

A quarantined generation may return only through `validating`, after the owning authorities prove the predicates that caused quarantine are current/satisfied. If the generation will not resume, it proceeds through controlled drain/retirement. No telemetry signal, environment relabel or operator convenience directly transitions `quarantined -> active`.

### `retired`

No tenant workload is authoritative in that generation. Retirement requires placement/lease/generation fences sufficient to reject stale work and defined handling of residual durable state. Retirement does not authorize cross-environment reuse of credentials/data/state ports.

### `failed`

Provisioning/runtime conformance failed before safe admission or requires explicit recovery/replacement path. `failed` does not authorize destructive cleanup and does not silently retry under the same authority assumption.

## Environment lifecycle rule

Canonical environment classes are:

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Rules:

- development/validation cell generations are never production placement authority by label, health or physical location;
- production cell generations require current production workload identity/config/network/state-port/placement evidence independently of the environment label;
- recovery runtime/cell generations remain in `environment.recovery@1` and non-serving/quarantined for normal production work until current recovery/resumption predicates are satisfied;
- recovery-to-production handoff creates/admits the appropriate production-target runtime generation or otherwise proves an accepted semantic transition; merely renaming an environment or changing a routing target is insufficient;
- Phase 14 may change physical environment mappings under `OPEN-PRT-035`, but the lifecycle/admission evidence must remain tied to the fixed logical environment class;
- `PRTV-044` falsifies environment label/reachability used as admission authority.

## Replacement is an operation, not a generation state

Cell/runtime replacement links at least two generation records:

```text
predecessor generation: active -> draining -> retired
successor generation:   provisioning -> validating -> admitted -> active
replacement operation:  prepared -> draining/preparing -> cutover -> completed
                        OR reconciliation_blocked / failed
```

The exact operation-state representation may vary, but implementations SHALL NOT represent both predecessor and successor as one ambiguous `replacing` generation. Each generation retains its own environment class, admission/fence/currentness evidence.

Replacement is not tenant relocation unless Control Plane placement authority changes the tenant's authoritative cell. Replacement also does not silently change environment class.

## Runtime generation

Each concrete cell/runtime generation has a non-business `runtime_generation` or equivalent fencing identity. It is used to distinguish stale runtime instances/configuration and support replacement/recovery evidence.

Rules:

- runtime generation never appears as canonical tenant/resource identity;
- increasing runtime generation does not itself move tenant placement or change environment class;
- restoring an older runtime generation cannot override current environment/placement/security/governance generations;
- stale instances SHALL be unable to regain protected admission merely because they can reach shared dependencies;
- predecessor and successor generations remain distinguishable throughout replacement/recovery.

## Placement admission join

For tenant-scoped work, destination admission requires at least:

```text
tenant_id
trusted cell assignment
placement_version
placement state eligible for operation
runtime environment_class eligible for workload
cell admission record recognizing tenant/version
environment-scoped workload/current authority checks required by operation
runtime lifecycle allowing workload class
```

Caller/provider/message physical routing metadata or environment labels are non-authoritative. Async work re-resolves placement or uses an accepted relocation-orchestrator pin/fence.

## Control Plane impairment

Stable already-admitted traffic MAY continue only through the accepted Phase 11 last-known-good placement profile. Phase 13 must provide the runtime capability for:

- trusted versioned cache/distribution of placement evidence;
- bounded expiry/currentness policy;
- destination-cell independent admission check;
- environment-class consistency with the admitted workload;
- immediate rejection after observing newer incompatible placement/security/environment state;
- topology-changing operations to fail closed without current Control Plane authority.

The implementation must not convert a cached placement hit or production environment label into global authorization.

## Draining semantics by workload

### Synchronous API/BFF

Stop new admission for the draining scope, allow bounded in-flight work to finish where safe, and reject/retry through routing according to API semantics. No ordinary transaction is abandoned after commit ambiguity as if absent.

### Workers

Stop claiming new work for the draining ownership scope, complete or safely release/expire leases according to Phase 10/11 semantics, and preserve durable outcome/reconciliation evidence. Worker obligations do not move across environment classes by drain/scale convenience.

### Realtime

Stop new protected socket admission; existing connections are terminated/resynced according to accepted revocation/relocation/drain policy. Socket existence never pins tenant placement or environment authority permanently.

### Automation/parser/privileged jobs

No new jobs after drain begins unless explicitly recovery-authorized. In-flight jobs reach a defined safe checkpoint or terminate into discoverable reconciliation state. Environment scope remains part of the operation identity/evidence.

## Cell replacement

Replacement SHALL prove:

- successor runtime uses accepted semantic/profile versions and an allowed environment class;
- state ports point to the intended authoritative data/reliability/governance state for that environment;
- secret/workload identity generations are current and environment-scoped;
- stale predecessor admission is fenced;
- Phase 12 health/diagnostic profile identities remain semantically compatible;
- durable async/realtime work can resume/reconcile without duplicate protected effects;
- predecessor retirement is terminal for its runtime generation;
- replacement does not silently promote development/validation/recovery authority into production.

## Tenant relocation support

Phase 13 provides runtime capabilities for accepted relocation, but does not redefine the relocation authority/state machine.

Required capabilities:

- source/target cell generation and admission fencing;
- target validation before write authority moves;
- production environment-class consistency for authoritative tenant-serving source/target;
- source drain without caller-controlled target selection;
- async/realtime re-resolution/resync;
- `(R,F]` evidence and ambiguous-effect reconciliation across cutover;
- rejection of stale source-cell workers/requests after authority moves;
- physical location changes without tenant/resource identity rewrite.

A validation rehearsal is not a production relocation unless current production placement authority explicitly performs it.

## Recovery continuity

After restore/replacement, recovery execution remains in its accepted environment class and cell runtime remains quarantined until applicable current authority is proven for:

- environment binding/handoff authority;
- placement/admission generation;
- authorization/session/revocation state;
- reliability inbox/outbox/replay/effect evidence;
- audit/accountability continuity;
- governance/erasure/legal-hold state;
- secret/key authority required to interpret retained protected evidence.

`runtime started`, `database reachable`, `environment.production@1` label or successful physical remapping are insufficient recovery completion predicates.

## Observability join

Lifecycle emits Phase 12-compatible evidence for:

- lifecycle state, runtime generation and canonical environment class;
- cell admission/readiness/degradation/drain/quarantine;
- placement/configuration/currentness/environment-binding gaps;
- replacement predecessor/successor generation identity;
- durable-progress and recovery reconciliation;
- capacity/saturation.

Telemetry observes lifecycle/environment; it does not transition authoritative placement, promote environments or clear quarantine by itself.
