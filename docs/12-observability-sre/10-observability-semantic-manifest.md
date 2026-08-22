# Phase 12 — Observability Semantic Manifest

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This manifest is the enforcement-oriented join across signal semantics, health, correlation, SLI, alerting, security/cardinality, pipeline resilience, compatibility and evidence.

An implementation mapping MAY add backend-specific fields but SHALL NOT weaken the required manifest properties.

The complete Phase 12 observability record is keyed by stable Phase 12 profile identity and, for inherited reliability coverage, by the exact Phase 11 `reliability_profile_id@profile_version`. Narrative resemblance is not a valid join.

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

For every accepted Phase 11 reliability profile, the Phase 12 join additionally records:

```text
reliability_profile_id
reliability_profile_version
diagnostic_signal_bindings
health_binding
sli_applicability
alert_applicability
required_fault_vectors
security_cardinality_constraints
```

A `no_applicable_case` SLI or alert decision is valid only when this manifest states why a direct service-level/action contract would be semantically wrong or redundant and names the indirect outcome profile that carries customer/system impact where applicable. Omission is not `no_applicable_case`.

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
| `obs.security.authority-freshness@1` | health/event | inability to prove current authorization/trust/config/placement authority where operationally required | protected/internal; no sensitive reason disclosure publicly |
| `obs.message-equivalence.admission@1` | metric/event/log | duplicate-sensitive admission outcome at the owning Phase 11 profile boundary, distinguishing proven duplicate, identity conflict, unknown equivalence, reconciliation block and trust failure | MUST NOT emit fingerprint/MAC/digest/comparison bytes as metric labels or equality lookup keys; message IDs are diagnostic only and not metric labels |
| `obs.message-equivalence.verifier@1` | metric/health/event | bounded verifier/comparison dependency state: temporary availability, historical continuity, trust and comparison-work pressure | no key material; verifier/profile generation references are protected diagnostic identifiers only, never public/cross-scope equality handles |
| `obs.configuration.generation@1` | event/health | accepted configuration generation/currentness and last-known-good eligibility summary | configuration content/secrets excluded; generation reference diagnostic only |
| `obs.audit.responsibility-health@1` | health/event | safe evidence that mandatory-audit responsibility path is available/blocked without copying audit records | accountability reference only; ordinary telemetry cannot prove audit commit |
| `obs.artifact.lifecycle@1` | event/health/metric | artifact storage/releasability/delivery-generation operational progress and reconciliation state | no artifact bytes/capabilities; tenant/artifact IDs controlled as diagnostic identifiers |

### Message-equivalence outcome semantics

`obs.message-equivalence.admission@1` SHALL carry bounded canonical classes sufficient to preserve the Phase 11 boundary-specific distinction:

```text
comparison_outcome_class:
  equivalent_duplicate_proven
  identity_conflict
  equivalence_unknown
  verifier_temporarily_unavailable
  historical_comparison_continuity_blocked
  comparison_authority_compromised_or_untrusted
  poison_or_contract_invalid

reliability_failure_class:
  <the exact Phase 11 failure class selected at the owning profile boundary>

reliability_degradation_mode:
  <the exact Phase 11 degradation mode selected at the owning profile boundary>
```

The same `comparison_outcome_class=verifier_temporarily_unavailable` can map differently by owning reliability profile, exactly as Phase 11 requires:

- `rel.consumer-inbox-effect@1` → `unavailable:reconciliation_blocked` when historical continuity remains intact;
- `rel.replay-consume-state@1` → inability to establish the historical equality proof is observed as `recovery_continuity_blocked:reconciliation_blocked`; its unrelated base generic `unavailable:fail_closed` remains unchanged;
- `rel.secret-key-authority@1` → temporary verifier/key-service outage remains `unavailable:capability_unavailable` at that authority boundary;
- continuity loss/rollback/mismatch/uninterpretable retired verifier/profile → `recovery_continuity_blocked:reconciliation_blocked` for duplicate-sensitive effect/replay profiles;
- compromised/untrusted comparison authority → `compromised_or_untrusted:fail_closed`.

Observability SHALL report the selected Phase 11 class/mode; it SHALL NOT normalize those distinct boundaries into one permissive generic `unavailable` state.

## Core health profiles

