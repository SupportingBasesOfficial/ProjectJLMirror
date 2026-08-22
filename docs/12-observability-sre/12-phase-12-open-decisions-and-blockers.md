# Phase 12 — OPEN Decisions and Acceptance Blockers

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This registry preserves decisions that require Product, runtime, benchmark, compliance, cost or operational evidence. `OPEN` is not permission for implementation defaults to decide architecture silently.

## Disposition vocabulary

An item may become:

```text
OPEN
SATISFIED
NO_APPLICABLE_CASE
```

`NO_APPLICABLE_CASE` requires explicit applicability condition, authority and evidence. Generic waiver/accepted-risk/tool-unavailable is not a valid blocker disposition unless a separately accepted authority defines it.

Unknown or unproven applicability is `OPEN`; it is not `NO_APPLICABLE_CASE`.

## OPEN registry

| ID | Decision | Owner | Required evidence / closure gate |
|---|---|---|---|
| OPEN-OBS-001 | observability backend/product | Phase 13/implementation | capability, security, portability, cost and failure evidence |
| OPEN-OBS-002 | collector/agent topology | Phase 13 | runtime/isolation/network/capacity model |
| OPEN-OBS-003 | trace transport/export protocol details beyond OTel-compatible semantics | Phase 13 | interoperability/security/load evidence |
| OPEN-OBS-004 | metric/log/trace storage topology | Phase 13 | retention/query/tenant/cost benchmarks |
| OPEN-OBS-005 | sampling mechanism | implementation/SRE | SLI/security/diagnostic bias + load evidence |
| OPEN-OBS-006 | sampling rates/numerics | SRE/Product | production-like volume and diagnostic-quality evidence |
| OPEN-OBS-007 | retention durations by signal class | Security/Data/SRE | compliance, incident, recovery and cost evidence |
| OPEN-OBS-008 | metric cardinality numeric budgets | SRE/Capacity | load/skew/cost benchmarks |
| OPEN-OBS-009 | per-tenant metric-dimension policy | SRE/Security | tenant-count/skew/use-case/cost evidence |
| OPEN-OBS-010 | query/index strategy for high-cardinality diagnostic IDs | Phase 13/SRE | diagnosis latency + storage/index cost evidence |
| OPEN-OBS-011 | numeric API SLOs | Product/SRE | business commitments + baseline/runtime evidence |
| OPEN-OBS-012 | numeric async progress SLOs | Product/SRE | workload/business tolerance evidence |
| OPEN-OBS-013 | numeric provider integration SLOs | Product/SRE | provider capability + customer-impact evidence |
| OPEN-OBS-014 | numeric realtime SLOs | Product/SRE | UX/runtime evidence |
| OPEN-OBS-015 | numeric customer telemetry freshness SLOs | Product/SRE | product semantics + ingest benchmarks |
| OPEN-OBS-016 | numeric recovery/reconciliation SLOs | Product/SRE/Recovery | recovery objectives and rehearsal evidence |
| OPEN-OBS-017 | SLO windows/error-budget numerics | Product/SRE | business/release/incident evidence |
| OPEN-OBS-018 | platform-level multi-tenant SLI aggregation method | Product/SRE | tenant skew and fairness evidence |
| OPEN-OBS-019 | alert thresholds/windows/debounce numerics | SRE | baseline + injected incident/false-positive evidence |
| OPEN-OBS-020 | paging/notification product | Phase 15 | operational process/integration/security/cost evidence |
| OPEN-OBS-021 | alert urgency/page mapping | Phase 15/Product | impact and operating-model evidence |
| OPEN-OBS-022 | concrete runbook system/link format | Phase 15 | incident operating model |
| OPEN-OBS-023 | observability query/admin role implementation | Phase 13/15 Security | least privilege, tenant scope and audit evidence |
| OPEN-OBS-024 | privileged cross-tenant diagnostic capability | Product/Security | explicit use case, authority, privacy and audit evidence |
| OPEN-OBS-025 | self-observation/secondary evidence mechanism for telemetry-pipeline outage | Phase 13 | failure-coupling/independence, boundedness and outage evidence |
| OPEN-OBS-026 | telemetry buffer sizes/backpressure numerics | Capacity/SRE | load/failure benchmarks |
| OPEN-OBS-027 | log/trace diagnostic payload size limits | Security/Capacity | leakage and cost evidence |
| OPEN-OBS-028 | normalized provider-error detail retention/searchability | Security/SRE | support value vs disclosure/cardinality evidence |
| OPEN-OBS-029 | health endpoint concrete routes/protocols | Phase 13/API | runtime/deployment needs + disclosure review |
| OPEN-OBS-030 | health probe thresholds/timeouts | Phase 13/SRE | runtime/startup/failure evidence |
| OPEN-OBS-031 | synthetic journey execution platform/schedule | Phase 13/15 | isolation, credential and cost model |
| OPEN-OBS-032 | telemetry encryption/backend key implementation | Phase 13/Security | storage/network threat model + key authority |
| OPEN-OBS-033 | observability data residency topology | Product/Security/Compliance | customer/regulatory geography evidence |
| OPEN-OBS-034 | diagnostic export format/size limits | Product/Security/Capacity | support/export use case and leakage/load evidence |
| OPEN-OBS-035 | whether enabled outbound webhooks require dedicated SLO/alert commitments | Product/SRE | Product enablement plus contractual/operational impact evidence |
| OPEN-OBS-036 | exact semantic-convention machine-readable schema format | implementation/governance | tooling/conformance/portability evidence |
| OPEN-OBS-037 | authoritative Product applicability for conditional Phase 12 Product-facing profiles, initially outbound-webhook enablement and protected-artifact direct-delivery exposure | Product | accepted Product authority proving enabled/exposed vs not enabled/not exposed for each conditional capability; unproven state remains OPEN |

