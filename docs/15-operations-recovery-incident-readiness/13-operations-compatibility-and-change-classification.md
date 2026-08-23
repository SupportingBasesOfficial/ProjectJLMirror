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
Changes to incident lifecycle/closure/residual disposition, recovery state/R/F/resumption mode, operational-owner mapping, Product-applicability binding, canonical runbook role/precondition/effect semantics, redrive/replay eligibility, relocation/decommission semantics, evidence disposition or ownership boundaries.

### OPS-COMP-D — security/recovery sensitive
Changes that broaden break-glass, weaken separation/dual control or its applicability proof, make stale authority current, weaken partial-admission independence/isolation, weaken tenant isolation, expose secrets/data, allow missing restored state as permission, regress revocation/erasure/legal hold/audit/crypto/customer-telemetry/artifact-authority decisions, bypass ambiguity reconciliation, clear a residual reconciliation block on incident closure, convert Product applicability uncertainty/disablement into operational enablement, retain a canonical runbook ID while weakening protected authority boundaries, or allow AI/tool output into protected authority decisions.

## Normalized operations catalog compatibility

The accepted Phase 11 reliability key + Phase 12 same-key observability join + Phase 15 operational owner/runbook row form one normalized operations record.

A Phase 11 profile addition/change, Phase 12 same-key health/SLI/alert/applicability change, or change in Phase 15 logical owner/incident/runbook/escalation mapping is compatibility-relevant. Removing a row or silently mapping an implementation-local alias to a different owner/path is breaking.

Changing a physical assignee/on-call rotation can remain operational state only when logical owner/current delegation/revocation/escalation semantics remain unchanged.

## Product applicability compatibility

Operational preparedness does not create Product scope.

For any Product-gated upstream branch, including `rel.webhook-delivery@1` and Product-facing artifact delivery, the exact accepted Product/Phase 12 applicability selector remains authoritative. A Phase 15 catalog row, owner, runbook, deployment, configuration, feature flag, environment, traffic observation or implementation presence cannot change:

```text
product_state_unproven -> OPEN
product_not_enabled / product_not_exposed_delivery -> not enabled/exposed
product_enabled / product_exposed_delivery -> enabled/exposed only by accepted Product authority
```

Changing `product_state_unproven` to enabled, disabled or `NO_APPLICABLE_CASE` without the owning accepted authority is semantic breaking. Treating operational ownership as Product enablement is also semantic breaking. `OPRV-058` applies.

Underlying diagnostic, security, recovery and ownership obligations may remain applicable even when a Product-facing capability is not enabled/exposed; removing those obligations merely because Product exposure is absent is likewise incompatible when upstream profiles still require them.

## Ownership compatibility

Changing an owner/rotation mechanism is compatible only if current delegation/revocation and escalation remain unambiguous. Removing an owner for a critical capability is breaking.

## Incident compatibility

Changing classification may be breaking when it alters mandatory authority, communication, recovery or evidence paths. Renaming a severity label is not automatically semantic, but mapping a security/recovery incident to a weaker response is.

`residual_obligation_disposition` semantics are compatibility-sensitive. A change that permits incident closure to mutate an underlying reconciliation-blocked operation into completed/retryable/absent state is breaking. `OPRV-057` applies.

## Runbook compatibility

The materialized canonical runbook definitions in `04-runbook-and-break-glass-governance.md` are versioned semantic contracts. The following changes are compatibility-relevant even when a tool/workflow file still carries the same profile name:

- required role or separation-of-duty binding;
- current-authority/precondition input;
- allowed procedure/effect boundary;
- prohibited substitution/fallback;
- underlying stable effect identity/fence handling;
- pause/abort/reconciliation behavior;
- evidence obligations;
- applicability/Product/recovery selector handling.

A material change SHALL use an explicitly reviewed successor/version or an accepted compatibility migration. Reusing `runbook.*@1` while weakening one of these fields is breaking. Old paused executions cannot silently resume under a materially changed definition; they revalidate/migrate against the accepted profile. `OPRV-059` applies.

Tool/vendor replacement remains OPS-COMP-B only when the exact canonical runbook semantics survive unchanged.

## Break-glass compatibility

Broadening actions, duration, target scope, credential authority, approval/dual-control rules or post-use review is security-sensitive.

The selector values `required_by_current_policy`, `not_required_by_current_policy_with_evidence` and `applicability_unproven` are semantic. Changing unknown applicability into N/A/allow, or allowing implementation defaults to select the branch, is breaking. `OPRV-055` applies.

## Recovery compatibility

Changing recovery profile/subprofile owner, R/F interpretation, continuity inventory, admission criteria, resumption-mode meaning or failover writer fencing is breaking unless an accepted migration proves equivalent safety.

For `partially_admitted`, changing the required exact operation scope, shared-authority independence evidence, isolation/fencing, prohibited operations, residual quarantine or revalidation behavior is security/recovery-sensitive. `OPRV-056` applies.

The Phase 12 operational-observability vs customer-monitoring distinction and Phase 09/14 artifact bytes vs lifecycle/disclosure/release distinction remain mandatory recovery compatibility boundaries. `OPRV-053` and `OPRV-054` apply.

## Crypto recovery compatibility

Verifier/key lifecycle changes must preserve historical evidence interpretability without reviving retired current authority. Vendor migration is compatible only with that property.

## Async/replay compatibility

Changing dedup/equivalence/redrive/replay/generation semantics remains owned by prior contracts. Operational tooling may change only while preserving them.

## Release recovery compatibility

Phase 14 operation identity, target-state fencing, config evidence and rollback/forward-recovery classes cannot be weakened by incident tooling.

## Evidence compatibility

Changing evidence identity, retention, auditability or correlation can be security/recovery breaking even if procedure steps are unchanged. Evidence changes must preserve exact recovery scope/subscope, R/F, resumption mode/partial profile, dual-control policy/applicability, Product applicability evidence where gated, exact runbook profile/version and residual operation identity where applicable.

## OPEN transitions

Closing an `OPEN-OPS-*` decision is a compatibility-relevant change when it selects a product/mechanism/numeric that affects authority/failure/evidence semantics. Closure cannot silently redefine a fixed property or resolve an unknown applicability/authority state permissively.

An operational OPEN closure also cannot close an upstream Product/Phase 12 applicability OPEN unless that upstream authority explicitly owns and accepts the change.