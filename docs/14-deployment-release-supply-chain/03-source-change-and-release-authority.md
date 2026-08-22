# Phase 14 — Source, Change and Release Authority

**Status:** proposed baseline

## Authority separation

Phase 14 distinguishes these authorities:

```text
source_change_authority
review_assurance_authority
authorized_build_identity
artifact_attestation_authority
promotion_authority
deployment_authority
migration_authority
emergency_change_authority
runtime_authority (Phase 13, separate)
```

No principal implicitly owns all stages.

## Source state

A releasable source state is identified by immutable repository/source identity sufficient to reproduce the reviewed inputs. Branch name alone is insufficient.

The release record binds the exact source SHA and applicable accepted contract/profile versions.

## Change authority

A source change may be proposed by an authorized contributor/tool workflow, but proposal does not equal acceptance. Automated systems may analyze/report/block under repository assurance governance; they do not gain silent mutation or merge authority.

## Review and merge

Repository merge authorization remains distinct from release authorization. A merged source SHA may be eligible for build but is not automatically authorized for production promotion.

## Release authority

Promotion/deployment approvals are explicit bounded decisions over:

- exact artifact identity;
- target environment;
- runtime/cell/wave scope;
- configuration candidate/generation;
- migration/backfill state;
- compatibility evidence;
- required release evidence;
- expiry/supersession where applicable.

## Separation of duties

A compliant design avoids one omnipotent CI principal that can modify source, forge provenance, publish arbitrary artifact, alter production configuration, obtain production secrets, run migrations, deploy, disable evidence and approve itself.

Where physical tooling combines stages, logical principal scopes and independently verifiable evidence still preserve separation.

## Human vs machine authority

Machine identities execute bounded release actions. Human authorization, when required, is represented as an explicit decision/evidence input rather than ambient workstation credential inheritance.

## Repository automation boundary

The existing JLMIRROR deterministic assurance workflow remains observer-only. Phase 14 does not reinterpret it as production release authority.

Future release automation may have bounded write authority to release systems, but SHALL NOT use that authority to silently mutate normative repository state or self-authorize merges.

## Revocation/currentness

Release/promotion/deployment credentials and approvals are revocable. Revocation does not require changing artifact identity. A stale approval/principal cannot become current because an old pipeline run resumes.

## Evidence

Every privileged release mutation is attributable to principal, exact requested operation, target, artifact/config/migration state, result and timestamp/order without exposing secret material.