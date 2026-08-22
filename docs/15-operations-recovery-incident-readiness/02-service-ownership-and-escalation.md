# Phase 15 — Service Ownership and Escalation

**Status:** proposed baseline

## Purpose

Every critical capability must have an operational owner, escalation path and bounded responsibility model. Ownership is accountability for operating accepted semantics; it is not permission to redefine them.

## Ownership record

Each operationally critical capability/profile records:

```text
capability_or_profile_id
criticality_class
primary_operational_owner_profile
secondary/escalation_owner_profiles
security_owner_if_applicable
data/domain_authority_if_applicable
release/platform_owner_if_applicable
supported_operational_modes
incident_classes
mandatory_runbook_profiles
automatic_handling_boundary
manual_intervention_boundary
required_evidence
OPEN decisions
```

## Normalized catalog join

The complete logical operations record for one accepted reliability profile is the same-key join of:

```text
Phase 11 reliability manifest/profile
  + Phase 12 canonical reliability -> signal/health/SLI/alert join
  + Phase 15 operations catalog row in this document
  + applicable Phase 15 recovery-scope join in 11-operations-semantic-manifest.md
```

The join key is the exact accepted `reliability_profile_id@profile_version`. Therefore:

- `criticality_class`, automatic failure/degradation semantics and protected authority come from Phase 11;
- exact health/SLI/alert and Product-applicability bindings come from the accepted Phase 12 same-key join;
- logical operational owner, incident classes, manual runbook paths and escalation come from this Phase 15 table;
- recovery-specific owner/admission/vector bindings come from the Phase 15 manifest;
- no implementation may duplicate those upstream fields under a divergent local alias or omit them because a dashboard/service name looks equivalent.

A future serializer/catalog MAY flatten this normalized join, but it SHALL preserve every field and exact key. A Phase 11 or Phase 12 same-key change invalidates the old Phase 15 joined record until compatibility review updates it.

## Criticality classes

Phase 15 consumes the Phase 11 criticality model rather than inventing a parallel ranking. Operational ownership binds to the accepted reliability profile and its allowed degradation.

## Canonical operational owner profiles

These are logical accountability profiles, not staffing assignments and not domain authority:

```text
owner.control-plane@1
owner.data-runtime@1
owner.security-identity@1
owner.platform-runtime@1
owner.async-messaging@1
owner.integrations@1
owner.realtime@1
owner.observability@1
owner.artifact@1
owner.reporting@1
owner.privileged-operations@1
```

A concrete team/person/on-call mapping is implementation/operational state under `OPEN-OPS-002` / `OPEN-OPS-003`. Changing the physical assignee does not change these logical ownership semantics.

## Responsibility separation

Operational responsibilities are separated into logical roles:

```text
role.service-owner@1
role.incident-commander@1
role.operations-executor@1
role.recovery-authority@1
role.break-glass-approver@1
role.break-glass-executor@1
role.security-authority@1
role.domain-outcome-authority@1
role.communications-owner@1
role.evidence-reviewer@1
```

One person may hold multiple roles only where accepted policy permits and separation-of-duty requirements remain satisfied. Role names describe logical authority, not staffing counts.

## Canonical Phase 11 → Phase 15 operations catalog

This table is mandatory. Every accepted Phase 11 reliability profile has an exact Phase 15 owner/runbook/escalation binding. Prose aliases or implementation-local service names do not replace these keys.

