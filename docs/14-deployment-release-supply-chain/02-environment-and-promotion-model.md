# Phase 14 — Environment and Promotion Model

**Status:** proposed baseline

## Purpose

This document defines promotion semantics over the Phase 13 logical environment classes. Promotion changes artifact/config eligibility; it does not create Product, tenant, security or placement authority.

## Canonical environment classes

Phase 14 consumes, unchanged:

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Phase 14 SHALL NOT invent a fifth logical `staging` environment class merely to satisfy rollout terminology. The accepted Data rollout step “staging/reference cell” is represented as a bounded validation scope inside `environment.validation@1`.

## Validation scopes

Within `environment.validation@1`, release evidence distinguishes at least:

```text
validation.general@1
validation.reference-cell@1
```

These are rollout/evidence scopes, not new environment authorities.

- `validation.general@1` covers ordinary pre-production functional, contract, security and integration validation appropriate to the release.
- `validation.reference-cell@1` is required for cell/runtime/schema changes whose accepted Data/Platform semantics require proving the change on a production-like reference cell before production canary admission.

A validation reference cell remains non-production authority. It may mirror production runtime semantics/config shape where necessary without receiving production tenant authority, production secrets or production placement authority by label.

## One-artifact promotion rule

A release candidate is built once into immutable `release.artifact@1`. The same artifact identity is promoted between logical environments/scopes.

Forbidden default:

```text
source -> build-for-validation
same source -> rebuild-for-production
```

Required shape:

```text
reviewed source S
  -> build B
  -> immutable artifact A
  -> validation.general of A
  -> validation.reference-cell of A when applicable
  -> production promotion of A
```

Environment-specific behavior is provided through separately governed configuration and secret references, never by rebuilding source into a different artifact under the same release identity.

## Artifact sameness vs configuration compatibility

The same immutable artifact is promoted, but validation and production configuration are not required to be byte-identical.

Production promotion binds an exact production configuration identity/generation plus evidence showing that release-relevant differences from validated configuration are compatible/equivalent, or that material target-specific differences were separately validated.

Environment-specific endpoints, resource settings and secret references may differ under accepted profiles. Differences affecting trust, authorization, tenant isolation, network/egress, Product behavior, failure/retry semantics, schema/API/event behavior, runtime authority, SLI meaning, recovery or release gates are material and cannot inherit validation evidence silently.

Production secret values are never copied into validation to manufacture configuration equality. Secret-purpose/reference semantics may be compared without exposing secret material.

## Promotion object

A promotion record includes at least:

```text
promotion_id
artifact_id / immutable artifact digest
target_environment_class
validation_scope_or_evidence_class
runtime_profile_set
target_configuration_identity/generation
target_configuration_semantic_profile
validation_to_target_configuration_evidence
schema/contract compatibility set
cell compatibility metadata version/evidence when applicable
required evidence set
promotion_authority
approved_at
expiry/retirement state where applicable
```

## Promotion state model

```text
proposed
 -> validating
 -> eligible
 -> approved
 -> deploying
 -> runtime_verification
 -> completed

side states:
 paused
 rejected
 aborted
 superseded
 reconciliation_required
```

`completed` means the bounded deployment objective is achieved; it does not imply business correctness beyond the evidence profile.

## Validation environment

`environment.validation@1` is the mandatory logical pre-production conformance surface for release-candidate evidence that requires deployed behavior. It may be production-like but receives no production authority by label.

For a cell-affecting release, production canary eligibility requires the applicable `validation.reference-cell@1` evidence unless a higher accepted authority explicitly classifies the release as `NO_APPLICABLE_CASE` with evidence.

Reference-cell evidence binds the same immutable artifact and the validated configuration semantic profile. Production may use a distinct environment-scoped configuration only when the validation-to-target configuration relationship is explicitly accounted for.

## Production promotion

Production promotion requires:

- exact immutable artifact identity;
- accepted source/build/provenance evidence;
- applicable validation scopes completed on the same artifact;
- exact production configuration identity/generation and semantic profile;
- validation-to-production configuration compatibility/equivalence evidence or target-specific validation for material differences;
- compatible API/event/schema/runtime matrix;
- current Control Plane cell compatibility metadata/evidence where placement/cutover safety depends on it;
- required security/reliability/observability gates;
- current release/promotion authority;
- exact target cell/wave scope;
- environment-appropriate secret references without copying production secret values into validation;
- no unresolved release-blocking ambiguity.

## Recovery environment

`environment.recovery@1` is not an ordinary promotion destination for serving traffic. Recovery deployments are constrained by Phase 13 recovery authority and Phase 15 operational recovery procedures. Reachability or successful restore never promotes recovery state into production authority.

## Physical mapping

Cloud account/project/subscription, cluster, namespace, registry, region and pipeline mapping remain implementation choices. They SHALL preserve logical environment isolation and are tracked under Phase 13 `OPEN-PRT-035` plus Phase 14 OPEN decisions.

## Cross-environment prohibitions

- production workload credentials are not copied down by convenience;
- production secrets are not embedded into artifacts or validation configuration;
- production tenant traffic/data are not admitted into lower environments without governed purpose/minimization;
- validation success cannot directly mutate production;
- validation evidence cannot be reused across a material target-configuration difference without explicit compatibility/validation evidence;
- validation reference-cell state cannot become authoritative production placement state by reuse;
- an artifact being present in a production registry/location is not promotion or deployment authority;
- promotion metadata never changes canonical tenant/resource/API/event identity.

`RLV-049` falsifies validation-to-production configuration evidence laundering.