# Phase 14 — Release Semantic Manifest

**Status:** proposed baseline

## Purpose

This manifest is the enforcement-oriented join for Phase 14.

## Release record schema

Every releasable candidate materializes:

```text
release_id
source_state_id
artifact_id
artifact_integrity_identity
build_record_id
provenance_profile
SBOM_or_dependency_inventory_reference
artifact_attestation_profile
runtime_profile_set
target_environment_class
configuration_identity/generation
schema_state / migration compatibility
API compatibility family
Event compatibility set
promotion_state
deployment_state
rollout_scope/wave
release principal identities
required Phase 11 reliability gates
required Phase 12 health/security gates
required Phase 13 runtime/environment conformance
rollback_forward_recovery_class
release validation vectors
OPEN decisions
release evidence references
```

Omission is not `NO_APPLICABLE_CASE`.

## Canonical release principals

```text
principal.release-build@1
principal.release-publish@1
principal.release-promote@1
principal.release-deploy@1
principal.release-migrate@1
principal.release-verify@1
principal.release-emergency@1
```

## Canonical promotion states

```text
proposed
validating
eligible
approved
deploying
runtime_verification
completed
paused
rejected
aborted
superseded
reconciliation_required
```

## Canonical outcome classes

```text
rollback_eligible
forward_recovery_required
reconciliation_required
irreversible_without_governed_migration
```

## Canonical trust joins

| Stage | Required identity/evidence | Forbidden substitution |
|---|---|---|
| source | exact source SHA/state + review provenance | branch/tag name alone |
| dependency/build input | integrity-bound declared input set | mutable/floating undeclared input |
| build | authorized builder/profile + input record | successful job alone |
| artifact | immutable content identity | mutable tag/location |
| provenance | source+inputs+builder->artifact evidence | signature validity without trusted issuer/currentness |
| promotion | exact artifact + environment + evidence + authority | registry presence |
| deployment | promotion + target + principal + compatibility | pipeline job existence |
| runtime verification | deployed immutable identity + Phase 13/12 admission evidence | vendor green/ready alone |

## Environment join

The manifest uses exact Phase 13 environment IDs. Promotion/deployment never resolves tenant/Product/security authority from the environment label.

## Runtime join

Each deployment identifies exact Phase 13 runtime profiles/worker specializations and allowed environment classes. Release principal authority does not transfer into runtime principals.

## Mixed-version join

A release declares old/new compatibility across runtime, schema, API, event and semantic configuration before coexistence is admitted.

## Migration join

If schema/data evolution is present, the release records current step:

```text
expand
compatible_runtime_deployed
migrate_backfill
switch
observe_verify
contract
```

and the exact migration/backfill operation identities.

## Progressive rollout join

Production deployment records canary/wave scope, accepted pause/abort signals, capacity envelope and runtime verification evidence.

## Cross-cutting validation

`RLV-001..040` apply according to stage. Any future manifest field added with authority/compatibility effect is semantic and requires compatibility review.

## OPEN discipline

Concrete implementation expands every selected `OPEN-RLS-*` to exact disposition/evidence. Tool defaults do not become manifest values silently.