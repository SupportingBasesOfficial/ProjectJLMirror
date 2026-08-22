# Phase 13 — Compatibility and Change Classification

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

Platform/runtime compatibility is semantic. A new container image, cluster, network policy, secret backend, storage endpoint or environment mapping is compatible only when accepted runtime authority, lifecycle, failure, recovery, tenant, environment and observability semantics remain valid.

## Change classes

### PRT-COMP-A — Operationally additive/non-semantic

Examples:

- additional replica of an interchangeable stateless runtime;
- resource tuning that remains inside accepted profile and does not alter failure/admission semantics;
- implementation-specific metadata not consumed by canonical contracts.

Requires ordinary review and evidence that no accepted semantic profile changes.

### PRT-COMP-B — Runtime consumer-relevant

Examples:

- new bounded runtime class implementation;
- new state-port endpoint/topology with equivalent authority semantics;
- network/egress mapping change within same accepted capability set;
- new worker specialization implementation that maps exactly to an already accepted `worker.*@1` profile;
- new physical account/project/cluster mapping for an unchanged accepted logical environment class;
- new diagnostic/runtime-generation field consumed by later phases.

Requires profile/conformance, mixed-version, security/capacity and rollback review. Physical environment mapping additionally preserves `OPEN-PRT-035`/Phase 14 promotion authority.

### PRT-COMP-C — Semantic breaking

Includes changes to:

- runtime role responsibility or trust envelope;
- canonical manifest-field meaning, requiredness or disposition rules;
- logical environment-class semantics or allowed runtime/environment bindings;
- treating physical environment/account/cluster labels as authorization, tenant or Product authority;
- worker-specialization identity, responsibility, privilege, state-port, queue/transport or bulkhead meaning;
- co-location that unions principals/secrets/state/network authority;
- workload identity meaning or capability scope;
- lifecycle/admission/draining/quarantine meaning;
- predecessor/successor replacement-generation semantics;
- `runtime_generation`, `configuration_generation`, `workload_credential_generation`, `placement_version` or `network_policy_generation` meaning/ownership;
- using one generation as a substitute for another owning authority;
- state-port durability/transaction/fencing/failure semantics or logical authority separation;
- artifact/object release authority;
- network trust assumptions or egress policy meaning;
- parser/automation/admin/recovery isolation;
- tenant/cell authority mapping;
- capacity/bulkhead/noisy-neighbor semantics;
- relocation/replacement/recovery fencing;
- mapping from Phase 11 failure or Phase 12 health semantics;
- Product applicability inferred from deployment/configuration/environment state.

These cannot silently retain the same canonical Phase 13 profile/version.

### PRT-COMP-D — Security/recovery authority-sensitive

Breaking changes affecting tenant isolation, environment isolation, production credential/data boundaries, machine identity, secret/key authority, secret materialization/disclosure, privileged execution, physical placement authority, recovery quarantine, audit/governance continuity, state-port authority collapse, artifact release fencing, stale-runtime fencing or external egress are security/recovery-sensitive and release-blocking until owning authority proves safety.

## Manifest completeness compatibility

A runtime implementation is not compatible merely because omitted fields happen to receive safe defaults in one vendor/environment.

Every required manifest field must remain represented by an exact canonical binding, fixed accepted rule, explicit OPEN owner, or evidence-backed `NO_APPLICABLE_CASE` with enclosing impact/evidence path.

Changing a field from explicit to implicit/vendor-default is semantic because it removes enforceable authority/provenance. `PRTV-043` is the canonical falsification vector.

## Logical environment compatibility

The canonical Phase 13 classes are:

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Their logical meanings are part of the runtime contract. Compatibility rules:

- changing which runtime profile may execute in an environment class is semantic and requires privilege/data/network/recovery review;
- development/validation gaining production workload credentials, production placement authority, authoritative production tenant traffic or ungoverned production-derived data is security-breaking;
- recovery environment becoming a normal production-serving class, or bypassing current production resumption predicates, is recovery/security-breaking;
- environment class never enters canonical tenant/resource/API/event identity;
- moving the same logical environment to another physical account/project/subscription/cluster/namespace/region may be compatible only when the logical semantics remain unchanged and `OPEN-PRT-035`/Phase 14 promotion/mapping evidence is satisfied;
- adding a new logical environment class changes Phase 13 normative semantics and requires a Phase 13 successor/review, not just deployment configuration.

`PRTV-044` is the canonical environment isolation/authority falsification vector.

## Runtime-profile versioning

A profile identity/version represents behavior and authority, not image tag/vendor object.

An implementation may change without canonical profile version only when it proves semantic equivalence for principal/capability scope; allowed environment classes; lifecycle/drain behavior; ingress/egress/state-port access; secret-reference classes; currentness/generation checks; resource/concurrency isolation; failure/recovery behavior; Phase 11 reliability binding; Phase 12 health/observability mapping; and validation/OPEN bindings.

## Worker-specialization compatibility

`runtime.worker@1` is incomplete without the exact selected `worker_specialization_id` set.

A change among or within:

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

requires review of reliability binding, Phase 12 evidence, queue/transport ownership, secret/state/egress access, environment applicability and concurrency/bulkhead budget.

