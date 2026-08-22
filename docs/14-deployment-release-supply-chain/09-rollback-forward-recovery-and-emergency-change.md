# Phase 14 — Rollback, Forward Recovery and Emergency Change

**Status:** proposed baseline

## Core rule

Rollback changes software/configuration state. It does not erase history or move an independently owned authority backwards.

A rollback SHALL NOT make external effects disappear, resurrect revoked authority, undo audit evidence, reverse erasure/legal-hold decisions, reopen consumed capabilities, forget replay/idempotency outcomes, restore retired release approvals/policies/verifier trust, regress authoritative cell compatibility state, erase a possibly completed release effect or treat restored/missing state as proof of absence.

## Change outcome classes

Each release change declares one of:

```text
rollback_eligible
forward_recovery_required
reconciliation_required
irreversible_without_governed_migration
```

The class may be target/state dependent; it is not inferred from deployment tool capability.

## Rollback eligible

Rollback is eligible only when the older runtime/config remains semantically compatible with current authoritative state and does not require resurrection of retired security, recovery, schema, release-policy, verifier, cell-compatibility or release-target authority.

Eligibility is checked against the current mixed-version matrix, current Control Plane cell compatibility metadata, current release-policy/verifier trust, current release-target state/fence and current security/governance/reliability state immediately before rollback execution.

## Forward recovery required

Forward recovery is required when current state cannot safely be interpreted by the previous version, destructive contract has occurred, security/current-authority state would regress, release-policy/verifier trust would regress, current cell compatibility metadata rejects the older runtime/schema combination, current release-target state has advanced beyond a safely reversible point, or rolling back would invalidate required evidence.

A deployment product offering a “rollback” button is not proof of rollback eligibility.

## Reconciliation required

When an external/multi-authority effect may have occurred and durable outcome is ambiguous, deployment state remains `reconciliation_required`. Retrying, aborting or rolling back does not create new effect eligibility.

If migration/backfill state, deployment outcome, artifact identity, target release state/version or cell compatibility state is ambiguous, the release remains blocked at the owning reconciliation boundary rather than selecting the more convenient historical state.

## Release operation ambiguity

An effectful deployment/migration operation has a stable logical operation identity and target scope. Timeout, worker/process loss or transport failure after dispatch is not evidence that the target was unchanged.

Before any retry or rollback of an ambiguous operation:

- the same operation identity is observed;
- the current release-target state/version and runtime evidence are read;
- any surviving deployment-controller, migration, audit and runtime-artifact evidence is reconciled;
- stale executors are fenced;
- only the owning outcome classification may authorize further effectful work.

Creating a new deployment ID to bypass an unresolved old operation is prohibited. `RLV-047` and `RLV-048` are canonical falsification paths.

## Release-policy/verifier continuity

The release-policy profile/version and signing/provenance verifier authority used to admit a release are continuity state.

Restore/PITR/rollback of CI/CD or release-control-plane data SHALL NOT make:

- a retired production approval current;
- a broader historical CI/CD principal current;
- an obsolete trusted builder/signing issuer current;
- a retired provenance verifier current;
- a policy version that candidate source could exploit current.

Current authority is reconciled forward before privileged release actions resume. If it cannot be proven, promotion/deployment/migration remains fail-closed. `RLV-044` applies.

## Release-target continuity

Phase 14 release-target state/version is release-control authority for serialized effectful target transitions. It remains distinct from Phase 13 `runtime_generation`, `placement_version`, cell admission and business/security authority.

Restore or rollback of release-control state SHALL NOT permit a stale deployment executor to overwrite a newer target release state. If recovered release-target state may be behind surviving deployment/runtime evidence, target advancement stays reconciliation-blocked until continuity is established.

## Cell compatibility continuity

Rollback does not overwrite current Control Plane cell current/target runtime-schema compatibility metadata with an older snapshot merely to fit the desired old artifact.

The owning Control Plane/release mechanism evaluates whether the older runtime/schema combination remains admitted. A stale release snapshot, caller hint or deploy-controller state cannot override newer incompatible/deny metadata. `RLV-046` applies.

## Recovery continuity

Deployment rollback after restore/PITR respects `(R,F]`: missing restored evidence is uncertainty, not permission. Release tooling cannot clear Phase 13 quarantine on its own.

Affected release-policy/verifier, promotion/approval, deployment-operation/target-state, artifact/provenance, migration/backfill, cell compatibility and runtime-verification evidence in the recovery interval are reconciled with surviving current authorities before effectful release admission resumes.

## Emergency change

`release.emergency-change@1` is a distinct path with explicit scope, reason, current release-policy profile, principal, immutable artifact/config identity, target, expected release-target state, compatibility state, evidence, expiry/cleanup and post-change review.

Emergency governance may compress timing/approval workflow only where accepted policy permits. It cannot waive:

- accepted-source trust and bounded evaluator semantics;
- immutable artifact identity/integrity/provenance;
- stable operation identity and release-target fencing;
- ambiguity/reconciliation before retry;
- actual running-artifact verification;
- current tenant/security/recovery/release-policy/verifier authority;
- current cell runtime/schema compatibility where applicable;
- secret handling;
- audit/accountability;
- migration safety;
- external-effect ambiguity handling;
- exact target scoping.

## Hotfix artifact

A hotfix is still built/provenanced as a new immutable artifact from an accepted exact source state. Editing production files or mutating an existing artifact in place is prohibited as the normal emergency model.

Emergency source does not skip the untrusted-candidate boundary simply because urgency is high; any accelerated source acceptance remains explicit, bounded and accountable.

## Failed emergency action

Failure/cancellation/timeout of an emergency action does not prove no effect. Result remains discoverable and reconciliation-aware under the same stable operation identity.

## Post-change

Emergency changes require later normalization into ordinary source/release history and evidence review; temporary emergency authority is retired rather than becoming a permanent bypass.

Any later normal release must still pass the ordinary source/build/artifact/promotion/deployment/runtime-verification trust chain.