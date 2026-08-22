# Phase 15 — Incident Classification, Command and Communications

**Status:** proposed baseline

## Purpose

Define incident command as a coordination authority over accepted operational procedures, not as Product, Security, tenant, domain, release or recovery authority.

## Incident record

Every incident materializes:

```text
incident_id
classification_set
affected_capability_profile_ids
affected_tenant/cell/environment_scope_or_minimized_equivalent
declared_at
incident_commander
operations/recovery/security/domain owners
current lifecycle state
current containment/degradation profile
active recovery/release/relocation operation IDs
break-glass session IDs if any
communication responsibility/status
known ambiguity/recovery blockers
required evidence
closure criteria
post-incident review state
```

## Classification dimensions

Classification is multi-dimensional rather than one scalar severity alone. At minimum distinguish:

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

Numeric/severity labels, paging thresholds and business impact numerics remain OPEN. The dimensions above determine mandatory authority/evidence paths.

## Command lifecycle

```text
detected -> declared -> triaged -> contained_or_stabilizing
 -> recovery_in_progress -> verification -> resolved
 -> post_incident_review_required -> closed
```

State transitions require attributable evidence. Symptom disappearance, a green dashboard, vendor status or AI recommendation cannot close an incident.

## Command authority

The incident commander may coordinate owners, freeze risky changes, request accepted break-glass admission, choose among already-accepted operational procedures, establish communication cadence and require evidence review.

The incident commander SHALL NOT:

- invent retry/redrive/replay eligibility;
- override tenant placement or current authorization;
- declare ambiguous external effects absent;
- waive erasure/legal hold/audit/crypto continuity;
- convert forward-recovery-required into rollback-eligible;
- bypass release artifact/config verification or target fencing;
- self-admit break-glass where separation/dual control applies;
- redefine Product or architecture.

## Handoff

Command handoff records previous/new commander, time/order, active blockers, active operation identities, authority state and acknowledged evidence set. A handoff never resets incident/recovery state.

## Communication responsibility

Communications have explicit owner and audience class. Communications are fact/evidence bounded and do not expose tenant data, physical topology, security-sensitive details or secret references unnecessarily.

Public/customer/internal/regulatory communication mechanisms and numeric cadences remain OPEN; responsibility, reviewability and classification are fixed.

## Incident closure

Closure requires:

- affected capability has an accepted restored or safe-degraded state;
- recovery/admission blockers are dispositioned;
- unresolved ambiguous effects remain explicitly tracked rather than hidden by closure;
- break-glass sessions are revoked/expired and post-use review is queued/completed as required;
- required evidence is retained;
- follow-up owners exist for residual risk/actions;
- communication obligations are dispositioned;
- post-incident review requirement is recorded.

Incident closure is an operational governance decision; AI/tool output is never direct, indirect or joint closure authority.

## Evidence

Permanent evidence preserves command transitions, decisions, consulted authorities, affected operation IDs, communication decisions, unresolved ambiguity and closure basis without turning chat/transcript text into authoritative system state.