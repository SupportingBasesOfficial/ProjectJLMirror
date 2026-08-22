# Phase 14 — Security, Privacy and Supply-Chain Threat-Model Delta

**Status:** proposed baseline

## Trust boundaries

Phase 14 adds/refines:

- contributor/source -> reviewed source;
- source/dependency/toolchain -> build executor;
- build executor -> artifact registry;
- artifact -> provenance/attestation authority;
- release authority -> promotion record;
- deployment principal -> target environment/cell;
- release system -> secret/config authority;
- deployment -> migration/admin runtime;
- desired release state -> observed runtime/drift evidence;
- emergency principal -> production target.

## Threats

### RLS-TM-001 — Source-to-build substitution
Build uses source/dependency state different from reviewed input. Controls: exact source/input binding, provenance. Vectors: `RLV-003..005`.

### RLS-TM-002 — Artifact substitution
Mutable tag/registry path changes bytes after approval. Controls: immutable content identity, deployment-time verification. Vectors: `RLV-002`, `RLV-007`.

### RLS-TM-003 — Provenance/attestation forgery
Controls: trusted/current issuer authority, verifier lifecycle, immutable binding. `RLV-006`.

### RLS-TM-004 — CI privilege concentration
One pipeline principal edits source, forges evidence and deploys production. Controls: logical principal separation, least privilege, audit. `RLV-009..011`.

### RLS-TM-005 — Secret exfiltration through build/release evidence
Controls: secret references, redaction/classification, scoped ephemeral credentials. `RLV-012`, `RLV-037`.

### RLS-TM-006 — Environment authority laundering
Deployment location/label grants production authority. Controls: Phase 13 environment semantics, explicit promotion/deployment authority. `RLV-014`, `RLV-015`.

### RLS-TM-007 — Stale approval replay
Old queued job executes after revocation/supersession. Controls: currentness revalidation on resume. `RLV-013`.

### RLS-TM-008 — Health authority laundering
Vendor green bypasses recovery/security quarantine. Controls: Phase 12/13 semantic admission. `RLV-016`.

### RLS-TM-009 — Rollout blast-radius amplification
Bad release changes all cells simultaneously. Controls: canary/bounded waves/pause/abort and capacity gates. `RLV-017..019`, `RLV-027`.

### RLS-TM-010 — Mixed-version semantic split
Old/new runtime/schema/API/event disagree on authority/effect meaning. Controls: explicit compatibility matrix. `RLV-021..024`.

### RLS-TM-011 — Migration race / destructive contract
Controls: dedicated migration principal, lock/fence, expand/migrate/contract. `RLV-024..026`.

### RLS-TM-012 — Rollback authority resurrection
Controls: change outcome classes, current authority/recovery continuity. `RLV-028..030`.

### RLS-TM-013 — Emergency bypass persistence
Controls: new immutable hotfix artifact, bounded emergency principal, audit/expiry/post-review. `RLV-031`, `RLV-032`.

### RLS-TM-014 — Drift remediation as autonomous mutation
Controls: observer-only detection by default, deliberate correction. `RLV-033`.

### RLS-TM-015 — Evidence destruction during retirement
Controls: retention/verification continuity. `RLV-034`.

### RLS-TM-016 — Decommission stale authority
Controls: placement/credential/network/data/recovery fencing. `RLV-035`, `RLV-036`.

### RLS-TM-017 — Tool default becomes authority
Controls: manifest completeness, explicit OPEN ownership. `RLV-038`, `RLV-039`.

### RLS-TM-018 — Evidence reuse across changed state
Controls: exact artifact/config/target identity and revalidation. `RLV-040`.

## Privacy

Release evidence minimizes tenant identifiers, physical topology, secret references and production data. Build/test evidence may use synthetic/minimized data; production-derived validation data follows Security governance.

## Recovery/security continuity

Rollback, restore, redeploy or registry recovery cannot move authorization, revocation, erasure, legal-hold, reliability or verifier authority backwards. When continuity cannot be proven, deployment admission remains blocked/quarantined.

## Supply-chain portability

Replacing build/registry/CI/signing/orchestrator product must preserve trust/evidence semantics. A vendor-specific verification badge is not a canonical security authority.