| Profile | Scope | Required dimensions |
|---|---|---|
| `health.api-bff@1` | API/BFF operation classes | liveness, workload readiness, dependency degradation, saturation, draining |
| `health.async-worker@1` | worker workload class | liveness, durable progress, backlog/lease pressure, dependency degradation, draining |
| `health.provider-adapter@1` | provider/integration class | readiness, throttling/unavailable/ambiguity/trust state, saturation |
| `health.realtime@1` | realtime admission/delivery | liveness, admission readiness, delivery degradation, resync pressure, draining |
| `health.control-plane@1` | control plane/placement/config distribution | liveness, authority/config freshness summary, degradation, saturation |
| `health.cell@1` | logical cell/workload class | readiness, placement/generation freshness summary, degradation, draining, recovery quarantine |
| `health.security-authority@1` | authorization/secret/key/trust authority class | availability, currentness, trust, revocation/generation summary, no public sensitive detail |
| `health.message-equivalence@1` | duplicate-sensitive inbox/replay/comparison proof path | verifier availability, historical comparison continuity, comparison trust, reconciliation block, comparison/KMS saturation; no equality oracle |
| `health.customer-telemetry@1` | customer-monitoring durable acceptance/projections | acceptance readiness, projection progress, backlog/saturation, recovery continuity |
| `health.audit-plane@1` | mandatory audit responsibility path | availability/durable-responsibility eligibility summary without substituting for authoritative audit evidence |
| `health.artifact@1` | artifact storage/delivery lifecycle | storage availability, integrity/reconciliation, delivery-generation/governance block, saturation |
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
| `sli.control-plane.admission@1` | placement/config/lifecycle operations for eligible control-plane work | OPEN |
| `sli.cell.admission@1` | eligible cell admission/readiness outcome by stable workload class | OPEN |
| `sli.artifact.delivery@1` | eligible protected artifact lifecycle/delivery outcome where Product exposes it | OPEN |
| `sli.recovery.convergence@1` | recovery/reconciliation progress/evidence-gap convergence | OPEN |

Each SLI inherits missing-data=`unknown` unless its specialized profile proves another behavior.

Correctness/security authorities such as message-equivalence proof, current authorization and mandatory audit may intentionally have `no_applicable_case` for a **direct** SLO: their required correctness is a hard gate, not an error-budget allowance. Their availability/customer impact remains measurable through the consuming API/async/recovery outcome SLIs.

## Core alert families

| Alert family | Required action semantics |
|---|---|
| `alert.customer-impact@1` | actionable user/capability outcome degradation |
| `alert.durable-progress@1` | backlog/lag/quarantine/reconciliation progress risk |
| `alert.capacity-saturation@1` | bounded resource pressure requiring capacity/admission action |
| `alert.security-trust@1` | trust/current-authority/comparison-authority anomaly routed to Security ownership |
| `alert.recovery-continuity@1` | recovery or historical-comparison continuity block requiring reconciliation/recovery action |
| `alert.telemetry-integrity@1` | signal loss/broken propagation/pipeline blind spot |

Concrete thresholds/windows remain OPEN.

## Canonical Phase 11 → Phase 12 reliability join

This table is mandatory. It closes the ambiguity between “Phase 12 should observe Phase 11” and which exact profile/evidence actually applies.

