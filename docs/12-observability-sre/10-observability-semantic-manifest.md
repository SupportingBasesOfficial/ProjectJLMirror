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

A `NO_APPLICABLE_CASE` SLI or alert decision is valid only when this manifest states why a direct service-level/action contract would be semantically wrong or redundant and names the indirect outcome profile that carries customer/system impact where applicable. Omission is not `NO_APPLICABLE_CASE`.

An OPEN decision may appear in an applicability field only when the OPEN registry explicitly owns that semantic choice. It is not equivalent to `NO_APPLICABLE_CASE` and SHALL NOT be silently resolved by implementation.

## Core signal profiles

| Profile | Family | Required meaning | Cardinality/security rule |
|---|---|---|---|
| `obs.request.outcome@1` | metric/log/trace | accepted request attempt outcome and latency by stable operation class | no raw URL/query; request ID not metric label |
| `obs.operation.state@1` | event/metric/log | durable long-running operation progress/terminal/reconciliation state | operation ID diagnostic only; bounded indexing |
| `obs.async.progress@1` | metric/event | durable accepted-work age/lag, completion, retry/quarantine/reconciliation pressure | no message payload; message ID not metric label |
| `obs.async.transport@1` | metric/event/health | transport backlog, delivery/lease/checkpoint progress and transport saturation without becoming effect authority | physical broker/topic identifiers are diagnostic only; bounded workload/consumer dimensions |
| `obs.provider.operation@1` | metric/trace/log | normalized provider call outcome/latency/ambiguity | provider error text excluded from metrics; tenant/provider skew bounded |
| `obs.realtime.lifecycle@1` | metric/event/log | admission, subscription, delivery lag, resync lifecycle | connection IDs diagnostic only; no auth capability leakage |
| `obs.webhook.delivery@1` | metric/event/log | webhook obligation/attempt outcome when Product enables it | delivery identity separate from destination generation; no secret/signature leakage |
| `obs.telemetry.acceptance@1` | metric/event | customer-monitoring durable acceptance/projection lag | distinct from operational observability pipeline |
| `obs.observability.pipeline@1` | metric/health/event | exporter/collector ingest, drop, backlog, query/evaluation freshness | self-observation bounded; no recursive false-green |
| `obs.recovery.reconciliation@1` | metric/event/health | recovery/reconciliation progress, quarantine and evidence-gap state | no authority inferred from green state |
| `obs.security.authority-freshness@1` | health/event | inability to prove current authorization/trust/config/placement authority where operationally required | protected/internal; no sensitive reason disclosure publicly |
| `obs.message-equivalence.admission@1` | metric/event/log | duplicate-sensitive admission outcome at the owning Phase 11 profile boundary, distinguishing proven duplicate, identity conflict, unknown equivalence, reconciliation block and trust failure | comparison evidence is not emitted as a metric dimension or equality lookup handle; message IDs are diagnostic only |
| `obs.message-equivalence.verifier@1` | metric/health/event | bounded comparison dependency state: temporary availability, historical continuity, trust and comparison-work pressure | comparison-generation references are protected diagnostic identifiers only, never public/cross-scope equality handles |
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
| `health.webhook-delivery@1` | enabled webhook delivery workload/destination generation | worker liveness, delivery obligation progress, destination degradation/ambiguity, saturation, draining |
| `health.control-plane@1` | control plane/placement/config distribution | liveness, authority/config freshness summary, degradation, saturation |
| `health.cell@1` | logical cell/workload class | readiness, placement/generation freshness summary, degradation, draining, recovery quarantine |
| `health.security-authority@1` | authorization/secret/key/trust authority class | availability, currentness, trust, revocation/generation summary, no public sensitive detail |
| `health.message-equivalence@1` | duplicate-sensitive inbox/replay/comparison proof path | verifier availability, historical comparison continuity, comparison trust, reconciliation block, comparison-work saturation; no equality oracle |
| `health.customer-telemetry@1` | customer-monitoring durable acceptance/projections | acceptance readiness, projection progress, backlog/saturation, recovery continuity |
| `health.audit-plane@1` | mandatory audit responsibility path | availability/durable-responsibility eligibility summary without substituting for authoritative audit evidence |
| `health.artifact@1` | artifact storage/delivery lifecycle | storage availability, integrity/reconciliation, delivery-generation/governance block, saturation |
| `health.observability-pipeline@1` | observability evidence plane | ingest/export/query health, drop/backlog, self-observation confidence |
| `health.recovery@1` | recovery scope | quarantine, reconciliation progress, continuity blocked/eligible summary |

