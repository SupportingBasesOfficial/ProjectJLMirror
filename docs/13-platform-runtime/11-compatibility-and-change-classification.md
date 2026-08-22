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
- new workload pool/bulkhead mapping;
- new diagnostic/runtime-generation field consumed by later phases.

Requires profile/conformance, mixed-version, security/capacity and rollback review.

### PRT-COMP-C — Semantic breaking

Includes changes to:

- runtime role responsibility or trust envelope;
- co-location that unions principals/secrets/state/network authority;
- workload identity meaning or capability scope;
- lifecycle/admission/draining/quarantine meaning;
- placement/runtime/configuration/network generation meaning;
- state-port durability/transaction/fencing/failure semantics;
- network trust assumptions or egress policy meaning;
- parser/automation/admin/recovery isolation;
- tenant/cell authority mapping;
- capacity/bulkhead/noisy-neighbor semantics;
- relocation/replacement/recovery fencing;
- mapping from Phase 11 failure or Phase 12 health semantics;
- Product applicability inferred from deployment/configuration state.

These cannot silently retain the same canonical Phase 13 profile/version.

### PRT-COMP-D — Security/recovery authority-sensitive

Breaking changes affecting tenant isolation, machine identity, secret/key authority, privileged execution, physical placement authority, recovery quarantine, audit/governance continuity, stale-runtime fencing or external egress are security/recovery-sensitive and release-blocking until owning authority proves safety.

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

## Co-location compatibility

Combining two previously separate runtime profiles is semantic unless evidence proves the effective authority and failure envelope remain no broader.

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

If the union creates a capability neither original profile owned, co-location is breaking or forbidden without upstream architectural change.

## Stateful-port replacement

A replacement that preserves API shape but changes durability, isolation, consistency, acknowledgement, lease/fence, restore or ambiguity semantics is breaking.

Port migration must preserve historical/current evidence needed for:

- idempotency/inbox/outbox/replay;
- placement/configuration currentness;
- audit/governance;
- artifact release/erasure;
- recovery continuity.

## Workload identity and secret rotation

Credential generation rotation is normally compatible when accepted overlap/retirement semantics remain unchanged. Changing principal scope, issuer trust, revocation behavior or secret-reference access can be security-breaking even if application code is unchanged.

Rollback SHALL NOT reactivate retired credentials or broader old privileges.

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

Changing `draining`, `quarantined`, `retired` or stale-generation rejection behavior is correctness/recovery breaking.

## Mixed-version runtime

Rolling coexistence of runtime/profile versions declares:

- versions allowed simultaneously;
- state-port/schema/message compatibility;
- credential/config/network generation overlap;
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

- restoring stale placement/config/network/credential authority;
- broadening secret/egress privileges;
- clearing recovery quarantine;
- making consumed capabilities/replayed effects eligible;
- restoring pre-erasure/legal-hold behavior;
- reusing retired runtime generation as current;
- treating an older vendor health mapping as authoritative when its semantics differ.

If safe downgrade cannot be proven, forward recovery or continued quarantine is required.

## Evidence

Compatibility evidence includes semantic manifest diff, effective-principal/policy diff, state-port authority diff, mixed-version tests, stale-generation tests, credential/config rotation tests, drain/relocation/recovery tests, capacity/security analysis and portability mapping.

Schema/API/config syntax compatibility alone is insufficient.