| Phase 11 reliability profile | Primary operational owner | Mandatory incident classes | Manual runbook profiles | Mandatory escalation |
|---|---|---|---|---|
| `rel.control-plane-placement@1` | `owner.control-plane@1` | `incident.availability-degradation@1`, `incident.recovery-continuity@1`, `incident.tenant-isolation@1` | `runbook.degraded-operation@1`, `runbook.recovery@1`, `runbook.relocation@1` | `role.recovery-authority@1`; `role.security-authority@1` when placement/auth isolation is affected |
| `rel.cell-transactional-store@1` | `owner.data-runtime@1` | `incident.availability-degradation@1`, `incident.data-integrity@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | `role.recovery-authority@1`, data/domain authority for outcome/integrity decisions |
| `rel.security-session-authority@1` | `owner.security-identity@1` | `incident.security-authority@1`, `incident.tenant-isolation@1`, `incident.availability-degradation@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | `role.security-authority@1` |
| `rel.placement-reference-cache@1` | `owner.control-plane@1` | `incident.availability-degradation@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | `role.recovery-authority@1` if current placement cannot be proven |
| `rel.performance-cache@1` | `owner.platform-runtime@1` | `incident.availability-degradation@1` | `runbook.degraded-operation@1` | capability service owner when accepted degradation envelope is exceeded |
| `rel.replay-consume-state@1` | `owner.async-messaging@1` | `incident.recovery-continuity@1`, `incident.data-integrity@1`, `incident.security-authority@1` | `runbook.redrive-replay-quarantine@1`, `runbook.recovery@1` | `role.recovery-authority@1`; `role.security-authority@1` for verifier/trust defects |
| `rel.secret-key-authority@1` | `owner.security-identity@1` | `incident.crypto-authority@1`, `incident.security-authority@1`, `incident.recovery-continuity@1` | `runbook.crypto-secret-recovery@1`, `runbook.recovery@1` | `role.security-authority@1`, `role.recovery-authority@1` |
| `rel.configuration-authority@1` | `owner.control-plane@1` | `incident.security-authority@1`, `incident.release-runtime@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.recovery@1`, `runbook.release-forward-recovery@1` | `role.security-authority@1` for trust/secret scope; release/platform owner for release-bound config |
| `rel.outbox-publication@1` | `owner.async-messaging@1` | `incident.availability-degradation@1`, `incident.external-effect-ambiguity@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.redrive-replay-quarantine@1`, `runbook.recovery@1` | domain outcome authority for ambiguous business publication/effect |
| `rel.broker-job-transport@1` | `owner.async-messaging@1` | `incident.availability-degradation@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.redrive-replay-quarantine@1` | service owner when backlog/capacity exceeds accepted bounds |
| `rel.consumer-inbox-effect@1` | `owner.async-messaging@1` | `incident.data-integrity@1`, `incident.external-effect-ambiguity@1`, `incident.recovery-continuity@1` | `runbook.redrive-replay-quarantine@1`, `runbook.recovery@1` | domain outcome authority for effect ambiguity; Security for comparison-trust defects |
| `rel.external-provider@1` | `owner.integrations@1` | `incident.availability-degradation@1`, `incident.external-effect-ambiguity@1`, `incident.security-authority@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | domain outcome authority for ambiguous provider effects; Security for trust/auth defects |
| `rel.realtime-fanout@1` | `owner.realtime@1` | `incident.availability-degradation@1`, `incident.security-authority@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | Security/current-placement authority when admission/resync authority is uncertain |
| `rel.webhook-delivery@1` | `owner.integrations@1` | `incident.availability-degradation@1`, `incident.external-effect-ambiguity@1`, `incident.security-authority@1` | `runbook.degraded-operation@1`, `runbook.redrive-replay-quarantine@1`, `runbook.recovery@1` | domain/integration outcome authority for ambiguous delivery; Security for destination trust |
| `rel.telemetry-plane@1` | `owner.observability@1` | `incident.observability-blindness@1`, `incident.availability-degradation@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | service owner when blindness affects protected admission/evidence |
| `rel.customer-telemetry-acceptance@1` | `owner.observability@1` | `incident.data-integrity@1`, `incident.recovery-continuity@1`, `incident.availability-degradation@1` | `runbook.degraded-operation@1`, `runbook.recovery@1`, `runbook.redrive-replay-quarantine@1` | `role.recovery-authority@1`; domain/data authority for customer-observation continuity decisions |
| `rel.mandatory-audit-plane@1` | `owner.security-identity@1` | `incident.security-authority@1`, `incident.data-integrity@1`, `incident.recovery-continuity@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | `role.security-authority@1`; governance/audit authority as applicable |
| `rel.artifact-storage@1` | `owner.artifact@1` | `incident.availability-degradation@1`, `incident.security-authority@1`, `incident.recovery-continuity@1` | `runbook.recovery@1`, `runbook.release-forward-recovery@1` | Security/governance for disclosure/erasure; release owner for promotion/deployment eligibility |
| `rel.reporting-derived@1` | `owner.reporting@1` | `incident.availability-degradation@1`, `incident.data-integrity@1` | `runbook.degraded-operation@1`, `runbook.recovery@1` | domain/data owner if derived state could be mistaken for authoritative business truth |
| `rel.privileged-operations@1` | `owner.privileged-operations@1` | `incident.security-authority@1`, `incident.recovery-continuity@1`, `incident.external-effect-ambiguity@1` | `runbook.break-glass@1`, `runbook.recovery@1`, `runbook.release-forward-recovery@1` | `role.security-authority@1`, `role.recovery-authority@1`, owning domain/process for effect outcome |

## Product applicability preservation

A catalog row means **prepared operational accountability**, not Product enablement.

For any Phase 12 same-key join with an accepted Product selector, operational behavior consumes that selector unchanged. In particular:

```text
rel.webhook-delivery@1
  -> webhook_product_state