A single process may implement multiple profiles. One global `/health=true` does not replace them.

## Core SLI profiles

| SLI | Outcome semantics | Numeric objective / applicability |
|---|---|---|
| `sli.api.outcome@1` | eligible request success ratio by stable operation class | objective OPEN |
| `sli.api.latency@1` | latency distribution for eligible operation class | objective OPEN |
| `sli.async.progress@1` | accepted-work age/convergence and terminal outcome | objective OPEN |
| `sli.provider.outcome@1` | eligible provider operation normalized outcome | objective OPEN |
| `sli.realtime.delivery@1` | eligible admission/delivery/resync convergence | objective OPEN |
| `sli.webhook.convergence@1` | candidate enabled-webhook obligation terminal-convergence profile | Product applicability `OPEN-OBS-037`; if enabled, activation/commitment `OPEN-OBS-035`; numeric objective OPEN if activated |
| `sli.customer-telemetry.acceptance@1` | durable observation acceptance/projection freshness | objective OPEN |
| `sli.observability.integrity@1` | required signal delivery/propagation/evidence completeness | objective OPEN |
| `sli.control-plane.admission@1` | placement/config/lifecycle operations for eligible control-plane work | objective OPEN |
| `sli.cell.admission@1` | eligible cell admission outcome by stable workload class | objective OPEN |
| `sli.artifact.delivery@1` | candidate protected artifact lifecycle/delivery outcome | Product applicability `OPEN-OBS-037`; objective OPEN if applicable |
| `sli.recovery.convergence@1` | recovery/reconciliation progress/evidence-gap convergence | objective OPEN |

Each SLI inherits missing-data=`unknown` unless its specialized profile proves another behavior.

Correctness/security authorities such as message-equivalence proof, current authorization and mandatory audit may intentionally have `NO_APPLICABLE_CASE` for a **direct** SLO: their required correctness is a hard gate, not an error-budget allowance. Their availability/customer impact remains measurable through the consuming API/async/recovery outcome SLIs.

## Core alert profiles

| Alert profile | Required action semantics |
|---|---|
| `alert.customer-impact@1` | actionable user/capability outcome degradation |
| `alert.durable-progress@1` | backlog/lag/quarantine/reconciliation progress risk |
| `alert.capacity-saturation@1` | bounded resource pressure requiring capacity/admission action |
| `alert.security-trust@1` | trust/current-authority/comparison-authority anomaly routed to Security ownership |
| `alert.recovery-continuity@1` | recovery or historical-comparison continuity block requiring reconciliation/recovery action |
| `alert.telemetry-integrity@1` | signal loss/broken propagation/pipeline blind spot |

Concrete thresholds/windows remain OPEN.

## Canonical Phase 11 → Phase 12 reliability join

This table is mandatory. Every profile, signal, health, SLI, alert and fault-vector reference is an exact canonical ID; prose aliases are invalid as join values.

