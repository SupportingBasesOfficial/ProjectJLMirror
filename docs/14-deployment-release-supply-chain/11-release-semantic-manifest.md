# Phase 14 — Release Semantic Manifest

**Status:** proposed baseline

## Purpose

This manifest is the enforcement-oriented join for Phase 14.

## Release record schema

Every releasable candidate materializes:

```text
release_id
source_state_id
source_trust_class
release_policy_profile_and_version
artifact_id
artifact_integrity_identity
build_record_id
builder_principal_class
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
runtime_observed_artifact_identity_or_equivalent
rollback_forward_recovery_class
release validation vectors
OPEN decisions
release evidence references
```

Omission is not `NO_APPLICABLE_CASE`. A conforming implementation records an exact canonical binding, fixed rule, explicit OPEN owner or evidence-backed `NO_APPLICABLE_CASE` with enclosing evidence/impact path.

## Canonical source trust classes

```text
source.untrusted-candidate@1
source.accepted-review-state@1
```

A branch name, repository event or successful validation job cannot change the source trust class. Transition to `source.accepted-review-state@1` requires accepted repository/change authority and exact source-state evidence.

## Canonical release principals

```text
principal.release-untrusted-validation@1
principal.release-build@1
principal.release-publish@1
principal.release-promote@1
principal.release-deploy@1
principal.release-migrate@1
principal.release-verify@1
principal.release-emergency@1
```

`principal.release-untrusted-validation@1` cannot sign/publish a trusted release artifact, promote/deploy production, run privileged migration, read production release secrets or choose a broader principal class from candidate-controlled workflow input.

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
| source candidate validation | exact candidate SHA + `source.untrusted-candidate@1` + bounded validation principal | PR/branch/event as trusted authority |
| accepted source | exact source SHA/state + accepted review/change provenance + trusted policy profile/version | branch/tag name or validation success alone |
| dependency/build input | integrity-bound declared input set | mutable/floating undeclared input |
| build | accepted source + authorized builder/profile + input record + trusted release-policy profile | successful job or candidate-selected privileged runner |
| artifact | immutable content identity | mutable tag/location |
| provenance | source+inputs+builder->artifact evidence | signature validity without trusted issuer/currentness |
| promotion | exact artifact + environment + evidence + current authority | registry presence or stale approval |
| deployment | promotion + target + principal + compatibility + current policy | pipeline job existence |
| runtime verification | independently observed running artifact identity/equivalent + Phase 13/12 admission evidence | deploy-controller success or vendor green alone |

## Release policy currentness

The policy/profile version governing source trust transition, principal selection, promotion, deployment and verification is recorded as release evidence and cannot be selected or weakened unilaterally by the candidate source it evaluates.

Restore/rollback to an older release-policy state does not make retired approvals, principals, verifier trust or broader historical privileges current. If policy currentness cannot be established, privileged release advancement fails closed.

## Environment join

The manifest uses exact Phase 13 environment IDs. Promotion/deployment never resolves tenant/Product/security authority from the environment label.

## Runtime join

Each deployment identifies exact Phase 13 runtime profiles/worker specializations and allowed environment classes. Release principal authority does not transfer into runtime principals.

Runtime verification proves that the executing/deployed runtime corresponds to the approved immutable artifact identity (or an explicitly reviewed equivalent identity mapping). A deployment-controller receipt, desired-state object or mutable image tag alone is not proof of running artifact identity.

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

`RLV-001..044` apply according to stage. `RLV-041..044` are mandatory where untrusted-source validation, candidate-controlled workflow/policy, runtime artifact verification or restored release-policy currentness can affect release authority.

Any future manifest field added with authority/compatibility effect is semantic and requires compatibility review.

## OPEN discipline

Concrete implementation expands every selected `OPEN-RLS-*` to exact disposition/evidence. Tool defaults do not become manifest values silently.