Adding a specialization to an existing physical worker pool is not non-semantic when it broadens effective principal/state-port/secret/egress access or failure/resource coupling. `PRTV-037` applies.

## Co-location compatibility

Combining runtime profiles or worker specializations is semantic unless evidence proves the effective authority and failure envelope remain no broader.

The review compares principal union, secret-reference union, state-port union, egress/network union, environment scope, resource/bulkhead coupling, lifecycle coupling and blast-radius coupling.

If the union creates a capability neither original profile owned, co-location is breaking or forbidden without upstream architectural change. `PRTV-037` is canonical.

## Stateful-port replacement and co-location

A replacement that preserves API shape but changes durability, isolation, consistency, acknowledgement, lease/fence, restore or ambiguity semantics is breaking.

Physical co-location of multiple logical ports does not merge authority. `PRTV-039` proves transactional, reliability, audit, customer-telemetry and observability meanings remain enforceable even if one physical backend implements several ports.

Port migration preserves historical/current evidence needed for idempotency/inbox/outbox/replay, placement/configuration currentness, audit/governance, artifact release/erasure and recovery continuity.

## Workload identity, credential and secret compatibility

`workload_credential_generation` rotation is normally compatible when accepted overlap/retirement semantics remain unchanged. Changing principal scope, issuer trust, revocation behavior, secret-reference access or environment scope can be security-breaking even if application code is unchanged.

Secret/key/verifier generations owned by upstream contracts remain separate. Runtime compatibility SHALL NOT rename/collapse them into a universal currentness generation.

A runtime implementation that newly materializes secret values into environment/config snapshots, logs, traces, metrics, messages, artifacts or ordinary audit evidence is security-breaking. `PRTV-041` applies.

Rollback SHALL NOT reactivate retired credentials, broaden old privileges or map lower environments to production credentials by convenience.

## Generation compatibility

The canonical Phase 13 generation set is:

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

Changing ownership/interpretation is semantic. A green/current value in one dimension cannot prove another; `PRTV-042` falsifies generation-authority conflation.

Environment class is not a generation/currentness token. Upstream authorization/revocation, schema, replay, artifact-delivery, governance and cryptographic/verifier generations keep accepted owners.

## Network compatibility

A networking implementation change is breaking when it broadens reachable destination/trust zones, changes caller authentication, lets internal/environment reachability substitute for identity, weakens connector redirect/SSRF controls, changes cross-cell mutation capability, or removes required isolation/bulkheads.

Service mesh/proxy/discovery changes are not automatically semantic, but their effective policy must be proven equivalent.

## Lifecycle compatibility

Vendor readiness, desired replicas, task/VM health map into accepted Phase 13 lifecycle/Phase 12 health; they cannot redefine it.

Changing `draining`, `quarantined`, `retired` or stale-generation rejection is correctness/recovery breaking. Direct `quarantined -> active` is incompatible; `PRTV-038` requires revalidation.

Replacement keeps predecessor and successor generation identities distinct.

## Artifact release compatibility

Changing object-store/runtime integration is breaking when bytes/object existence, stale direct capability or storage success can bypass artifact lifecycle, delivery-generation, active-delivery/lease or current governance authority. `PRTV-040` applies.

## Mixed-version runtime

Rolling coexistence declares runtime/worker versions, environment class, state-port/schema/message compatibility, workload-credential/config/network-policy overlap, placement/runtime generation boundaries/upstream generations, which generation may create work, drain/fence criteria, Phase 12 interpretation and rollback/forward-recovery behavior.

An older runtime unable to interpret current authority/evidence remains non-admitted.

## Cell portability and relocation

Changing cell implementation/provider/region must not change logical tenant/resource/API/event identity or logical environment semantics. If relocation/replacement requires such rewrite, it violates accepted architecture.

## Product applicability

Deploying/removing a runtime component or mapping it to an environment does not change Product scope. Runtime/environment state is not accepted Product applicability without upstream authority.

## Rollback

Rollback is prohibited from silently restoring stale placement/config/network/workload-credential authority; broadening secret/egress/environment privileges; re-exposing secret material; clearing quarantine; making consumed capabilities/replayed effects eligible; restoring pre-erasure/legal-hold behavior; reusing retired runtime generation as current; collapsing state-port authority; bypassing artifact release fences; mapping development/validation/recovery to production authority; or treating older vendor health mapping as authoritative.

If safe downgrade cannot be proven, forward recovery or continued quarantine is required.

## Evidence

Compatibility evidence includes semantic manifest diff, manifest-completeness `PRTV-043`, environment mapping/isolation `PRTV-044`, worker-specialization diff, effective-principal/policy diff, state-port authority diff, generation-ownership diff, mixed-version tests, stale-generation tests, credential/config rotation tests, co-location `PRTV-037`, quarantine `PRTV-038`, port-authority `PRTV-039`, artifact-release `PRTV-040`, secret-materialization `PRTV-041`, generation-separation `PRTV-042`, drain/relocation/recovery tests, capacity/security analysis and portability mapping.

Schema/API/config syntax compatibility alone is insufficient.