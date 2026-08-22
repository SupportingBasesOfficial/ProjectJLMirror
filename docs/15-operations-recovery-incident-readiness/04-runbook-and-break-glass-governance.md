# Phase 15 — Runbook and Break-Glass Governance

**Status:** proposed baseline

## Core law

```text
RUNBOOK != AUTHORITY
BREAK-GLASS != AUTHORITY ESCAPE HATCH
UNKNOWN DUAL-CONTROL APPLICABILITY != NO_APPLICABLE_CASE
```

A runbook encodes an accepted procedure and its preconditions. It cannot create authority missing from Product, Security, domain, data, API/event, runtime or release contracts.

## Mandatory runbook classes

```text
runbook.diagnose@1
runbook.degraded-operation@1
runbook.recovery@1
runbook.crypto-secret-recovery@1
runbook.redrive-replay-quarantine@1
runbook.relocation@1
runbook.release-forward-recovery@1
runbook.break-glass@1
runbook.maintenance-decommission@1
runbook.incident-closure@1
```

Each runbook records owner, applicability, required roles, preconditions, prohibited actions, exact authoritative inputs, step classes, abort/pause/reconciliation conditions, evidence outputs, rollback/forward-recovery class and OPEN implementation choices.

## Runbook execution

`ops.runbook-execution@1` has stable execution identity. Resume after pause/restart revalidates current authority and operation state rather than assuming old eligibility.

A runbook step that performs an effectful ambiguous operation preserves the owning stable operation ID/fence. Retrying the human step does not create a new effect identity by convenience.

## Break-glass session

Canonical record:

```text
break_glass_session_id
break_glass_policy_profile_and_version
requester
approver_authority
executor_principal
reason/incident_id
exact allowed actions
resource/tenant/cell/environment scope
start/expiry
revocation/currentness
dual_control_applicability_state
dual_control_policy_evidence
dual_control_execution_profile_or_NO_APPLICABLE_CASE
credential/reference profile
audit/evidence sink
post_use_review_owner/status
```

## Dual-control applicability

The canonical selector is closed:

```text
dual_control_applicability_state:
  required_by_current_policy
  not_required_by_current_policy_with_evidence
  applicability_unproven
```

Rules:

- `required_by_current_policy` requires the accepted current Security/Risk policy evidence and the required independent approval/execution constraints before admission;
- `not_required_by_current_policy_with_evidence` may use `dual_control_execution_profile_or_NO_APPLICABLE_CASE=NO_APPLICABLE_CASE`, but only with exact accepted policy evidence proving non-applicability for the same action/scope;
- `applicability_unproven` is fail-closed for break-glass admission. It is not `NO_APPLICABLE_CASE` and cannot inherit the less restrictive branch;
- `OPEN-OPS-010` owns the concrete dual-control implementation/applicability-mapping mechanism; it does not authorize an implementation to resolve unknown policy applicability locally.

`OPRV-055` falsifies applicability laundering.

## Admission

Break-glass requires explicit current policy and incident/operational justification. Where accepted Security/risk authority requires dual control, requester/approver/executor constraints are enforced; exact staffing/count/product remains OPEN.

No emergency condition turns a denied, stale or unknown authorization/dual-control state into allowed state automatically.

## Least privilege

Break-glass authority is narrower than ordinary administrator omnipotence. It is action-scoped, resource-scoped, time-bounded/revocable and cannot silently inherit broad credentials from a workstation or dashboard session.

## Forbidden break-glass bypasses

Break-glass cannot waive:

- tenant isolation and current placement;
- immutable audit/accountability;
- erasure/legal hold/crypto-erasure intent;
- cryptographic/verifier currentness;
- `(R,F]` reconciliation;
- ambiguous external-effect reconciliation;
- idempotency/dedup/content-equivalence requirements;
- release artifact/configuration integrity and operation fencing;
- stale-writer/source/destination generation fencing;
- Product applicability/architecture authority.

## Session end

Expiry/revocation removes further eligibility but does not erase effects already performed. Ambiguous effects remain reconciliation-required. Temporary credentials/tokens are revoked/retired; ordinary authority is re-established explicitly.

## Post-use review

Every material break-glass use is attributable and reviewable. Review compares requested scope, actual effects, authority/currentness, evidence completeness, unexpected access/effects and required follow-up.

Break-glass cannot self-certify its own safe completion.

## Tool/AI boundary

Automation may prefill evidence, detect policy mismatch or recommend a runbook. AI/tool output cannot admit break-glass, select the dual-control applicability state, broaden scope, waive dual control, decide recovery eligibility or close the incident.