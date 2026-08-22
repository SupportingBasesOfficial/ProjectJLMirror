# Phase 13 — Compatibility and Change Classification

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

Platform/runtime compatibility is semantic. A new container image, cluster, network policy, secret backend or storage endpoint is compatible only when accepted runtime authority, lifecycle, failure, recovery, tenant and observability semantics remain valid.

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
- new diagnostic/runtime-generation field consumed by later phases.

Requires profile/conformance, mixed-version, security/capacity and rollback review.

### PRT-COMP-C — Semantic breaking

Includes changes to:

- runtime role responsibility or trust envelope;
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
- Product applicability inferred from deployment/configuration state.

These cannot silently retain the same canonical Phase 13 profile/version.

### PRT-COMP-D — Security/recovery authority-sensitive

Breaking changes affecting tenant isolation, machine identity, secret/key authority, secret materialization/disclosure, privileged execution, physical placement authority, recovery quarantine, audit/governance continuity, state-port authority collapse, artifact release fencing, stale-runtime fencing or external egress are security/recovery-sensitive and release-blocking until owning authority proves safety.

## Runtime-profile versioning

A profile identity/version represents behavior and authority, not image tag/vendor object.

An implementation may change without canonical profile version only when it proves semantic equivalence for:

- principal/capability scope;
- lifecycle/drain behavior;
- ingress/egress/state-port access;
- currentness/generation checks;
- failure/recovery behavior;
- Phase 12 health/observability mapping;
- capacity/isolation envelope.

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

requires review of the specialization's reliability binding, Phase 12 evidence binding, queue/transport ownership, secret/state/egress access and concurrency/bulkhead budget.

Adding a specialization to an existing physical worker pool is not a non-semantic deployment tweak when it broadens the effective principal, state-port/secret/egress access or failure/resource coupling. `PRTV-037` is required for such co-location evidence.

## Co-location compatibility

Combining two previously separate runtime profiles or worker specializations is semantic unless evidence proves the effective authority and failure envelope remain no broader.

The review must compare:

```text
principal union
secret-reference union
state-port union
egress/network union
resource/bulkhead coupling
lifecycle coupling
blast-radius coupling
```

If the union creates a capability neither original profile owned, co-location is breaking or forbidden without upstream architectural change. `PRTV-037` is the canonical falsification vector.

## Stateful-port replacement and co-location

A replacement that preserves API shape but changes durability, isolation, consistency, acknowledgement, lease/fence, restore or ambiguity semantics is breaking.

Physical co-location of multiple logical ports does not merge their authority. `PRTV-039` SHALL prove that transactional, reliability, audit, customer-telemetry and observability meanings/roles remain enforceable even if one physical backend later implements several ports.

Port migration must preserve historical/current evidence needed for:

- idempotency/inbox/outbox/replay;
- placement/configuration currentness;
- audit/governance;
- artifact release/erasure;
- recovery continuity.

## Workload identity, credential and secret compatibility

`workload_credential_generation` rotation is normally compatible when accepted overlap/retirement semantics remain unchanged. Changing principal scope, issuer trust, revocation behavior or secret-reference access can be security-breaking even if application code is unchanged.

Secret/key/verifier generations owned by upstream contracts remain separate. Runtime compatibility SHALL NOT rename or collapse them into a universal currentness generation.

A runtime implementation that newly materializes secret values into environment/config snapshots, logs, traces, metrics, messages, artifacts or ordinary audit evidence is security-breaking regardless of unchanged application schema. `PRTV-041` applies.

Rollback SHALL NOT reactivate retired credentials or broader old privileges.

## Generation compatibility

The canonical Phase 13 generation set is:

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

Changing the ownership or interpretation of any member is semantic. A green/current value in one dimension cannot prove currentness in another dimension; `PRTV-042` falsifies such generation-authority conflation.

Upstream authorization/revocation, schema, replay, artifact-delivery, governance and cryptographic/verifier generations keep their accepted owners and semantics.

## Network compatibility

A networking implementation change is breaking when it:

- broadens reachable destination/trust zones;
- changes caller authentication semantics;
- allows internal reachability to substitute for identity;
- weakens connector redirect/SSRF controls;
- changes cross-cell mutation capability;
- removes required isolation/bulkhead behavior.

Service mesh/proxy/discovery changes are not automatically semantic, but their effective policy must be proven equivalent.

## Lifecycle compatibility

Vendor concepts such as readiness, desired replicas, pod/task state or VM health map into the accepted Phase 13 lifecycle/Phase 12 health model. They cannot redefine it.

Changing `draining`, `quarantined`, `retired` or stale-generation rejection behavior is correctness/recovery breaking. A direct `quarantined -> active` shortcut is incompatible with the accepted lifecycle; `PRTV-038` requires revalidation through the owning authority predicates.

Replacement keeps predecessor and successor generation identities distinct. Collapsing them into one implementation state that loses stale-generation/fence provenance is breaking.

## Artifact release compatibility

Changing object-store/runtime integration is breaking when bytes/object existence, a stale direct capability or storage success can bypass accepted artifact lifecycle, delivery-generation, active-delivery/lease or current governance authority. `PRTV-040` is required for artifact-serving mappings.

## Mixed-version runtime

Rolling coexistence of runtime/profile versions declares:

- runtime and worker-specialization versions allowed simultaneously;
- state-port/schema/message compatibility;
- `workload_credential_generation` / configuration / network-policy overlap;
- placement/runtime generation boundaries and upstream generation dependencies;
- which generation may admit/create new work;
- drain/retirement/fence criteria;
- Phase 12 health/diagnostic interpretation;
- rollback/forward-recovery behavior.

An older runtime that cannot safely interpret current authority/evidence must remain non-admitted rather than guess.

## Cell portability and relocation

Changing cell implementation/provider/region must not change logical tenant ID/resource/API/event identity. If relocation/replacement would require such a rewrite, the implementation violates the accepted architecture rather than representing a compatible migration.

## Product applicability

Deploying/removing a runtime component does not change Product scope. A compatibility diff SHALL NOT record runtime presence/absence as accepted Product applicability without upstream Product authority.

## Rollback

Rollback is prohibited from silently:

- restoring stale placement/config/network/workload-credential authority;
- broadening secret/egress privileges or re-exposing secret material;
- clearing recovery quarantine;
- making consumed capabilities/replayed effects eligible;
- restoring pre-erasure/legal-hold behavior;
- reusing retired runtime generation as current;
- collapsing state-port authority;
- bypassing artifact release fences;
- treating an older vendor health mapping as authoritative when its semantics differ.

If safe downgrade cannot be proven, forward recovery or continued quarantine is required.

## Evidence

Compatibility evidence includes semantic manifest diff, worker-specialization diff, effective-principal/policy diff, state-port authority diff, generation-ownership diff, mixed-version tests, stale-generation tests, credential/config rotation tests, co-location `PRTV-037`, quarantine `PRTV-038`, port-authority `PRTV-039`, artifact-release `PRTV-040`, secret-materialization `PRTV-041`, generation-separation `PRTV-042`, drain/relocation/recovery tests, capacity/security analysis and portability mapping.

Schema/API/config syntax compatibility alone is insufficient.