| Phase 11 reliability profile | Diagnostic signal binding | Health binding | SLI applicability | Alert applicability | Required vectors / security-cardinality notes |
|---|---|---|---|---|---|
| `rel.control-plane-placement@1` | `obs.operation.state@1`, `obs.security.authority-freshness@1`, `obs.recovery.reconciliation@1` | `health.control-plane@1` | `sli.control-plane.admission@1` | customer-impact, recovery-continuity, security-trust as applicable | OBSV-013/014/015/021; no physical placement identity in public/canonical dimensions |
| `rel.cell-transactional-store@1` | `obs.request.outcome@1`, `obs.operation.state@1`, `obs.recovery.reconciliation@1` | `health.cell@1` | `sli.cell.admission@1` plus consuming `sli.api.outcome@1` | customer-impact, recovery-continuity, capacity-saturation | OBSV-013/014/016/025; DB/schema/topology identifiers privileged diagnostics only |
| `rel.security-session-authority@1` | `obs.security.authority-freshness@1`, safe request outcome | `health.security-authority@1` | direct SLI=`no_applicable_case` because authorization correctness/currentness is a hard security gate; impact appears in `sli.api.outcome@1` | security-trust, customer-impact where service impact exists | OBSV-003/013/015/027; no token/session/deny evidence values in telemetry |
| `rel.placement-reference-cache@1` | `obs.security.authority-freshness@1`, control-plane state | `health.control-plane@1` | direct SLI=`no_applicable_case`; impact measured by control-plane/cell admission SLIs | recovery-continuity/customer-impact | OBSV-013/014/021; cached physical placement details remain privileged |
| `rel.performance-cache@1` | request outcome/latency and saturation | `health.api-bff@1` | `sli.api.outcome@1`, `sli.api.latency@1` | customer-impact, capacity-saturation | OBSV-011/025; cache keys/content never become public telemetry dimensions |
| `rel.replay-consume-state@1` | `obs.message-equivalence.admission@1`, `obs.message-equivalence.verifier@1`, `obs.recovery.reconciliation@1` | `health.message-equivalence@1`, `health.recovery@1` | direct SLI=`no_applicable_case` because replay/equality correctness is a hard gate; convergence appears in `sli.recovery.convergence@1` | recovery-continuity, security-trust | OBSV-023/031/032/033/034/035/036; no comparison bytes/fingerprints/equality lookup oracle |
| `rel.secret-key-authority@1` | `obs.security.authority-freshness@1`, `obs.message-equivalence.verifier@1` where historical verifier is used | `health.security-authority@1`, conditional `health.message-equivalence@1` | direct SLI=`no_applicable_case` for cryptographic correctness; dependent service SLIs carry availability impact | security-trust, durable-progress where a dependent proof blocks | OBSV-015/031/033/034/035; no key material/key handles as public dimensions |
| `rel.configuration-authority@1` | `obs.configuration.generation@1`, `obs.security.authority-freshness@1` | `health.control-plane@1`, `health.cell@1` as target-specific summary | direct SLI=`no_applicable_case`; control-plane/cell SLIs carry admission impact | customer-impact, security-trust where stale config affects authority | OBSV-013/021; configuration contents/secrets excluded |
| `rel.outbox-publication@1` | `obs.async.progress@1`, operation/message correlation | `health.async-worker@1` | `sli.async.progress@1` | durable-progress, capacity-saturation | OBSV-001/016/025; message ID diagnostic only, not metric label |
| `rel.broker-job-transport@1` | `obs.async.progress@1`, transport backlog/drop/lag | `health.async-worker@1` | `sli.async.progress@1` | durable-progress, capacity-saturation | OBSV-008/016/025; broker/topic physical identity not canonical contract identity |
| `rel.consumer-inbox-effect@1` | `obs.async.progress@1`, `obs.message-equivalence.admission@1`, `obs.message-equivalence.verifier@1` | `health.async-worker@1`, `health.message-equivalence@1` | `sli.async.progress@1`; direct equality SLI=`no_applicable_case` because equality correctness cannot have an error budget | durable-progress, recovery-continuity, security-trust | OBSV-031..036 plus OBSV-016; duplicate admission emits class only, never comparison value |
| `rel.external-provider@1` | `obs.provider.operation@1`, operation/reconciliation state | `health.provider-adapter@1` | `sli.provider.outcome@1` | customer-impact, durable-progress, capacity-saturation, security-trust when compromised | OBSV-001/015/017/025; provider error/body bounded/redacted |
| `rel.realtime-fanout@1` | `obs.realtime.lifecycle@1` | `health.realtime@1` | `sli.realtime.delivery@1` | customer-impact, capacity-saturation | OBSV-001/013/025; connection/auth capability not telemetry authority |
| `rel.webhook-delivery@1` | `obs.webhook.delivery@1`, reconciliation state | `health.async-worker@1` plus destination-specific diagnostic health | `sli.webhook.convergence@1` only when Product enables the capability; otherwise `no_applicable_case` | durable-progress/customer-impact only when enabled | OBSV-017/019/025; destination generation separated from delivery identity; signing secrets excluded |
| `rel.telemetry-plane@1` | `obs.observability.pipeline@1` | `health.observability-pipeline@1` | `sli.observability.integrity@1` | telemetry-integrity, capacity-saturation | OBSV-008/010/011/026; explicitly optional operational telemetry, not customer acceptance/audit |
| `rel.customer-telemetry-acceptance@1` | `obs.telemetry.acceptance@1`, async/recovery progress | `health.customer-telemetry@1` | `sli.customer-telemetry.acceptance@1` | customer-impact, durable-progress, capacity-saturation, recovery-continuity | OBSV-010/012/016/025; canonical observation identity scope is not an observability authorization handle |
| `rel.mandatory-audit-plane@1` | `obs.audit.responsibility-health@1` plus safe `accountability_reference` only | `health.audit-plane@1` | direct SLI=`no_applicable_case` for audit correctness/durability; consuming protected-operation SLI records service impact without permitting audit loss | customer-impact/security-trust if audit authority blocks protected operation | OBSV-009/011/015; ordinary telemetry never proves or copies audit evidence |
| `rel.artifact-storage@1` | `obs.artifact.lifecycle@1`, recovery/reconciliation state | `health.artifact@1` | `sli.artifact.delivery@1` where Product exposes delivery | customer-impact, recovery-continuity, capacity-saturation, security-trust where governance blocked | OBSV-014/024/025/028; no artifact bytes/capabilities/secret URLs |
| `rel.reporting-derived@1` | request/operation/async progress | `health.api-bff@1`, `health.async-worker@1` | `sli.api.outcome@1` and/or `sli.async.progress@1` by execution class | customer-impact, durable-progress, capacity-saturation | OBSV-016/025/029; report/filter payloads bounded/redacted |
| `rel.privileged-operations@1` | `obs.operation.state@1`, `obs.security.authority-freshness@1`, `obs.recovery.reconciliation@1` | `health.security-authority@1`, `health.recovery@1`, workload health | `sli.async.progress@1` for durable operations; direct authorization SLI=`no_applicable_case` | security-trust, recovery-continuity, durable-progress | OBSV-003/014/015/028; privileged targets/credentials not ordinary dimensions |

