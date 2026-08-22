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
Includes changes to artifact identity, provenance meaning, promotion/deployment authority, environment mapping semantics, principal separation, mixed-version support, migration step meaning, rollback eligibility, pause/abort gates or evidence disposition.

### RLS-COMP-D — security/recovery sensitive
Includes broadened CI/CD principal, secret exposure, weaker artifact verification, stale approval reuse, production/lower-environment bleed, rollback of revocation/governance/reliability state, migration-owner reuse, supply-chain evidence loss or release authority inferred from tool defaults.

## Tool replacement

Replacing CI/CD, registry, scanner, signing service, orchestrator or cloud mechanism is compatible only when logical source/build/artifact/promotion/deployment/runtime-verification semantics and evidence remain equivalent.

## Artifact compatibility

A new artifact build is never “the same release artifact” merely because source SHA matches. Artifact immutable identity is distinct and provenance must identify the build.

## Configuration compatibility

Configuration-only changes may be semantic/security breaking. Changes to tenant/security/network/runtime/failure/Product/recovery behavior follow the owning higher-level compatibility rules.

## Mixed-version compatibility

Review includes old/new combinations of API, event, runtime, schema, configuration and workers, plus current authority generations and historical evidence interpretation.

## Migration compatibility

Changing expand/migrate/contract ordering, backfill resume semantics, lock/fence ownership or destructive-contract prerequisites is breaking.

## Rollback compatibility

A change from `rollback_eligible` to any stricter class is material. Rollback support cannot be advertised after irreversible schema/effect/security state makes old runtime unsafe.

## Evidence compatibility

Changing provenance/SBOM/signature/attestation interpretation, verifier authority, retention or correlation is compatibility-sensitive even if artifact bytes are unchanged.

## Downgrade

If a previous runtime cannot safely interpret current authoritative state, downgrade is prohibited; forward recovery or quarantine is required.