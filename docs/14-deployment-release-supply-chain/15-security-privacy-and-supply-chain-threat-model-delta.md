# Phase 14 — Security, Privacy and Supply-Chain Threat-Model Delta

**Status:** proposed baseline

## Trust boundaries

Phase 14 adds/refines:

- untrusted source/candidate workflow -> bounded validation principal;
- accepted source trust policy -> trusted build principal;
- contributor/source -> reviewed source;
- source/dependency/toolchain -> build executor;
- build executor -> artifact registry;
- artifact -> provenance/attestation authority;
- release authority -> promotion record;
- release deployment operation -> release target state/fence;
- validation.general -> validation.reference-cell for applicable cell releases;
- validation configuration evidence -> target environment configuration identity/profile;
- release system -> Control Plane cell compatibility metadata;
- deployment principal -> target environment/cell;
- release system -> secret/config authority;
- deployment -> migration/admin runtime;
- deployment controller desired state -> observed running artifact identity;
- trusted release-policy/verifier authority -> pipeline admission after restart/restore;
- desired release state -> observed runtime/drift evidence;
- emergency principal -> production target.

## Threats

### RLS-TM-001 — Source-to-build substitution
Build uses source/dependency state different from reviewed input. Controls: exact source/input binding, provenance. Vectors: `RLV-003..005`.

### RLS-TM-002 — Artifact substitution
Mutable tag/registry path changes bytes after approval. Controls: immutable content identity, deployment-time verification. Vectors: `RLV-002`, `RLV-007`, `RLV-043`.

### RLS-TM-003 — Provenance/attestation forgery
Controls: trusted/current issuer authority, verifier lifecycle, immutable binding. `RLV-006`, `RLV-044`.

### RLS-TM-004 — CI privilege concentration
One pipeline principal edits source, forges evidence and deploys production. Controls: logical principal separation, least privilege, audit. `RLV-009..011`.

### RLS-TM-005 — Secret exfiltration through build/release evidence
Controls: secret references, redaction/classification, scoped ephemeral credentials. `RLV-012`, `RLV-037`.

### RLS-TM-006 — Environment authority laundering
Deployment location/label grants production authority. Controls: Phase 13 environment semantics, explicit promotion/deployment authority. `RLV-014`, `RLV-015`.

### RLS-TM-007 — Stale approval replay
Old queued job executes after revocation/supersession. Controls: currentness revalidation on resume. `RLV-013`, `RLV-044`.

### RLS-TM-008 — Health authority laundering
Vendor green bypasses recovery/security quarantine. Controls: Phase 12/13 semantic admission. `RLV-016`, `RLV-043`.

### RLS-TM-009 — Rollout blast-radius amplification
Bad release changes all cells simultaneously. Controls: reference-cell validation when applicable, canary/bounded waves/pause/abort and capacity gates. `RLV-017..019`, `RLV-027`, `RLV-045`.

### RLS-TM-010 — Mixed-version semantic split
Old/new runtime/schema/API/event disagree on authority/effect meaning. Controls: explicit compatibility matrix and current cell compatibility metadata. `RLV-021..024`, `RLV-046`.

### RLS-TM-011 — Migration race / destructive contract
Controls: dedicated migration principal, lock/fence, expand/migrate/contract and compatibility metadata proving old readers retired. `RLV-024..026`, `RLV-046`.

### RLS-TM-012 — Rollback authority resurrection
Controls: change outcome classes, current authority/recovery continuity. `RLV-028..030`, `RLV-044`.

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

### RLS-TM-019 — Untrusted source receives privileged evaluator context
Candidate source or fork obtains production/release secrets, trusted signing/provenance key authority, artifact overwrite authority, migration privilege or privileged internal network through the validation trigger. Controls: `source.untrusted-candidate@1`, `principal.release-untrusted-validation@1`, candidate-independent credential/network policy. `RLV-041`.

### RLS-TM-020 — Candidate-controlled policy self-escalation
Candidate workflow edits token permissions, secret inheritance, runner/environment selection or admission policy to evaluate itself with more authority. Controls: trusted release-policy profile/version outside candidate unilateral control and source-trust transition separated from validation. `RLV-042`.