### Join completeness rule

The exact accepted Phase 11 profile key set is the source set for this table. A future Phase 11 profile addition/change is a Phase 12 compatibility input: Phase 12 conformance SHALL fail until the new/changed reliability key has an explicit observability join or an evidence-backed successor mapping.

A signal/health/SLI/alert mapping SHALL NOT alter the Phase 11 `failure_class:degradation_mode` decision. It exposes that decision and its evidence state only.

## Message-equivalence observability safeguards

For `rel.consumer-inbox-effect@1`, `rel.replay-consume-state@1` and applicable `rel.secret-key-authority@1` paths:

- comparison evidence bytes, digests, MACs, keyed fingerprints and canonicalized protected content SHALL NOT be logged or exposed as metric labels;
- comparison profile/version and verifier generation references MAY be retained only as protected bounded diagnostic identifiers where needed for compatibility/recovery diagnosis;
- no telemetry query may offer unrestricted “find equal message/content/fingerprint across tenants/consumers” semantics;
- `message_id`, fingerprint-like values or verifier references never become authorization, routing, ordering, retry, replay or effect authority;
- comparison/KMS calls, latency, saturation and failures are aggregated under bounded profile/workload dimensions rather than attacker-controlled message/content dimensions;
- temporary availability, historical continuity loss and compromised trust remain separate health/outcome states and have different clear predicates;
- reachability restoration may clear only a temporary availability observation after the owning authority successfully re-establishes the required proof; it cannot clear continuity/trust failure by itself.

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
- any accepted Phase 11 reliability profile lacks an explicit same-key Phase 12 join/applicability decision;
- a metric admits an unbounded protected dimension without evidence;
- audit or customer telemetry is silently collapsed into operational observability;
- a profile treats telemetry as authorization/retry/recovery authority;
- duplicate/equality observability collapses verifier temporary unavailability, historical continuity loss and compromised trust into one state;
- comparison evidence/fingerprint telemetry can become a cross-tenant/cross-consumer equality oracle;
- a direct SLI/error budget is used to tolerate correctness failure in authorization, mandatory audit or message-equivalence proof.
