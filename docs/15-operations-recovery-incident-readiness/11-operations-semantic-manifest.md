# Phase 15 — Operations Semantic Manifest

**Status:** proposed baseline

## Purpose

This manifest is the machine-oriented join for Phase 15 operational conformance.

## Capability operations record

Each critical capability/profile materializes:

```text
capability_profile_id
accepted_reliability_profile
accepted_health/SLI/alert profiles
operational_owner
escalation_owner
incident_class_set
automatic_handling_profile_or_NO_APPLICABLE_CASE
mandatory_runbook_profiles
allowed_break_glass_profile_or_NO_APPLICABLE_CASE
recovery_scope_profiles
capacity/admission profile
permanent evidence profile
OPEN decisions
```

Omission is not `NO_APPLICABLE_CASE`.

## Incident record schema

```text
incident_id
classification_set
capability/scope bindings
command lifecycle state
incident commander/current delegation
operations/security/recovery/domain owner bindings
active operation IDs
break_glass_session_ids
communication owner/status
recovery/ambiguity blockers
closure evidence
post-incident review state
```

## Recovery operation schema

```text
recovery_operation_id
recovery_scope_profile
scope identity
owning authority
R
F_or_unproven
restore/backup identities
recovery target
continuity inventory profile
quarantine state
reconciliation operation IDs
current security/governance/crypto/release/runtime authority evidence
admission verification profile
partial/full resumption scope
terminal state
permanent evidence refs
```

## Mandatory recovery profiles

```text
recovery.control-plane@1
recovery.cell@1
recovery.tenant@1
recovery.telemetry@1
recovery.artifact@1
recovery.crypto-authority@1
```

Each profile requires owner + quarantine + R + F + continuity inventory + reconciliation + admission proof. `F_or_unproven` is not equivalent to an absent F requirement.

## Runbook execution schema

```text
runbook_execution_id
runbook_profile/version
incident/change/recovery relationship
executor principal
current authorization evidence
scope
stable underlying effect-operation IDs/fences
precondition evidence
step/outcome state
pause/abort/reconciliation state
permanent evidence refs
```

## Break-glass schema

```text
break_glass_session_id
requester
approver authority
executor principal
incident/reason
allowed actions
scope
time/expiry/revocation state
dual_control_profile_or_NO_APPLICABLE_CASE
credential/reference profile
audit evidence
post_use_review state
```

## Canonical incident classes

```text
incident.availability-degradation@1
incident.data-integrity@1
incident.security-authority@1
incident.tenant-isolation@1
incident.recovery-continuity@1
incident.external-effect-ambiguity@1
incident.release-runtime@1
incident.observability-blindness@1
incident.crypto-authority@1
```

## Canonical runbook profiles

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

## Operational joins

| Operation | Required upstream authority/evidence | Forbidden substitution |
|---|---|---|
| incident declaration | accepted detection/evidence + accountable operator policy | alert/AI score as autonomous incident authority |
| break-glass admission | current Security/ops policy + approver + exact scope | incident status or operator role alone |
| restore | exact recovery scope + backup/restore evidence + R | backup success as resumption authority |
| recovery admission | F + `(R,F]` reconciliation + current authorities + scope proof | service health/reachability alone |
| redrive/replay | current contract authority + dedup/effect/equivalence + generation + capacity | DLQ button/age |
| relocation | current Control Plane placement authority + source/target fences | manual routing/pointer edit |
| release recovery | Phase 14 current operation/target/config/runtime evidence | vendor rollback button |
| incident closure | accepted closure criteria + residual ownership/evidence | symptom disappearance/tool green |

## Cross-cutting validation

`OPRV-001..052` are canonical Phase 15 adversarial vectors. Implementations map every applicable vector to owner, expected result and evidence or an evidence-backed `NO_APPLICABLE_CASE` for a genuinely conditional subcase.

## OPEN discipline

Concrete products, topology and numerics resolve only through `OPEN-OPS-*` closure evidence. Tool defaults never become manifest authority silently.