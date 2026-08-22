# Phase 12 — Observability Semantic Manifest

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This manifest is the enforcement-oriented join across signal semantics, health, correlation, SLI, alerting, security/cardinality, pipeline resilience, compatibility and evidence.

An implementation mapping MAY add backend-specific fields but SHALL NOT weaken the required manifest properties.

## Manifest schema

Every stable profile records as applicable:

```text
profile_id
profile_version
capability_id
signal_family / health_profile / sli_profile / alert_profile
owner
source boundary
operation/workload class
required correlation identities
classification and tenant scope
cardinality profile
sampling eligibility
retention class
failure/degradation behavior
health binding
SLI binding
alert binding
compatibility class
validation vectors
OPEN decisions
```

## Core signal profiles

| Profile | Family | Required meaning | Cardinality/security rule |
|---|---|---|---|
| `obs.request.outcome@1` | metric/log/trace | accepted request attempt outcome by stable operation class | no raw URL/query; request ID not metric label |
| `obs.operation.state@1` | event/metric/log | durable long-running operation progress/terminal/reconciliation state | operation ID diagnostic only; bounded indexing |
| `obs.async.progress@1` | metric/event | durable accepted-work age/lag, completion, retry/quarantine/reconciliation pressure | no message payload; message ID not metric label |
| `obs.provider.operation@1` | metric/trace/log | normalized provider call outcome/latency/ambiguity | provider error text excluded from metrics; tenant/provider skew bounded |
| `obs.realtime.lifecycle@1` | metric/event/log | admission, subscription, delivery lag, resync lifecycle | connection IDs diagnostic only; no auth capability leakage |
| `obs.webhook.delivery@1` | metric/event/log | webhook obligation/attempt outcome when Product enables it | delivery identity separate from destination generation; no secret/signature leakage |
| `obs.telemetry.acceptance@1` | metric/event | customer-monitoring durable acceptance/projection lag | distinct from operational observability pipeline |
| `obs.observability.pipeline@1` | metric/health/event | exporter/collector ingest, drop, backlog, query/evaluation freshness | self-observation bounded; no recursive false-green |
| `obs.recovery.reconciliation@1` | metric/event/health | recovery/reconciliation progress, quarantine and evidence-gap state | no authority inferred from green state |
| `obs.security.authority-freshness@1` | health/event | inability to prove current authority/trust where operationally required | protected/internal; no sensitive reason disclosure publicly |

## Core health profiles

| Profile | Scope | Required dimensions |
|---|---|---|
| `health.api-bff@1` | API/BFF operation classes | liveness, workload readiness, dependency degradation, saturation, draining |
| `health.async-worker@1` | worker workload class | liveness, durable progress, backlog/lease pressure, dependency degradation, draining |
| `health.provider-adapter@1` | provider/integration class | readiness, throttling/unavailable/ambiguity/trust state, saturation |
| `health.realtime@1` | realtime admission/delivery | liveness, admission readiness, delivery degradation, resync pressure, draining |
| `health.control-plane@1` | control plane | liveness, authority/config freshness summary, degradation, saturation |
| `health.cell@1` | logical cell/workload class | readiness, placement/generation freshness summary, degradation, draining, recovery quarantine |
| `health.observability-pipeline@1` | observability evidence plane | ingest/export/query health, drop/backlog, self-observation confidence |
| `health.recovery@1` | recovery scope | quarantine, reconciliation progress, continuity blocked/eligible summary |

A single process may implement multiple profiles. One global `/health=true` does not replace them.

## Core SLI profiles

| SLI | Outcome semantics | Numeric objective |
|---|---|---|
| `sli.api.outcome@1` | eligible request success ratio by stable operation class | OPEN |
| `sli.api.latency@1` | latency distribution for eligible operation class | OPEN |
| `sli.async.progress@1` | accepted-work age/convergence and terminal outcome | OPEN |
| `sli.provider.outcome@1` | eligible provider operation normalized outcome | OPEN |
| `sli.realtime.delivery@1` | eligible admission/delivery/resync convergence | OPEN |
| `sli.webhook.convergence@1` | enabled webhook obligation terminal convergence | OPEN / Product-gated |
| `sli.customer-telemetry.acceptance@1` | durable observation acceptance/projection freshness | OPEN |
| `sli.observability.integrity@1` | required signal delivery/propagation/evidence completeness | OPEN |
| `sli.recovery.convergence@1` | recovery/reconciliation progress/evidence-gap convergence | OPEN |

Each SLI inherits missing-data=`unknown` unless its specialized profile proves another behavior.

## Core alert families

| Alert family | Required action semantics |
|---|---|
| `alert.customer-impact@1` | actionable user/capability outcome degradation |
| `alert.durable-progress@1` | backlog/lag/quarantine/reconciliation progress risk |
| `alert.capacity-saturation@1` | bounded resource pressure requiring capacity/admission action |
| `alert.security-trust@1` | trust/current-authority anomaly routed to Security ownership |
| `alert.recovery-continuity@1` | recovery quarantine/continuity block requiring recovery action |
| `alert.telemetry-integrity@1` | signal loss/broken propagation/pipeline blind spot |

Concrete thresholds/windows remain OPEN.

## Required joins

For every critical capability profile accepted in Phase 11, Phase 12 SHALL establish at minimum:

1. a health/diagnostic evidence path;
2. an SLI applicability decision;
3. an alert/actionability applicability decision;
4. security/cardinality classification;
5. pipeline failure behavior;
6. compatibility classification;
7. validation vectors.

No critical capability may be omitted merely because a vendor dashboard is not yet selected.

## Audit join

Observability profiles MAY carry safe `accountability_reference` fields that point to audit evidence. They SHALL NOT copy audit snapshots into logs/traces or treat observability retention as audit retention.

## Recovery join

Recovery-related profiles SHALL expose quarantine, progress and evidence gaps while preserving the rule:

```text
observable_eligible_state != authority_to_resume
```

The owning recovery/security/governance authority decides resumption.

## Manifest consistency blockers

Acceptance is blocked when:

- two profiles assign conflicting meanings to the same identity/version;
- an SLI references undefined/mutable signal semantics;
- an alert has no owner/action class;
- a critical Phase 11 capability has no diagnostic/health evidence path;
- a metric admits an unbounded protected dimension without evidence;
- audit or customer telemetry is silently collapsed into operational observability;
- a profile treats telemetry as authorization/retry/recovery authority.
