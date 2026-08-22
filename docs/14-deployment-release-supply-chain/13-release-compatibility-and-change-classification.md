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
Includes changes to source trust-class meaning, trusted release-policy profile semantics, artifact identity, provenance meaning, promotion/deployment authority, environment mapping semantics, principal separation, runtime artifact verification meaning, mixed-version support, migration step meaning, rollback eligibility, pause/abort gates or evidence disposition.

### RLS-COMP-D — security/recovery sensitive
Includes broadened CI/CD principal; untrusted-source validation gaining trusted release credentials/network/secrets; candidate-controlled policy self-escalation; secret exposure; weaker artifact/runtime identity verification; stale approval reuse; production/lower-environment bleed; rollback of release-policy/verifier/revocation/governance/reliability state; migration-owner reuse; supply-chain evidence loss; or release authority inferred from tool defaults.

## Source-trust compatibility

`source.untrusted-candidate@1` and `source.accepted-review-state@1` are distinct trust classes.

Changing the evidence required to transition between them is semantic/security-sensitive. A workflow trigger, branch naming convention, repository membership or validation result cannot silently become accepted-source authority through implementation change.

The evaluator principal of untrusted source remains bounded. Changing runner, workflow engine or CI provider is compatible only when candidate source still cannot select a more privileged token/environment/secret/network/profile.

## Release-policy compatibility

The trusted release-policy profile/version used for source trust transition, principal selection, promotion, deployment and verification is part of release semantics.

A policy change that broadens privilege, weakens currentness, accepts a previously rejected artifact/provenance state, changes approval meaning or allows candidate-controlled authority selection is breaking/security-sensitive even when application code and pipeline syntax are otherwise compatible.

Restore/downgrade of policy/verifier authority is compatible only if retired principals, approvals and verifier trust do not become current again. `RLV-044` applies.

## Tool replacement

Replacing CI/CD, registry, scanner, signing service, orchestrator or cloud mechanism is compatible only when logical source/build/artifact/promotion/deployment/runtime-verification semantics and evidence remain equivalent.

## Artifact compatibility

A new artifact build is never “the same release artifact” merely because source SHA matches. Artifact immutable identity is distinct and provenance must identify the build.

Changing the mechanism that maps deployed/running workload to `release.artifact@1` is compatibility-sensitive. Desired-state object, mutable tag or deployment receipt cannot silently replace independently observed immutable runtime artifact identity. `RLV-043` applies.

## Configuration compatibility

Configuration-only changes may be semantic/security breaking. Changes to tenant/security/network/runtime/failure/Product/recovery behavior follow the owning higher-level compatibility rules.

## Mixed-version compatibility

Review includes old/new combinations of API, event, runtime, schema, configuration and workers, plus current authority generations, release policy/verifier state and historical evidence interpretation.

## Migration compatibility

Changing expand/migrate/contract ordering, backfill resume semantics, lock/fence ownership or destructive-contract prerequisites is breaking.

## Rollback compatibility

A change from `rollback_eligible` to any stricter class is material. Rollback support cannot be advertised after irreversible schema/effect/security state makes old runtime unsafe.

Rollback of release control-plane state is also unsafe when it would restore a retired promotion approval, broader old principal, obsolete verifier or weaker release policy.

## Evidence compatibility

Changing provenance/SBOM/signature/attestation interpretation, verifier authority, runtime-artifact observation, retention or correlation is compatibility-sensitive even if artifact bytes are unchanged.

## Downgrade

If a previous runtime or release-policy/verifier state cannot safely interpret current authoritative state, downgrade is prohibited; forward recovery or quarantine is required.