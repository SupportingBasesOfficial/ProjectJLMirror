# Phase 14 — Artifact Identity, Provenance and Integrity Profiles

**Status:** proposed baseline

## Artifact identity

`release.artifact@1` is immutable. Its identity is bound to artifact content through a collision-resistant content identity or reviewed equivalent. Mutable tags/labels may point to an artifact but never replace immutable identity.

A new build produces a distinct artifact identity even when source SHA is unchanged unless the selected build mechanism proves the exact same immutable artifact identity under accepted provenance semantics.

## Artifact profile

A release artifact record includes:

```text
artifact_id
artifact_digest_or_equivalent
artifact_type/profile
source_state_id
source_trust_class
build_record_id
provenance_record_id
SBOM_reference_or_equivalent_dependency_inventory
created_at
attestation/signature profile references
verifier_authority_profile/version references
retirement state
```

## Provenance

`release.provenance@1` establishes a verifiable relationship among exact accepted source state, declared build inputs, authorized builder identity/profile, trusted release-policy profile, build execution and resulting artifact identity.

Provenance is evidence, not authorization. A valid signature from an unauthorized, retired, stale or restored-obsolete issuer/verifier is not trusted release evidence.

Candidate validation evidence produced under `source.untrusted-candidate@1` cannot be re-labeled as trusted release provenance merely because the validation job succeeded.

## Integrity verification

Integrity/provenance verification occurs before promotion eligibility and again at deployment/runtime verification boundaries where substitution is possible.

Artifact bytes pulled at deployment must correspond to the approved immutable identity; a human-readable tag alone is insufficient.

## Runtime-observed artifact identity

`release.runtime-verification@1` establishes that the actually executing workload corresponds to the approved `release.artifact@1` identity or an explicitly reviewed equivalent mapping.

Evidence based only on any of the following is insufficient by itself:

- desired-state manifest/controller object;
- mutable image/package tag;
- deployment API success receipt;
- registry path;
- process liveness/readiness;
- vendor-native “deployed” or “healthy” state.

The observation mechanism may be implementation-specific, but it SHALL resist a substitution in which the controller intended artifact A while the running workload executes artifact B. `RLV-043` is the canonical falsification vector.

## SBOM / dependency inventory

The release records a dependency/component inventory sufficient for vulnerability, incident and retirement analysis. Exact SBOM format/tool remains OPEN.

A material mismatch between dependency inventory and artifact/provenance evidence is release-blocking until reconciled; an SBOM generated from source assumptions alone cannot silently override evidence of different artifact contents.

## Signing / attestation

Phase 14 requires authenticity/integrity properties but does not select signing algorithm, KMS/HSM, keyless mechanism or vendor.

Signing keys/attestation authorities are independently revocable/rotatable. Historical artifacts preserve verifiability or receive a reviewed equivalent migration before retirement of required verifier authority.

Verifier trust/currentness is continuity state. Restore or rollback of the release system SHALL NOT make a retired signing/attestation issuer or obsolete verifier policy trusted again. If historical evidence can no longer be interpreted safely, affected promotion/deployment/rollback eligibility remains blocked until reviewed reconciliation/migration restores an accepted verification path. `RLV-044` applies.

## Registry semantics

Registry/storage location is not artifact identity, promotion authority or release state. Copying the same immutable artifact across physical registries preserves identity only if byte/integrity equivalence is proven.

A registry restore that resurrects a retired tag/artifact does not restore promotion eligibility or verifier trust.

## Tamper response

Digest/provenance/signature/runtime-identity mismatch is fail-closed for promotion/deployment/admission. It is not repaired by retagging the unexpected bytes under the expected release name or by recording a new desired-state object after the fact.

## Artifact retirement

Retirement prevents new promotion/deployment under the retired authority while preserving evidence needed for incident, audit, rollback eligibility and governance. Physical deletion is separately governed.

Retirement of artifact bytes, signing authorities or verifier profiles SHALL be coordinated so evidence needed to establish historical release state remains interpretable for the required governance/incident/recovery horizon or has an accepted equivalent migration.

## Confidentiality

Provenance/SBOM/evidence are classified. They must not leak secrets, private credentials, protected topology or tenant data merely to maximize detail.

Runtime artifact verification exposes only the minimum immutable identity/provenance needed for release assurance and SHALL NOT turn internal topology, secret references or tenant identifiers into public release metadata.