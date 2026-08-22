# Phase 14 — Source, Change and Release Authority

**Status:** proposed baseline

## Authority separation

Phase 14 distinguishes these authorities:

```text
source_change_authority
review_assurance_authority
untrusted_validation_authority
authorized_build_identity
artifact_attestation_authority
promotion_authority
deployment_authority
migration_authority
release_policy_authority
emergency_change_authority
runtime_authority (Phase 13, separate)
```

No principal implicitly owns all stages.

## Canonical source trust classes

```text
source.untrusted-candidate@1
source.accepted-review-state@1
```

All not-yet-accepted candidate source, including candidate-controlled workflow/build definitions, begins as `source.untrusted-candidate@1` for privileged release-authority purposes.

Transition to `source.accepted-review-state@1` requires an exact immutable source state plus accepted source/change and repository governance evidence. Branch name, PR state, repository membership, validation success, CI green or workflow trigger is insufficient.

## Source state

A releasable source state is identified by immutable repository/source identity sufficient to reproduce the reviewed inputs. Branch name alone is insufficient.

The release record binds the exact source SHA, source trust class, trusted release-policy profile/version and applicable accepted contract/profile versions.

## Untrusted validation authority

`principal.release-untrusted-validation@1` or equivalent bounded authority may execute tests/scans against candidate source, but its results are evidence only.

It SHALL NOT by candidate-controlled trigger or workflow choice gain:

- trusted artifact publication/overwrite authority;
- production promotion/deployment authority;
- migration/admin authority;
- trusted provenance/attestation signing authority;
- production secrets/credentials;
- privileged internal network access outside the validation profile;
- authority to rewrite the trusted policy that classifies the same candidate.

The candidate cannot upgrade its own source trust class.

## Change authority

A source change may be proposed by an authorized contributor/tool workflow, but proposal does not equal acceptance. Automated systems may analyze/report/block under repository assurance governance; they do not gain silent mutation or merge authority.

## Review and merge

Repository merge authorization remains distinct from release authorization. A merged source SHA may become accepted source input under repository governance but is not automatically authorized for production promotion.

Review evidence for one SHA cannot be reused as acceptance of a materially different source state.

## Trusted release-policy authority

The profile/version that decides source trust transition, principal selection, promotion/deployment admission and verifier trust is explicit continuity state.

Candidate source cannot select or weaken it unilaterally. Restore/rollback of release control-plane state cannot make an obsolete release policy, retired approval, broader historical principal or retired verifier authority current.

If current release-policy authority cannot be proven, privileged advancement fails closed until reconciled forward.

## Target configuration authority/evidence

Configuration is a separately identified release input. Same immutable artifact does not confer authority to deploy any environment configuration.

Every target promotion/deployment decision binds:

```text
target_configuration_identity/generation
target_configuration_semantic_profile
validation_to_target_configuration_evidence
```

When validation evidence was produced under a different configuration identity/profile, the approval authority SHALL require explicit release-relevant semantic compatibility/equivalence evidence or target-specific applicable validation before treating the target configuration as eligible.

Differences affecting trust, authorization, tenant isolation, network/egress, Product behavior, failure/retry semantics, schema/API/event behavior, runtime authority, SLI meaning, recovery or release admission are material.

Production secret values are not copied into validation or approval evidence to manufacture equality. Secret-reference purpose/policy and consuming semantics are compared without disclosing secret material.

`RLV-049` is the canonical falsification path.

## Release authority

Promotion/deployment approvals are explicit bounded decisions over:

- exact artifact identity;
- exact accepted source/build/provenance relationship;
- target environment and validation scope;
- runtime/cell/wave scope;
- exact target configuration identity/generation and semantic profile;
- validation-to-target configuration compatibility/equivalence or target-specific validation evidence;
- migration/backfill and cell compatibility state;
- compatibility evidence;
- required release evidence;
- trusted release-policy profile/currentness;
- expiry/supersession where applicable.

An approval is not a reusable bearer capability for an arbitrary later artifact/configuration/target. Changing target configuration identity/profile invalidates silent approval reuse unless the owning evidence explicitly covers the new state.

## Separation of duties

A compliant design avoids one omnipotent CI principal that can modify source, forge provenance, publish arbitrary artifact, alter production configuration, obtain production secrets, run migrations, deploy, disable evidence and approve itself.

Where physical tooling combines stages, logical principal scopes and independently verifiable evidence still preserve separation.

## Human vs machine authority

Machine identities execute bounded release actions. Human authorization, when required, is represented as an explicit decision/evidence input rather than ambient workstation credential inheritance.

## Repository automation boundary

The existing JLMIRROR deterministic assurance workflow remains observer-only. Phase 14 does not reinterpret it as source acceptance, production release authority or proof that candidate source deserves a privileged evaluator.

Future release automation may have bounded write authority to release systems, but SHALL NOT use that authority to silently mutate normative repository state or self-authorize merges.

## Revocation/currentness

Release/promotion/deployment credentials, approvals, policy profiles and verifier authorities are revocable/retirable according to their owning contracts. Revocation does not require changing artifact identity.

A stale approval/principal/policy/verifier cannot become current because an old pipeline run resumes or a restored release system is reachable. Resume revalidates current source trust, policy, principal, artifact, exact target configuration identity/profile/evidence, target and approval state.

A restored or superseded target configuration generation cannot regain release eligibility merely because an older approval/equivalence record is still readable.

## Evidence

Every privileged release mutation is attributable to exact source trust state, trusted policy profile/version, principal, requested operation, target, artifact, target configuration identity/generation/profile and validation-to-target evidence, migration/cell-compatibility state, result and timestamp/order without exposing secret material.

`RLV-041`, `RLV-042`, `RLV-044` and `RLV-049` are canonical falsification paths for this authority boundary.