### RLS-TM-021 — Runtime artifact identity laundering
Deployment controller desired state/tag says artifact A while running workload executes different bytes/artifact B. Controls: independent runtime-observed immutable artifact identity/equivalent bound to rollout verification. `RLV-043`.

### RLS-TM-022 — Release-policy/verifier rollback
Restore or rollback reintroduces retired approval, broader historical CI principal or obsolete provenance verifier trust. Controls: forward reconciliation of release policy/verifier authority and fail-closed privileged release admission until currentness is proven. `RLV-044`.

### RLS-TM-023 — Reference-cell stage bypass
A cell/runtime/schema-affecting release skips the accepted staging/reference-cell step because the deployment platform exposes only “test” and “production”. Controls: `validation.reference-cell@1` as a required evidence scope inside `environment.validation@1`, explicit applicability/N/A evidence and production-canary gate. `RLV-045`.

### RLS-TM-024 — Cell compatibility metadata spoof/staleness
Release or placement consumes caller-controlled/stale current-target runtime/schema compatibility metadata and admits an incompatible cell/tenant cutover. Controls: trusted Control Plane ownership/currentness, exact release/migration binding, newer deny/incompatible state precedence. `RLV-046`.

### RLS-TM-025 — Concurrent release-target split brain
Two deployment operations with incompatible artifact/config target semantics race from the same predecessor and both act as current. Controls: stable operation IDs, atomic/create-or-observe target transition, expected `release_target_state_version`, stale-executor fencing and separation from placement/runtime authority. `RLV-047`.

### RLS-TM-026 — Ambiguous deployment replay
A deployment call times out or loses its response after target mutation may have occurred, then automation creates another deployment operation and repeats the effect. Controls: same logical operation identity, durable outcome discovery, target/runtime evidence reconciliation and no retry eligibility from timeout/process death. `RLV-048`.

### RLS-TM-027 — Validation-to-production configuration evidence laundering
Artifact A is validated under configuration V, while production uses configuration P whose release-relevant trust, authorization, tenant-isolation, network/egress, failure/retry, schema/API/event, runtime-authority, Product, SLI, recovery or release-gate semantics differ materially. Automation reuses V evidence because artifact identity or config key names match, or copies production secret values into validation to manufacture superficial equality. Controls: exact target configuration identity/generation and semantic profile, explicit V->P compatibility/equivalence evidence or target-specific applicable validation, secret-reference purpose/policy comparison without secret-value copying. `RLV-049`.

## Privacy

Release evidence minimizes tenant identifiers, physical topology, secret references and production data. Build/test evidence may use synthetic/minimized data; production-derived validation data follows Security governance.

Untrusted-source validation and validation reference cells are not allowed to access production tenant data merely to improve test fidelity. Any production-derived dataset requires explicit governed export/minimization and remains non-authoritative.

Production secret values are not copied into validation to prove configuration equivalence. Configuration evidence records only the minimum identity/profile, secret-reference purpose/policy and semantic differences required to establish release safety.

Release-operation/fencing evidence exposes only the minimum target identity/state necessary for accountability and SHALL NOT become a public physical-topology or tenant-correlation oracle.

## Recovery/security continuity

Rollback, restore, redeploy, registry recovery or CI/CD control-plane recovery cannot move authorization, revocation, erasure, legal-hold, reliability, release-policy, verifier, release-target or authoritative cell compatibility state backwards. When continuity cannot be proven, deployment/promotion/placement admission remains blocked/quarantined/reconciliation-required.

A restored release-target state that may predate a surviving deployment effect cannot authorize a second effect; current target/runtime evidence must be reconciled first.

Restored configuration metadata that predates a newer production configuration generation cannot silently reuse older validation-to-target equivalence evidence. Exact current target configuration identity/profile is re-established before privileged release advancement.

## Supply-chain portability

Replacing build/registry/CI/signing/orchestrator/coordination/configuration product must preserve trust/evidence semantics, including stable operation identity, target fencing, ambiguity discovery, validation-to-target configuration evidence, reference-cell staging evidence and cell compatibility ownership/currentness. A vendor-specific verification badge or environment name is not a canonical security authority.
