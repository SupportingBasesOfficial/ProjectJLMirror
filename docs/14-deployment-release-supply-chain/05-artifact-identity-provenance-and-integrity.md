# Phase 14 — Artifact Identity, Provenance and Integrity Profiles

**Status:** proposed baseline

## Artifact identity

`release.artifact@1` is immutable. Its identity is bound to artifact content through a collision-resistant content identity or reviewed equivalent. Mutable tags/labels may point to an artifact but never replace immutable identity.

## Artifact profile

A release artifact record includes:

```text
artifact_id
artifact_digest_or_equivalent
artifact_type/profile
source_state_id
build_record_id
provenance_record_id
SBOM_reference_or_equivalent_dependency_inventory
created_at
attestation/signature profile references
retirement state
```

## Provenance

`release.provenance@1` establishes a verifiable relationship among exact source state, build inputs, builder identity/profile, build execution and resulting artifact identity.

Provenance is evidence, not authorization. A valid signature from an unauthorized/stale issuer is not trusted release evidence.

## Integrity verification

Integrity/provenance verification occurs before promotion eligibility and again at deployment/runtime verification boundaries where substitution is possible.

Artifact bytes pulled at deployment must correspond to the approved immutable identity; a human-readable tag alone is insufficient.

## SBOM / dependency inventory

The release records a dependency/component inventory sufficient for vulnerability, incident and retirement analysis. Exact SBOM format/tool remains OPEN.

## Signing / attestation

Phase 14 requires authenticity/integrity properties but does not select signing algorithm, KMS/HSM, keyless mechanism or vendor.

Signing keys/attestation authorities are independently revocable/rotatable. Historical artifacts preserve verifiability or receive a reviewed equivalent migration before retirement of required verifier authority.

## Registry semantics

Registry/storage location is not artifact identity, promotion authority or release state. Copying the same immutable artifact across physical registries preserves identity only if byte/integrity equivalence is proven.

## Tamper response

Digest/provenance/signature mismatch is fail-closed for promotion/deployment. It is not repaired by retagging the unexpected bytes under the expected release name.

## Artifact retirement

Retirement prevents new promotion/deployment under the retired authority while preserving evidence needed for incident, audit, rollback eligibility and governance. Physical deletion is separately governed.

## Confidentiality

Provenance/SBOM/evidence are classified. They must not leak secrets, private credentials, protected topology or tenant data merely to maximize detail.