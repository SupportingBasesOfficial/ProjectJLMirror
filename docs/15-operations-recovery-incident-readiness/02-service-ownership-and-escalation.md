# Phase 15 — Service Ownership and Escalation

**Status:** proposed baseline

## Purpose

Every critical capability must have an operational owner, escalation path and bounded responsibility model. Ownership is accountability for operating accepted semantics; it is not permission to redefine them.

## Ownership record

Each operationally critical capability/profile records:

```text
capability_or_profile_id
criticality_class
primary_operational_owner
secondary/escalation_owner
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

## Criticality classes

Phase 15 consumes the Phase 11 criticality model rather than inventing a parallel ranking. Operational ownership binds to the accepted reliability profile and its allowed degradation.

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

1. an accepted automatic handling profile whose authority is already defined; or
2. an operational response owner and runbook class.

Automatic handling cannot silently cross into incident closure, break-glass admission, domain outcome, redrive/replay eligibility or recovery completion authority.

## Ownership currentness

Ownership, on-call/availability routing and delegation are current operational state. Stale ownership metadata may delay response but cannot grant privileged authority to a retired principal.

Delegation records scope, issuer, grantee, validity/currentness, revocation and audit evidence according to the owning authority.

## Tenant and cross-tenant operations

Operational tooling and procedures remain tenant-scoped where tenant data or effectful actions are involved. A global operator view does not create cross-tenant mutation authority.

Bulk/cross-tenant actions require an explicitly accepted operation class with bounded scope, security review, audit and capacity controls; convenience selection in a dashboard is insufficient authority.

## Service catalog minimum joins

The catalog SHALL cover at least the capabilities represented by accepted Phase 11 reliability profiles and their Phase 12 health/SLI/alert owners, plus Phase 13 runtime/cell/control-plane capabilities and Phase 14 release/recovery surfaces.

Unknown ownership for a critical capability is a Phase 15 blocker, not an implementation TODO.

## Evidence

Permanent evidence records owner/profile versions, delegation/currentness, escalation transitions, privileged decisions, handoffs and unresolved ownership gaps without exposing unnecessary personal data or secrets.