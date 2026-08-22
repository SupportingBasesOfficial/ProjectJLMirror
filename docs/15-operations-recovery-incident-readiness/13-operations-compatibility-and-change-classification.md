# Phase 15 — Operations Compatibility and Change Classification

**Status:** proposed baseline

## Principle

Operational compatibility is semantic. A runbook/tool change can be security/correctness breaking without changing application schemas.

## Classes

### OPS-COMP-A — non-semantic operational
Formatting, contact presentation or evidence-view changes that preserve authority/state semantics.

### OPS-COMP-B — implementation substitution
Incident, paging, backup, DR, KMS, runbook or automation product replacement preserving exact logical profiles, authority, evidence and failure semantics.

### OPS-COMP-C — semantic breaking
Changes to incident lifecycle/closure, recovery state/R/F meaning, runbook authority, redrive/replay eligibility, relocation/decommission semantics, evidence disposition or ownership boundaries.

### OPS-COMP-D — security/recovery sensitive
Changes that broaden break-glass, weaken separation/dual control, make stale authority current, weaken tenant isolation, expose secrets/data, allow missing restored state as permission, regress revocation/erasure/legal hold/audit/crypto decisions, bypass ambiguity reconciliation or allow AI/tool output into protected authority decisions.

## Ownership compatibility

Changing an owner/rotation mechanism is compatible only if current delegation/revocation and escalation remain unambiguous. Removing an owner for a critical capability is breaking.

## Incident compatibility

Changing classification may be breaking when it alters mandatory authority, communication, recovery or evidence paths. Renaming a severity label is not automatically semantic, but mapping a security/recovery incident to a weaker response is.

## Runbook compatibility

A runbook version is semantic when steps/preconditions/authority/effect identity/abort/recovery behavior changes. Old paused executions cannot silently resume under a materially different runbook without revalidation/migration of execution state.

## Break-glass compatibility

Broadening actions, duration, target scope, credential authority, approval/dual-control rules or post-use review is security-sensitive.

## Recovery compatibility

Changing recovery profile owner, R/F interpretation, continuity inventory, admission criteria, partial-resumption meaning or failover writer fencing is breaking unless an accepted migration proves equivalent safety.

## Crypto recovery compatibility

Verifier/key lifecycle changes must preserve historical evidence interpretability without reviving retired current authority. Vendor migration is compatible only with that property.

## Async/replay compatibility

Changing dedup/equivalence/redrive/replay/generation semantics remains owned by prior contracts. Operational tooling may change only while preserving them.

## Release recovery compatibility

Phase 14 operation identity, target-state fencing, config evidence and rollback/forward-recovery classes cannot be weakened by incident tooling.

## Evidence compatibility

Changing evidence identity, retention, auditability or correlation can be security/recovery breaking even if procedure steps are unchanged.

## OPEN transitions

Closing an `OPEN-OPS-*` decision is a compatibility-relevant change when it selects a product/mechanism/numeric that affects authority/failure/evidence semantics. Closure cannot silently redefine a fixed property.