| Phase 11 reliability profile | Diagnostic signal binding | Health binding | SLI applicability | Alert applicability | Required vectors / security-cardinality notes |
|---|---|---|---|---|---|
| `rel.control-plane-placement@1` | `obs.operation.state@1`, `obs.security.authority-freshness@1`, `obs.recovery.reconciliation@1` | `health.control-plane@1` | `sli.control-plane.admission@1` | `alert.customer-impact@1`, `alert.recovery-continuity@1`, `alert.security-trust@1` | `OBSV-013`, `OBSV-014`, `OBSV-015`, `OBSV-021`; no physical placement identity in public/canonical dimensions |
| `rel.cell-transactional-store@1` | `obs.request.outcome@1`, `obs.operation.state@1`, `obs.recovery.reconciliation@1` | `health.cell@1` | `sli.cell.admission@1`, `sli.api.outcome@1` | `alert.customer-impact@1`, `alert.recovery-continuity@1`, `alert.capacity-saturation@1` | `OBSV-013`, `OBSV-014`, `OBSV-016`, `OBSV-025`; DB/schema/topology identifiers privileged diagnostics only |
| `rel.security-session-authority@1` | `obs.security.authority-freshness@1`, `obs.request.outcome@1` | `health.security-authority@1` | direct SLI=`NO_APPLICABLE_CASE`; impact=`sli.api.outcome@1` | `alert.security-trust@1`, `alert.customer-impact@1` | `OBSV-003`, `OBSV-013`, `OBSV-015`, `OBSV-027`; protected authority evidence values excluded from ordinary telemetry |
| `rel.placement-reference-cache@1` | `obs.security.authority-freshness@1`, `obs.operation.state@1` | `health.control-plane@1` | direct SLI=`NO_APPLICABLE_CASE`; impact=`sli.control-plane.admission@1`, `sli.cell.admission@1` | `alert.recovery-continuity@1`, `alert.customer-impact@1` | `OBSV-013`, `OBSV-014`, `OBSV-021`; cached physical placement details privileged |
| `rel.performance-cache@1` | `obs.request.outcome@1` | `health.api-bff@1` | `sli.api.outcome@1`, `sli.api.latency@1` | `alert.customer-impact@1`, `alert.capacity-saturation@1` | `OBSV-011`, `OBSV-025`; cache keys/content never become public telemetry dimensions |
| `rel.replay-consume-state@1` | `obs.message-equivalence.admission@1`, `obs.message-equivalence.verifier@1`, `obs.recovery.reconciliation@1` | `health.message-equivalence@1`, `health.recovery@1` | direct SLI=`NO_APPLICABLE_CASE`; impact=`sli.recovery.convergence@1` | `alert.recovery-continuity@1`, `alert.security-trust@1` | `OBSV-023`, `OBSV-032`, `OBSV-033`, `OBSV-034`, `OBSV-035`, `OBSV-036`; no comparison-derived equality lookup oracle |
| `rel.secret-key-authority@1` | `obs.security.authority-freshness@1` | `health.security-authority@1` | direct SLI=`NO_APPLICABLE_CASE`; impact profiles=`sli.api.outcome@1`, `sli.async.progress@1`, `sli.recovery.convergence@1` | `alert.security-trust@1`, `alert.durable-progress@1` | `OBSV-015`, `OBSV-027`; protected authority references are non-public diagnostic identifiers |
| `rel.configuration-authority@1` | `obs.configuration.generation@1`, `obs.security.authority-freshness@1` | `health.control-plane@1`, `health.cell@1` | direct SLI=`NO_APPLICABLE_CASE`; impact=`sli.control-plane.admission@1`, `sli.cell.admission@1` | `alert.customer-impact@1`, `alert.security-trust@1` | `OBSV-013`, `OBSV-021`; configuration contents/secrets excluded |
| `rel.outbox-publication@1` | `obs.async.progress@1`, `obs.operation.state@1` | `health.async-worker@1` | `sli.async.progress@1` | `alert.durable-progress@1`, `alert.capacity-saturation@1` | `OBSV-001`, `OBSV-016`, `OBSV-025`; message ID diagnostic only, not metric label |
| `rel.broker-job-transport@1` | `obs.async.transport@1`, `obs.async.progress@1` | `health.async-worker@1` | `sli.async.progress@1` | `alert.durable-progress@1`, `alert.capacity-saturation@1` | `OBSV-008`, `OBSV-016`, `OBSV-025`; broker/topic physical identity not canonical contract identity |
| `rel.consumer-inbox-effect@1` | `obs.async.progress@1`, `obs.message-equivalence.admission@1`, `obs.message-equivalence.verifier@1` | `health.async-worker@1`, `health.message-equivalence@1` | `sli.async.progress@1`; direct equivalence SLI=`NO_APPLICABLE_CASE` | `alert.durable-progress@1`, `alert.recovery-continuity@1`, `alert.security-trust@1` | `OBSV-016`, `OBSV-031`, `OBSV-033`, `OBSV-034`, `OBSV-035`, `OBSV-036`; duplicate admission emits bounded class only |
| `rel.external-provider@1` | `obs.provider.operation@1`, `obs.operation.state@1`, `obs.recovery.reconciliation@1` | `health.provider-adapter@1` | `sli.provider.outcome@1` | `alert.customer-impact@1`, `alert.durable-progress@1`, `alert.capacity-saturation@1`, `alert.security-trust@1` | `OBSV-001`, `OBSV-015`, `OBSV-017`, `OBSV-025`; provider error/body bounded/redacted |
| `rel.realtime-fanout@1` | `obs.realtime.lifecycle@1` | `health.realtime@1` | `sli.realtime.delivery@1` | `alert.customer-impact@1`, `alert.capacity-saturation@1` | `OBSV-001`, `OBSV-013`, `OBSV-025`; connection/auth capability not telemetry authority |
| `rel.webhook-delivery@1` | `obs.webhook.delivery@1`, `obs.recovery.reconciliation@1` | `health.webhook-delivery@1` | if `product_enabled`=`OPEN-OBS-035`; if `product_not_enabled`=`NO_APPLICABLE_CASE`; if `product_state_unproven`=`OPEN-OBS-037` | if `product_enabled`=`OPEN-OBS-035`; if `product_not_enabled`=`NO_APPLICABLE_CASE`; if `product_state_unproven`=`OPEN-OBS-037` | `OBSV-017`, `OBSV-019`, `OBSV-025`; diagnostic/security/recovery evidence remains applicable regardless of Product-facing SLO/alert commitment |
| `rel.telemetry-plane@1` | `obs.observability.pipeline@1` | `health.observability-pipeline@1` | `sli.observability.integrity@1` | `alert.telemetry-integrity@1`, `alert.capacity-saturation@1` | `OBSV-008`, `OBSV-010`, `OBSV-011`, `OBSV-026`; optional operational telemetry distinct from customer acceptance/audit |
| `rel.customer-telemetry-acceptance@1` | `obs.telemetry.acceptance@1`, `obs.async.progress@1`, `obs.recovery.reconciliation@1` | `health.customer-telemetry@1` | `sli.customer-telemetry.acceptance@1` | `alert.customer-impact@1`, `alert.durable-progress@1`, `alert.capacity-saturation@1`, `alert.recovery-continuity@1` | `OBSV-010`, `OBSV-012`, `OBSV-016`, `OBSV-025`; observation identity scope is not observability authorization |
| `rel.mandatory-audit-plane@1` | `obs.audit.responsibility-health@1` | `health.audit-plane@1` | direct SLI=`NO_APPLICABLE_CASE`; impact profiles=`sli.api.outcome@1`, `sli.async.progress@1` | `alert.customer-impact@1`, `alert.security-trust@1` | `OBSV-009`, `OBSV-011`, `OBSV-015`; ordinary telemetry never proves or copies audit evidence |
| `rel.artifact-storage@1` | `obs.artifact.lifecycle@1`, `obs.recovery.reconciliation@1` | `health.artifact@1` | if `product_exposed_delivery`=`sli.artifact.delivery@1`; if `product_not_exposed_delivery`=`NO_APPLICABLE_CASE`; if `product_state_unproven`=`OPEN-OBS-037` | `alert.customer-impact@1`, `alert.recovery-continuity@1`, `alert.capacity-saturation@1`, `alert.security-trust@1` | `OBSV-014`, `OBSV-024`, `OBSV-025`, `OBSV-028`; diagnostic/security/recovery evidence remains applicable regardless of Product-facing delivery SLI |
| `rel.reporting-derived@1` | `obs.request.outcome@1`, `obs.operation.state@1`, `obs.async.progress@1` | `health.api-bff@1`, `health.async-worker@1` | `sli.api.outcome@1`, `sli.async.progress@1` | `alert.customer-impact@1`, `alert.durable-progress@1`, `alert.capacity-saturation@1` | `OBSV-016`, `OBSV-025`, `OBSV-029`; report/filter payloads bounded/redacted |
| `rel.privileged-operations@1` | `obs.operation.state@1`, `obs.security.authority-freshness@1`, `obs.recovery.reconciliation@1` | `health.security-authority@1`, `health.recovery@1`, `health.async-worker@1` | direct authorization SLI=`NO_APPLICABLE_CASE`; impact profiles=`sli.async.progress@1`, `sli.recovery.convergence@1` | `alert.security-trust@1`, `alert.recovery-continuity@1`, `alert.durable-progress@1` | `OBSV-003`, `OBSV-014`, `OBSV-015`, `OBSV-028`; privileged targets/credentials not ordinary dimensions |

