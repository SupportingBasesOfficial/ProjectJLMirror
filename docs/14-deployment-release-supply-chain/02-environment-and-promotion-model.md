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

## One-artifact promotion rule

A release candidate is built once into immutable `release.artifact@1`. The same artifact identity is promoted between logical environments.

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
  -> validation promotion of A
  -> production promotion of A
```

Environment-specific behavior is provided through separately governed non-secret configuration and secret references, never by rebuilding source into a different artifact under the same release identity.

## Promotion object

A promotion record includes at least:

```text
promotion_id
artifact_id / immutable artifact digest
target_environment_class
source_environment_or_evidence_class
runtime_profile_set
configuration_generation_or_candidate
schema/contract compatibility set
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

## Production promotion

Production promotion requires:

- exact immutable artifact identity;
- accepted source/build/provenance evidence;
- compatible API/event/schema/runtime matrix;
- required security/reliability/observability gates;
- current release/promotion authority;
- exact target cell/wave scope;
- configuration/secret references appropriate to production;
- no unresolved release-blocking ambiguity.

## Recovery environment

`environment.recovery@1` is not an ordinary promotion destination for serving traffic. Recovery deployments are constrained by Phase 13 recovery authority and Phase 15 operational recovery procedures. Reachability or successful restore never promotes recovery state into production authority.

## Physical mapping

Cloud account/project/subscription, cluster, namespace, registry, region and pipeline mapping remain implementation choices. They SHALL preserve logical environment isolation and are tracked under Phase 13 `OPEN-PRT-035` plus Phase 14 OPEN decisions.

## Cross-environment prohibitions

- production workload credentials are not copied down by convenience;
- production secrets are not embedded into artifacts;
- production tenant traffic/data are not admitted into lower environments without governed purpose/minimization;
- validation success cannot directly mutate production;
- an artifact being present in a production registry/location is not promotion or deployment authority;
- promotion metadata never changes canonical tenant/resource/API/event identity.