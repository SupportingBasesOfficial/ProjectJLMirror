# Phase 15 — Operations Semantic Manifest

**Status:** proposed baseline

## Purpose

This manifest is the machine-oriented join for Phase 15 operational conformance. Narrative resemblance is not a valid join.

## Capability operations record

Each critical capability/profile materializes:

```text
capability_profile_id
accepted_reliability_profile_id@version
accepted_health_profile_ids
accepted_SLI_profile_ids
accepted_alert_profile_ids
operational_owner
escalation_owner
incident_class_set
automatic_handling_profile_or_NO_APPLICABLE_CASE
mandatory_runbook_profiles
allowed_break_glass_profile_or_NO_APPLICABLE_CASE
recovery_scope_profiles
capacity/admission profile
permanent evidence profile
required_OPRV_vectors
OPEN decisions
```

Omission is not `NO_APPLICABLE_CASE`. A conditional `NO_APPLICABLE_CASE` requires the condition, accepted authority and reviewable evidence.

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
recovery_subscope_profile_or_NO_APPLICABLE_CASE
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
required_OPRV_vectors
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

`recovery.telemetry@1` additionally selects exactly one or both canonical subprofiles as applicable:

```text
telemetry.operational-observability@1
telemetry.customer-monitoring@1
```

These are semantic subprofiles inside the mandatory telemetry recovery scope, not new top-level recovery scopes.

Each recovery profile requires owner + quarantine + R + F + continuity inventory + reconciliation + admission proof. `F_or_unproven` is an explicit blocked state, not an absent F requirement.

## Canonical recovery-scope joins

| Recovery profile | Accepted upstream joins | Mandatory admission emphasis | Runbook profile | Required Phase 15 vectors |
|---|---|---|---|---|
| `recovery.control-plane@1` | `rel.control-plane-placement@1`, `health.control-plane@1`, Phase 13 placement/cell lifecycle, Phase 14 release-target/current-policy state | current placement/config/cell/release/security authority; stale writer/executor fencing; `(R,F]` | `runbook.recovery@1` | `OPRV-009..015`, `OPRV-019`, `OPRV-022`, `OPRV-035`, `OPRV-051`, `OPRV-052` |
| `recovery.cell@1` | `rel.cell-transactional-store@1`, `health.cell@1`, Phase 13 runtime/config/network/workload generations, Phase 14 artifact/config verification | current cell lifecycle/runtime/config/placement/release state; durable work continuity; stale worker/writer fencing | `runbook.recovery@1` | `OPRV-009..015`, `OPRV-020`, `OPRV-022`, `OPRV-024`, `OPRV-036..038`, `OPRV-052` |
| `recovery.tenant@1` | `rel.control-plane-placement@1`, `rel.security-session-authority@1`, relevant cell/data reliability profiles, current tenant placement/auth/governance | canonical tenant identity, current placement/auth/governance, tenant-scoped durable/effect continuity | `runbook.recovery@1`, `runbook.relocation@1` where relocation applies | `OPRV-011..014`, `OPRV-019`, `OPRV-021`, `OPRV-023`, `OPRV-042`, `OPRV-052` |
| `recovery.telemetry@1` | `health.observability-pipeline@1`, `health.customer-telemetry@1`, `sli.observability.integrity@1`, `sli.customer-telemetry.acceptance@1`, `obs.recovery.reconciliation@1` | operational-observability blindness separated from durably accepted customer-observation continuity; no false healthy silence/projection regression | `runbook.recovery@1` | `OPRV-009..014`, `OPRV-034`, `OPRV-048`, `OPRV-052`, `OPRV-053` |
| `recovery.artifact@1` | `health.artifact@1`, `obs.artifact.lifecycle@1`, Phase 09 artifact authority, Phase 14 artifact/release lifecycle | immutable integrity plus current lifecycle/delivery/disclosure/release authority; retired/consumed generations stay retired | `runbook.recovery@1`, `runbook.release-forward-recovery@1` as applicable | `OPRV-009..015`, `OPRV-032`, `OPRV-036..038`, `OPRV-052`, `OPRV-054` |
| `recovery.crypto-authority@1` | `rel.secret-key-authority@1`, `health.security-authority@1`, `health.message-equivalence@1` where historical proof applies, Phase 14 release verifier continuity | current key/verifier/secret authority plus narrow historical-proof usability; revocation/erasure/currentness cannot regress | `runbook.crypto-secret-recovery@1` | `OPRV-012..018`, `OPRV-045`, `OPRV-051`, `OPRV-052` |

A future implementation SHALL use exact accepted profile IDs where a normalized upstream catalog provides them. Tool/vendor object names are not valid substitutes.

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
| telemetry recovery | exact telemetry subscope + Phase 12 continuity semantics | restored logs/metrics or projection reachability as customer-observation truth |
| artifact recovery | immutable integrity + current lifecycle/delivery/disclosure/release authority | restored bytes/tag/access object as authority |
| redrive/replay | current contract authority + dedup/effect/equivalence + generation + capacity | DLQ button/age |
| relocation | current Control Plane placement authority + source/target fences | manual routing/pointer edit |
| release recovery | Phase 14 current operation/target/config/runtime evidence | vendor rollback button |
| incident closure | accepted closure criteria + residual ownership/evidence | symptom disappearance/tool green |

## Cross-cutting validation

`OPRV-001..054` are canonical Phase 15 adversarial vectors. Implementations map every applicable vector to owner, expected result and evidence or an evidence-backed `NO_APPLICABLE_CASE` for a genuinely conditional subcase.

## OPEN discipline

Concrete products, topology and numerics resolve only through `OPEN-OPS-*` closure evidence. Tool defaults never become manifest authority silently.