### Closed applicability selectors

The Product-state selectors are:

```text
webhook_product_state:
  product_enabled
  product_not_enabled
  product_state_unproven

artifact_delivery_product_state:
  product_exposed_delivery
  product_not_exposed_delivery
  product_state_unproven
```

Their values are derived from accepted Product authority, never implementation defaults or telemetry itself.

`product_state_unproven` is deliberately distinct from `product_not_enabled` / `product_not_exposed_delivery`. It remains `OPEN-OBS-037`; it is neither absence nor `NO_APPLICABLE_CASE`. Underlying diagnostic, security, recovery and governance evidence obligations remain active where the prepared reliability profile applies.

For webhook when `product_enabled`, `OPEN-OBS-035` remains the owner of whether a dedicated SLO/alert commitment is required. Phase 12 SHALL NOT silently resolve that OPEN through this manifest.

Rows that list multiple exact impact SLI/alert profiles define the complete applicable consumer set; runtime operation class selects which member receives an observation, but no new profile identity or semantic alias may be invented locally.

### Join completeness rule

The exact accepted Phase 11 profile key set is the source set for this table. A future Phase 11 profile addition/change is a Phase 12 compatibility input: Phase 12 conformance SHALL fail until the new/changed reliability key has an explicit observability join or an evidence-backed successor mapping.

