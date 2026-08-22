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
validation_scope/evidence_class
target_configuration_identity/generation
target_configuration_semantic_profile
validation_to_target_configuration_evidence
schema_state / migration compatibility
cell_compatibility_metadata_identity_or_NO_APPLICABLE_CASE
API compatibility family
Event compatibility set
promotion_state
deployment_state
deployment_operation_id
expected_release_target_state_version
resulting_release_target_state_version_or_pending
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

## Canonical validation evidence scopes

```text
validation.general@1
validation.reference-cell@1
```

These scopes both live inside `environment.validation@1`; they are not new Phase 13 environment classes.

`validation.reference-cell@1` is mandatory for cell/runtime/schema-affecting releases covered by the accepted Data staged-rollout requirement unless an evidence-backed `NO_APPLICABLE_CASE` proves that the specific release does not require a reference-cell stage.

## Configuration evidence rule

The one-artifact rule does not create a one-configuration rule.

Each target deployment records the exact target configuration identity/generation and semantic profile. Validation evidence may be reused across environment-scoped configurations only when `validation_to_target_configuration_evidence` proves that release-relevant differences are compatible/equivalent; material differences require target-specific applicable validation.

Material dimensions include trust, authorization, tenant isolation, network/egress, Product behavior, failure/retry semantics, schema/API/event behavior, runtime authority, SLI meaning, recovery and release admission gates.

Environment-specific secret values are never copied into validation to prove equality. Evidence compares allowed secret-reference purposes/policies and consuming semantics without disclosing secret material.

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

## Release operation identity and target fencing

Every effectful deployment (and any migration/backfill transition whose owning contract requires it) has a stable logical operation identity.

For deployment:

```text
deployment_operation_id
expected_release_target_state_version
requested immutable artifact + exact target configuration + target semantics
resulting_release_target_state_version_or_pending
terminal/reconciliation state
```

Rules:

- same operation ID + same immutable semantics = create-or-observe/retry of the same logical operation;
- same operation ID + conflicting immutable semantics = integrity conflict;
- a new operation ID does not bypass an unresolved prior operation on the same protected target;
- incompatible concurrent operations on the same target cannot both become current;
- stale executors observing a newer target release state lose effectful eligibility;
- timeout/process death/lost response does not prove target effect absence;
- ambiguous operations become `reconciliation_required` until durable target/runtime evidence resolves them.

`release_target_state_version` is owned by the Phase 14 release control plane. It is not `runtime_generation`, `placement_version`, cell admission, Product authority or tenant authorization.

The exact coordination/CAS/lease/store mechanism remains `OPEN-RLS-027`.

## Canonical trust joins

| Stage | Required identity/evidence | Forbidden substitution |
|---|---|---|
| source candidate validation | exact candidate SHA + `source.untrusted-candidate@1` + bounded validation principal | PR/branch/event as trusted authority |
| accepted source | exact source SHA/state + accepted review/change provenance + trusted policy profile/version | branch/tag name or validation success alone |
| dependency/build input | integrity-bound declared input set | mutable/floating undeclared input |
| build | accepted source + authorized builder/profile + input record + trusted release-policy profile | successful job or candidate-selected privileged runner |
| artifact | immutable content identity | mutable tag/location |
| provenance | source+inputs+builder->artifact evidence | signature validity without trusted issuer/currentness |
| validation general | same immutable artifact + exact validation configuration/profile + evidence | rebuild or assumed target-config safety |
| validation reference cell | same immutable artifact + production-relevant validation configuration semantic profile + schema/runtime evidence | copying production secrets or requiring byte-identical config |
| target configuration | exact target config/generation/profile + validation-to-target compatibility/equivalence or target-specific validation | same artifact as proof that config is safe |
| promotion | exact artifact + target config + environment + evidence + current authority | registry presence or stale approval |
| deployment admission | stable operation ID + expected target state + promotion + target + principal + compatibility + current policy | pipeline job existence or stale executor |
| deployment ambiguity resolution | durable operation/target/runtime evidence | timeout, crash or lost response as proof of no effect |
| runtime verification | independently observed running artifact identity/equivalent + exact target config/currentness + Phase 13/12 admission evidence | deploy-controller success or vendor green alone |

## Release policy currentness

The policy/profile version governing source trust transition, principal selection, promotion, deployment and verification is recorded as release evidence and cannot be selected or weakened unilaterally by the candidate source it evaluates.

Restore/rollback to an older release-policy state does not make retired approvals, principals, verifier trust or broader historical privileges current. If policy currentness cannot be established, privileged release advancement fails closed.

## Environment join

The manifest uses exact Phase 13 environment IDs. Promotion/deployment never resolves tenant/Product/security authority from the environment label.

For cell-affecting releases, the validation chain preserves accepted Data semantics without inventing a new environment class:

```text
environment.validation@1 / validation.general@1
 -> environment.validation@1 / validation.reference-cell@1
 -> environment.production@1 / production canary
 -> bounded production waves
```

The immutable artifact stays identical across this chain. Environment-scoped configuration identities may differ only with explicit validation-to-target configuration evidence.

## Cell compatibility metadata join

When placement/rollout safety depends on cell runtime/schema compatibility, the release record binds the current accepted Control Plane cell compatibility metadata identity/version/equivalent.

The metadata represents current/target runtime/schema compatibility sufficient for placement and release safety. It is not caller-selected and cannot be inferred from deployment success alone.

A cell/tenant cannot be admitted or cut over when the current cell compatibility record disagrees with the release mixed-version matrix or target configuration semantics. Stale metadata does not override a newer deny/incompatible state.

## Runtime join

Each deployment identifies exact Phase 13 runtime profiles/worker specializations and allowed environment classes. Release principal authority does not transfer into runtime principals.

Runtime verification proves that the executing/deployed runtime corresponds to the approved immutable artifact identity (or an explicitly reviewed equivalent identity mapping) and the exact target configuration generation/currentness. A deployment-controller receipt, desired-state object or mutable image tag alone is not proof of running artifact identity/configuration safety.

Release-target fencing and Phase 13 runtime/placement fencing are independent checks; one green/current value cannot substitute for the other.

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

and the exact migration/backfill operation identities/fences required by their owning contract.

Before `contract`, active/supported cell compatibility metadata must no longer advertise a runtime/schema/configuration combination that depends on the structure being removed.

## Progressive rollout join

Production deployment records validation scope, exact target configuration identity/profile/evidence, stable deployment operation identity, expected/resulting release-target state, canary/wave scope, accepted pause/abort signals, capacity envelope, cell compatibility metadata where applicable and runtime verification evidence.

## Cross-cutting validation

`RLV-001..049` apply according to stage. `RLV-041..044` are mandatory where untrusted-source validation, candidate-controlled workflow/policy, runtime artifact verification or restored release-policy currentness can affect release authority. `RLV-045..046` are mandatory for cell-affecting releases/reference-cell and cell-compatibility metadata paths. `RLV-047..048` are mandatory for effectful deployment concurrency and ambiguous-outcome retry paths. `RLV-049` applies whenever validation evidence is reused for a different target configuration identity/profile.

Any future manifest field added with authority/compatibility effect is semantic and requires compatibility review.

## OPEN discipline

Concrete implementation expands every selected `OPEN-RLS-*` to exact disposition/evidence. Tool defaults do not become manifest values silently.