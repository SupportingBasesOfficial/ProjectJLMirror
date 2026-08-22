# Phase 14 — Rollback, Forward Recovery and Emergency Change

**Status:** proposed baseline

## Core rule

Rollback changes software/configuration state. It does not erase history.

A rollback SHALL NOT make external effects disappear, resurrect revoked authority, undo audit evidence, reverse erasure/legal-hold decisions, reopen consumed capabilities, forget replay/idempotency outcomes or treat restored/missing state as proof of absence.

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

Rollback is eligible only when the older runtime/config remains semantically compatible with current authoritative state and does not require resurrection of retired security/recovery/schema authority.

## Forward recovery required

Forward recovery is required when current state cannot safely be interpreted by the previous version, destructive contract has occurred, security/current-authority state would regress, or rolling back would invalidate required evidence.

## Reconciliation required

When an external/multi-authority effect may have occurred and durable outcome is ambiguous, deployment state remains reconciliation-required. Retrying or rollback does not create new effect eligibility.

## Recovery continuity

Deployment rollback after restore/PITR respects `(R,F]`: missing restored evidence is uncertainty, not permission. Release tooling cannot clear Phase 13 quarantine on its own.

## Emergency change

`release.emergency-change@1` is a distinct path with explicit scope, reason, principal, artifact/config identity, target, evidence, expiry/cleanup and post-change review.

Emergency governance may compress timing/approval workflow only where accepted policy permits. It cannot waive:

- immutable artifact identity/integrity;
- current tenant/security/recovery authority;
- secret handling;
- audit/accountability;
- migration safety;
- external-effect ambiguity handling;
- exact target scoping.

## Hotfix artifact

A hotfix is still built/provenanced as a new immutable artifact. Editing production files or mutating an existing artifact in place is prohibited as the normal emergency model.

## Failed emergency action

Failure/cancellation/timeout of an emergency action does not prove no effect. Result remains discoverable and reconciliation-aware.

## Post-change

Emergency changes require later normalization into ordinary source/release history and evidence review; temporary emergency authority is retired rather than becoming a permanent bypass.