A signal/health/SLI/alert mapping SHALL NOT alter the Phase 11 `failure_class:degradation_mode` decision. It exposes that decision and its evidence state only.

## Message-equivalence observability safeguards

For `rel.consumer-inbox-effect@1`, `rel.replay-consume-state@1` and their accepted comparison-authority dependency path:

- comparison evidence/content-derived equality material SHALL NOT be logged or exposed as metric labels;
- comparison profile/version and verifier generation references MAY be retained only as protected bounded diagnostic identifiers where needed for compatibility/recovery diagnosis;
- no telemetry query may offer unrestricted “find equal message/content” semantics across tenant/consumer scopes;
- `message_id` or comparison references never become authorization, routing, ordering, retry, replay or effect authority;
- comparison-service calls, latency, saturation and failures are aggregated under bounded profile/workload dimensions rather than attacker-controlled message/content dimensions;
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
- a join uses an undefined prose alias instead of an exact canonical profile/vector/OPEN ID;
- a conditional applicability branch has no closed accepted selector outcome, explicit OPEN owner or explicit `NO_APPLICABLE_CASE`;
- Product state uncertainty is represented as Product absence/disablement or `NO_APPLICABLE_CASE`;
- a metric admits an unbounded protected dimension without evidence;
- audit or customer telemetry is silently collapsed into operational observability;
- a profile treats telemetry as authorization/retry/recovery authority;
- duplicate/equality observability collapses comparison temporary unavailability, historical continuity loss and compromised trust into one state;
- comparison telemetry can become a cross-tenant/cross-consumer equality oracle;
- a direct SLI/error budget is used to tolerate correctness failure in authorization, mandatory audit or message-equivalence proof.
