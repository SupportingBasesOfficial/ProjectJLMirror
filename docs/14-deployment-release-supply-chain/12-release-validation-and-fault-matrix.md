# Phase 14 — Release Validation and Fault Matrix

**Status:** proposed baseline

## Purpose

These vectors falsify release/supply-chain semantics. A successful build/deploy is not sufficient evidence.

## Mandatory vectors

### RLV-001 — Rebuild per environment
Inject: same source is rebuilt separately for validation and production.  
Required: production promotion uses the exact validated immutable artifact identity.  
Forbidden: environment-specific rebuild under one release identity.

### RLV-002 — Mutable tag substitution
Inject: tag points to different bytes after approval.  
Required: deployment verifies immutable artifact identity and rejects substitution.

### RLV-003 — Undeclared dependency drift
Inject: mutable dependency/build input changes without source change.  
Required: provenance/input validation fails.

### RLV-004 — Build cache poisoning
Inject: cache returns bytes from undeclared input state.  
Required: integrity/provenance checks reject or rebuild safely.

### RLV-005 — Unauthorized builder
Inject: artifact produced by untrusted/stale build principal.  
Required: artifact is not promotion-eligible.

### RLV-006 — Provenance forgery / issuer retirement
Inject: syntactically valid provenance from unauthorized/retired authority.  
Required: fail closed.

### RLV-007 — Artifact tamper after publication
Inject: bytes differ from approved digest/equivalent.  
Required: deployment/promotion denied.

### RLV-008 — SBOM/dependency inventory mismatch
Inject: material component absent/inconsistent with artifact evidence.  
Required: release blocker until reconciled.

### RLV-009 — Build principal attempts production deploy
Required: denied by principal separation.

### RLV-010 — Deploy principal attempts source/provenance mutation
Required: denied.

### RLV-011 — Migration principal reused for serving runtime
Required: denied; Phase 13 privilege separation preserved.

### RLV-012 — Secret embedded in artifact/provenance/log
Required: secret leakage test fails release; references only.

### RLV-013 — Stale promotion approval resume
Inject: paused pipeline resumes after approval/principal revocation.  
Required: current authority revalidated.

### RLV-014 — Environment label as production authority
Inject: lower/recovery environment mapped to production credential/traffic by label.  
Required: denied; Phase 13 environment semantics preserved.

### RLV-015 — Production artifact present without promotion
Required: presence in registry/location cannot deploy.

### RLV-016 — Vendor green overrides quarantine
Required: Phase 12/13 recovery/security gates still block admission.

### RLV-017 — Canary selection from caller/tenant input
Required: release authority owns target scope.

### RLV-018 — Canary passes, incompatible wave generalized
Required: evidence equivalence proven or new target validation required.

### RLV-019 — Pause loses durable obligations
Required: jobs/effects/migrations remain discoverable; pause is not absence.

### RLV-020 — Abort after external effect ambiguity
Required: reconciliation_required; no blind retry/rollback.

### RLV-021 — Old runtime with incompatible schema
Required: combination never admitted.

### RLV-022 — Old consumer with incompatible event semantics
Required: mixed-version gate blocks rollout.

### RLV-023 — API parser/runtime semantic drift during rollout
Required: Phase 09 semantic compatibility preserved, not schema-only acceptance.

### RLV-024 — Contract/drop before old readers retire
Required: destructive contract blocked.

### RLV-025 — Concurrent migration executors
Required: lock/lease/fence yields one controlled migration authority.

### RLV-026 — Backfill crash/resume
Required: resume from durable progress; no global long transaction or blind duplicate effect.

### RLV-027 — Noisy backfill/starves serving traffic
Required: capacity/bulkhead gates pause/throttle rollout.

### RLV-028 — Rollback attempts to resurrect revoked credential
Required: rollback blocked/forward recovery.

### RLV-029 — Rollback attempts to erase audit/external effect
Required: historical state/effect remains authoritative.

### RLV-030 — Restore + rollback sees missing effect evidence
Required: `(R,F]` reconciliation; missing != absent.

### RLV-031 — Hotfix edits artifact in place
Required: rejected; new immutable artifact/provenance required.

### RLV-032 — Emergency principal becomes permanent bypass
Required: scoped/expiring authority and post-change normalization.

### RLV-033 — Drift detector auto-fixes canonical state silently
Required: observer-only by default; remediation is new deliberate state.

### RLV-034 — Artifact retirement loses required verification evidence
Required: retirement preserves historical evidence/verification needed by governance/incident/rollback.

### RLV-035 — Decommission while placement/workloads remain
Required: decommission blocked.

### RLV-036 — Decommission leaves live credentials/routes
Required: stale access fenced/revoked before completion.

### RLV-037 — Release evidence leaks tenant/topology/secrets
Required: classification/minimization enforced.

### RLV-038 — Tool default silently grants release authority
Required: explicit manifest/OPEN owner required.

### RLV-039 — CI success interpreted as merge/release authorization
Required: rejected by governance.

### RLV-040 — Mixed-version evidence reused after material HEAD/artifact/config change
Required: old evidence remains historical; exact new state revalidated.

## Acceptance rule

Phase 14 SHALL NOT reach `READY_FOR_MERGE` while any applicable vector lacks owner, expected result, evidence path or evidence-backed `NO_APPLICABLE_CASE`.