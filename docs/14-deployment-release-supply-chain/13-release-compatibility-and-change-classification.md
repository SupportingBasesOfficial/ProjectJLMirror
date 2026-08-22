# Phase 14 — Release Compatibility and Change Classification

**Status:** proposed baseline

## Principle

Release compatibility is semantic and stateful. Same schema, same artifact format or successful rollout command does not prove compatibility.

## Classes

### RLS-COMP-A — non-semantic operational
Examples: bounded replica/wave implementation tuning that does not alter authority, compatibility or failure semantics.

### RLS-COMP-B — release-consumer relevant
Examples: equivalent physical registry, CI runner or deployment-controller replacement preserving the same logical profiles/evidence; new physical environment mapping preserving Phase 13 semantics.

### RLS-COMP-C — semantic breaking
Includes changes to source trust-class meaning, trusted release-policy profile semantics, artifact identity, provenance meaning, promotion/deployment authority, deployment operation identity, release-target state/fencing, ambiguity/retry eligibility, validation-scope applicability, environment mapping semantics, principal separation, runtime artifact verification meaning, cell compatibility metadata semantics/currentness, mixed-version support, migration step meaning, rollback eligibility, pause/abort gates or evidence disposition.

### RLS-COMP-D — security/recovery sensitive
Includes broadened CI/CD principal; untrusted-source validation gaining trusted release credentials/network/secrets; candidate-controlled policy self-escalation; secret exposure; weaker artifact/runtime identity verification; stale approval reuse; stale deployment executor regaining target authority; ambiguous deployment retried as absent; production/lower-environment bleed; stale/forged cell compatibility metadata granting placement/cutover; rollback of release-policy/verifier/revocation/governance/reliability state; migration-owner reuse; supply-chain evidence loss; or release authority inferred from tool defaults.

## Source-trust compatibility

`source.untrusted-candidate@1` and `source.accepted-review-state@1` are distinct trust classes.

Changing the evidence required to transition between them is semantic/security-sensitive. A workflow trigger, branch naming convention, repository membership or validation result cannot silently become accepted-source authority through implementation change.

The evaluator principal of untrusted source remains bounded. Changing runner, workflow engine or CI provider is compatible only when candidate source still cannot select a more privileged token/environment/secret/network/profile.

## Release-policy compatibility

The trusted release-policy profile/version used for source trust transition, principal selection, promotion, deployment and verification is part of release semantics.

A policy change that broadens privilege, weakens currentness, accepts a previously rejected artifact/provenance state, changes approval meaning or allows candidate-controlled authority selection is breaking/security-sensitive even when application code and pipeline syntax are otherwise compatible.

Restore/downgrade of policy/verifier authority is compatible only if retired principals, approvals and verifier trust do not become current again. `RLV-044` applies.

## Release operation / target-state compatibility

The meanings of `deployment_operation_id`, `expected_release_target_state_version`, target-state winner selection, stale-executor fencing and ambiguous-outcome reconciliation are correctness/security semantics.

Changing an implementation so that:

- two incompatible deployments can both advance one target;
- a deployment ID may be silently regenerated on retry;
- same operation ID can carry different immutable artifact/config/target semantics;
- timeout/process loss is treated as target-effect absence;
- a stale release-target version can overwrite a newer state;
- release-target state is treated as placement/runtime/business authority;

is breaking. `RLV-047` and `RLV-048` apply.

Replacing the coordination product may be compatible only when create-or-observe, one-current-transition, target-state fencing and ambiguity discovery remain semantically equivalent.

## Validation-scope compatibility

`validation.general@1` and `validation.reference-cell@1` are Phase 14 rollout/evidence scopes inside the accepted `environment.validation@1` class.

For cell/runtime/schema-affecting releases covered by the accepted Data rollout semantics, removing/skipping `validation.reference-cell@1`, treating it as a fifth environment, or replacing it with deployment-tool “staging” semantics that carry production authority is breaking.

Changing applicability from required to `NO_APPLICABLE_CASE` requires explicit evidence and owning authority; tool absence is not compatibility evidence. `RLV-045` applies.

## Cell compatibility metadata compatibility

The meaning, owner and currentness of Control Plane cell current/target runtime-schema compatibility metadata are release/placement safety semantics.

Changing the metadata so it becomes caller-controlled, inferred from deployment success, stale-tolerant beyond accepted authority, or no longer blocks incompatible placement/cutover is breaking/security-sensitive. `RLV-046` applies.

Adding physical fields without changing these semantics may be implementation evolution.

## Tool replacement

Replacing CI/CD, registry, scanner, signing service, orchestrator, release coordination store or cloud mechanism is compatible only when logical source/build/artifact/promotion/deployment/runtime-verification semantics and evidence remain equivalent.

## Artifact compatibility

A new artifact build is never “the same release artifact” merely because source SHA matches. Artifact immutable identity is distinct and provenance must identify the build.

Changing the mechanism that maps deployed/running workload to `release.artifact@1` is compatibility-sensitive. Desired-state object, mutable tag or deployment receipt cannot silently replace independently observed immutable runtime artifact identity. `RLV-043` applies.

## Configuration compatibility

Configuration-only changes may be semantic/security breaking. Changes to tenant/security/network/runtime/failure/Product/recovery behavior follow the owning higher-level compatibility rules.

## Mixed-version compatibility

Review includes old/new combinations of API, event, runtime, schema, configuration and workers, plus validation scope, current cell compatibility metadata, release-target state, current authority generations, release policy/verifier state and historical evidence interpretation.

## Migration compatibility

Changing expand/migrate/contract ordering, backfill resume semantics, lock/fence ownership, validation reference-cell requirement, cell compatibility metadata transitions or destructive-contract prerequisites is breaking.

Migration/release coordination changes also preserve stable operation identity/fencing where effectful ambiguity can occur.

## Rollback compatibility

A change from `rollback_eligible` to any stricter class is material. Rollback support cannot be advertised after irreversible schema/effect/security state makes old runtime unsafe.

Rollback of release control-plane state is also unsafe when it would restore a retired promotion approval, broader old principal, obsolete verifier, weaker release policy, stale release-target state or stale cell compatibility state.

## Evidence compatibility

Changing provenance/SBOM/signature/attestation interpretation, verifier authority, runtime-artifact observation, deployment operation identity/outcome evidence, validation-scope evidence, release-target state provenance, cell compatibility metadata provenance/retention or correlation is compatibility-sensitive even if artifact bytes are unchanged.

## Downgrade

If a previous runtime, release-target state, cell compatibility state or release-policy/verifier state cannot safely interpret current authoritative state, downgrade is prohibited; forward recovery, reconciliation or quarantine is required.