rel.artifact-storage@1 Product-facing delivery branch
  -> artifact_delivery_product_state
```

Rules:

- `product_state_unproven` remains the exact upstream OPEN state; it is neither enabled nor `NO_APPLICABLE_CASE`;
- `product_not_enabled` / `product_not_exposed_delivery` do not erase underlying diagnostic, security, recovery or governance ownership where the prepared reliability profile still applies;
- an owner/runbook/catalog entry cannot create a Product-facing SLO/alert/communication/release commitment;
- operational tooling cannot infer Product applicability from deployment, configuration, feature flags, traffic, catalog presence or team ownership;
- if upstream Product/Phase 12 applicability changes, the same-key operations record undergoes compatibility review before Product-facing operational commitments change.

`OPRV-058` falsifies Product-applicability laundering through the operations catalog.

### Catalog completeness rule

The exact accepted Phase 11 reliability profile set is the source set. A future Phase 11 profile addition/change is a Phase 15 compatibility input: Phase 15 conformance fails until an explicit operations catalog row exists or an accepted successor mapping is provided.

The accepted Phase 12 same-key observability join is also mandatory input. If its health/SLI/alert/Product-applicability mapping changes for a reliability key, the Phase 15 normalized record is stale until compatibility review confirms the operational owner/runbook/incident mapping remains correct or updates it.

The table selects operational accountability and mandatory manual paths. It does not replace Phase 11 automatic failure behavior: automatic handling remains the accepted reliability profile itself until the profile enters a state requiring human escalation.

## Escalation

Escalation is required when:

- the active failure/degradation mode has no accepted automatic handling path;
- current authority or recovery continuity cannot be proven;
- a break-glass profile may be required;
- tenant isolation, data integrity, confidentiality, revocation, erasure, legal hold or cryptographic authority may be affected;
- ambiguous external effects remain unresolved;
- a recovery scope cannot establish `R` or `F`;
- an accepted release/runtime rollback or admission gate is blocked;
- capacity/saturation threatens bounded operation;
- incident communication obligations exceed the current owner scope.

Escalation does not itself broaden privilege.

## Automatic vs manual handling

Every accepted Phase 11 failure/degradation class maps to either:

1. the accepted automatic handling selected by the exact Phase 11 reliability profile; or
2. an operational response owner and one of the mandatory runbook profiles above when manual intervention is required.

Automatic handling cannot silently cross into incident closure, break-glass admission, domain outcome, Product applicability, redrive/replay eligibility or recovery completion authority.

## Ownership currentness

Ownership, on-call/availability routing and delegation are current operational state. Stale ownership metadata may delay response but cannot grant privileged authority to a retired principal.

Delegation records scope, issuer, grantee, validity/currentness, revocation and audit evidence according to the owning authority.

## Tenant and cross-tenant operations

Operational tooling and procedures remain tenant-scoped where tenant data or effectful actions are involved. A global operator view does not create cross-tenant mutation authority.

Bulk/cross-tenant actions require an explicitly accepted operation class with bounded scope, security review, audit and capacity controls; convenience selection in a dashboard is insufficient authority.

## Service catalog minimum joins

The catalog above covers the accepted Phase 11 reliability profile set and consumes the corresponding exact Phase 12 health/SLI/alert/Product-applicability semantics through the normalized same-key join. Phase 13 runtime/cell/control-plane and Phase 14 release/recovery surfaces are joined through the applicable rows and the Phase 15 recovery manifest.

Unknown ownership for a critical capability is a Phase 15 blocker, not an implementation TODO.

## Evidence

Permanent evidence records exact reliability profile, exact accepted Phase 12 observability/applicability profile set, logical owner profile, physical delegation/currentness, escalation transitions, privileged decisions, handoffs and unresolved ownership gaps without exposing unnecessary personal data or secrets.