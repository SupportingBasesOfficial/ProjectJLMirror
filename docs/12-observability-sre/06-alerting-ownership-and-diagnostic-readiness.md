# Phase 12 — Alerting, Ownership and Diagnostic Readiness

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This document defines what makes an alert actionable and how diagnostic evidence is linked to logical ownership without selecting a paging/incident product or staffing model.

## Alert contract

Every alert profile SHALL declare:

```text
alert_id
capability_id
condition / signal profile
impact class
scope
owner
urgency class
action class
diagnostic entry points
correlation requirements
suppression/dedup policy
recovery/clear semantics
known false-positive/false-negative risks
security/privacy classification
runbook requirement or Phase-15 handoff
numeric threshold/window OPEN item where applicable
```

An alert with no owner/action class is not acceptance-ready.

## Alert classes

Phase 12 distinguishes at least:

- **customer-impact symptom** — accepted operation/outcome is failing/degraded;
- **durable-progress risk** — backlog/lag/reconciliation/quarantine is threatening progress;
- **capacity/saturation risk** — bounded resource envelope is under pressure;
- **security/trust signal** — compromise, authority-freshness or suspicious access evidence requiring Security ownership;
- **recovery-continuity signal** — recovery quarantine, missing `(R,F]` evidence, stale generation/fence or reconciliation block;
- **telemetry-integrity signal** — signal loss, broken propagation, pipeline drop or semantic/config drift that weakens observability evidence;
- **governance/release evidence signal** — missing/incompatible required evidence consumed by later release gates.

Exact urgency/paging mapping belongs to Phase 15 and Product/SRE evidence.

## Symptom before cause, cause without noise

Where possible, user-impact alerts SHOULD originate from user/capability outcomes rather than every low-level dependency symptom. Dependency/cause signals remain available for diagnosis and may have separate alerts when early action is necessary.

One shared dependency incident SHALL NOT produce unbounded duplicate paging across every dependent component. Dedup/grouping may reduce notification noise but SHALL NOT erase the underlying evidence or hide distinct tenant/security/recovery scopes.

## Suppression and maintenance

Suppression is a governed notification behavior, not deletion of evidence.

A suppression/maintenance profile SHALL:

- identify scope and expiry;
- preserve underlying signal/SLI accounting unless an accepted SLO exclusion says otherwise;
- not suppress mandatory security/recovery evidence globally through a generic maintenance switch;
- remain auditable when it changes operational notification behavior;
- avoid permanent silent disablement.

## Clear/recovery semantics

An alert SHALL clear only when its condition's accepted recovery predicate is met. Ordinary reachability SHALL NOT clear:

- compromised/untrusted dependency alerts;
- recovery-quarantine alerts requiring reconciliation;
- ambiguous external-effect alerts requiring terminal reconciliation;
- telemetry-integrity alerts when the evidence gap remains unknown.

Flapping control may delay notification transitions under bounded policy but cannot rewrite the underlying health/SLI state.

## Diagnostic readiness

For each critical flow, operators SHALL be able to reach bounded evidence for:

- current capability health/degradation state;
- relevant request/operation/message/delivery/replay/recovery identities;
- normalized failure class;
- dependency state;
- retry/quarantine/reconciliation state;
- generation/fence/config references where material;
- saturation/backlog dimensions;
- safe recent diagnostic logs/traces/events;
- applicable audit reference without exposing audit-protected content improperly.

Diagnostic tooling SHALL NOT require raw production secrets or unrestricted database access as the normal path.

## Runbook linkage

Phase 12 defines that action classes require a runbook/diagnostic procedure before production where appropriate. Phase 15 owns the concrete incident-command, operator privilege, break-glass and rehearsal process.

An alert may therefore be semantically accepted in Phase 12 with a Phase-15 runbook implementation obligation, provided the required inputs/action class are explicit.

## Tenant-aware alerting

Tenant-specific degradation MAY produce tenant-scoped alerts when operationally useful, but tenant identity/classification and alert fanout must be bounded. One noisy tenant/provider/destination SHALL NOT generate unbounded global notification amplification.

Cross-tenant aggregate alerts SHALL not expose tenant identity to unauthorized operators/sinks.

## Alert quality evidence

Before production, alert profiles require evidence appropriate to risk, including:

- injected failure triggers the intended alert;
- healthy/no-applicable-case does not trigger it;
- clear semantics work after real recovery predicate;
- suppression expires and preserves underlying evidence;
- dedup does not collapse distinct security/recovery incidents incorrectly;
- telemetry loss cannot silently prevent every alert without a telemetry-integrity signal;
- cardinality/fanout remains bounded under tenant/provider/destination skew.

## Numeric policy

Thresholds, burn windows, debounce durations and paging urgency numerics remain OPEN until baseline/load/incident evidence supports them. Semantic alert contracts are not OPEN.