## Fixed properties — not OPEN

The following are fixed by Phase 12 and SHALL NOT be delegated to tooling defaults:

- telemetry is evidence, not business/security/recovery authority;
- audit is separate from ordinary observability;
- platform operational observability is separate from customer monitoring durable acceptance;
- secrets are excluded from ordinary observability;
- trusted tenant context cannot be selected from caller/provider correlation data;
- raw protected URLs/query/cursors/capabilities are not ordinary telemetry;
- metric dimensions are bounded by profile;
- health distinguishes liveness, readiness, degradation, draining, saturation and recovery quarantine;
- missing telemetry is not success by default;
- SLI semantics are explicit before numeric SLOs;
- alert profiles require owner/action/clear semantics;
- telemetry pipeline failure/backpressure is bounded;
- incompatible semantic changes require versioning/migration;
- every accepted Phase 11 reliability profile has an explicit same-key Phase 12 observability applicability join;
- duplicate-sensitive observability distinguishes temporary comparison dependency outage, historical comparison continuity loss and compromised comparison trust according to the owning Phase 11 profile;
- comparison/equality diagnostics cannot become a cross-tenant/cross-consumer oracle, retry authority or duplicate proof;
- correctness gates such as authorization, mandatory audit and message-equivalence proof cannot be weakened by assigning them an error-budget allowance;
- unknown/unproven Product applicability remains OPEN and is not represented as disabled or `NO_APPLICABLE_CASE`;
- exact-state evidence and separate merge authorization remain mandatory.

## Acceptance blockers

Phase 12 SHALL NOT be accepted while any applicable condition remains:

1. a critical Phase 11 capability lacks diagnostic/health evidence;
2. signal families/fields lack classification/cardinality policy;
3. secrets or protected raw URL/query data are permitted in ordinary telemetry;
4. correlation/trace identifiers can influence protected authority;
5. tenant telemetry query/isolation semantics are undefined;
6. liveness/readiness/degradation/draining/recovery quarantine are conflated;
7. telemetry outage can be counted as SLI success;
8. an SLI lacks explicit population/numerator/denominator or equivalent distribution semantics;
9. numeric SLO/error-budget/threshold values are asserted without evidence;
10. alerting lacks owner/action/clear/suppression semantics;
11. observability pipeline can create unbounded backlog/retry/cost amplification;
12. audit or customer telemetry is silently replaced by ordinary observability;
13. critical compatibility/mixed-version behavior is undefined;
14. leakage, broken propagation, cardinality explosion, telemetry loss and recovery-quarantine vectors lack expected outcomes;
15. a backend/vendor/default is treated as architecture without decision evidence;
16. deterministic/AI/scanner green evidence is represented as Phase acceptance or merge authorization;
17. any accepted Phase 11 `reliability_profile_id@version` lacks an explicit Phase 12 signal/health/SLI/alert/fault applicability row;
18. duplicate-sensitive comparison observability collapses the accepted Phase 11 distinctions among temporary dependency outage, historical comparison continuity loss and compromised/untrusted comparison authority;
19. ordinary telemetry exposes comparison-derived values or query behavior that can answer protected equality across tenant/consumer scopes;
20. comparison-security-service work or its telemetry can be amplified without bounded tenant/workload/profile budgets;
21. a direct SLO/error budget is used to tolerate failure of a hard correctness authority such as duplicate-equivalence proof, current authorization or mandatory audit;
22. a healthy generic worker/security service state can mask an applicable `health.message-equivalence@1` continuity/trust block;
23. unknown/unproven applicability is converted to `NO_APPLICABLE_CASE`, disabled, absent or enabled without accepted authority;
24. a Product-gated profile is activated by implementation configuration while `OPEN-OBS-037` or a capability-specific applicability OPEN remains unresolved.

## Closure rule

Closing one OPEN item does not authorize a downstream technology choice beyond its scope. Material closure changes Phase 12 or later owning authority through ordinary reviewed governance and exact-HEAD validation.

The join/comparison/applicability blockers above do not create a technology choice. They enforce inherited Phase 10/11 properties and Product-authority discipline using the existing Phase 12 signal, health, validation, security and capacity authorities.
