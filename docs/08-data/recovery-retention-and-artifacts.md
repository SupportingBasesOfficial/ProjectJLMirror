# Recovery, Retention and Artifacts

**Status:** proposed baseline  
**Primary ADR:** ADR-018

## Recovery scopes

JLMIRROR distinguishes:

- Control Plane recovery;
- whole-cell transactional recovery;
- tenant-level logical recovery within a pooled cell;
- telemetry recovery/reconstruction;
- artifact/object recovery;
- configuration/secret-reference recovery.

A backup is not a recovery capability until restoration is rehearsed.

## Control Plane recovery

Placement/lifecycle metadata is high criticality. Recovery must restore a consistent tenant-to-cell authority and prevent routing to ambiguous/stale placement. Restore procedures include validation of cell/placement versions before normal topology changes resume.

## Cell physical recovery

Cell transactional PostgreSQL uses encrypted backup and point-in-time recovery capabilities selected by platform design. Cell recovery occurs to a controlled target, validates schema/invariants and only then resumes admitted traffic.

## Tenant-level recovery in pooled cells

Physical PITR restores an entire database, not one logical tenant. Therefore tenant recovery uses an isolated recovery environment:

```text
restore cell snapshot/PITR to quarantine
   -> select tenant rows by tenant_id across owned schemas
   -> validate relationships/invariants/audit/outbox state
   -> build tenant recovery set
   -> controlled reintroduction/reconciliation into authoritative cell
```

Recovery tooling must preserve tenant-safe relationships and not overwrite unrelated tenants.

## Recovery point/time objectives

Numeric RPO/RTO values remain OPEN until commercial/SLO work. Targets are defined separately for Control Plane, cell transactional data, telemetry and artifacts because their business criticality differs.

## Retention policy

Retention is driven by data class, tenant plan/policy, security/compliance/legal requirement and storage tier.

Canonical lifecycle:

```text
hot/current -> warm/rolled-up -> archive -> governed deletion
```

Not every data class uses every stage.

## Deletion/anonymization

Data-rights workflows distinguish physical deletion, anonymization, pseudonymization and legal retention. Auditability does not justify retaining unnecessary personal data forever.

## Object/artifact storage

Large generated/exported binary content lives outside transactional PostgreSQL. Metadata includes:

```text
artifact_id
tenant_id
artifact_type
storage_reference
content_type
size
checksum
created_at
expires_at/retention policy
classification
status
```

Object namespaces use immutable tenant identity, not mutable slug. Access is mediated by application authorization or short-lived scoped download capability; storage paths are not authorization.

## Artifact authorization

For delayed exports/reports, authorization is checked when requested and, where policy requires, again before artifact release/download. Revoked users do not retain indefinite access through stale permanent links.

## Restore rehearsal

Scheduled recovery tests prove:

- backup readability;
- key/secret availability required for decryption;
- restore procedure correctness;
- RLS/tenant isolation after restore;
- application/schema compatibility;
- measured recovery duration and data-loss window.

Results are operational evidence used to set/revise RPO/RTO.
