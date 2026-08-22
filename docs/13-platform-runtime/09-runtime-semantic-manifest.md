# Phase 13 — Runtime Semantic Manifest

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This manifest is the enforcement-oriented join for Phase 13. It binds runtime roles, identity, lifecycle, isolation, network, state ports, capacity, recovery and accepted Phase 11/12 semantics to stable canonical profile IDs.

Implementation-specific deployment objects MAY map to these records but SHALL NOT weaken or rename their semantics without compatibility review.

## Runtime profile schema

Every runtime profile records:

```text
runtime_profile_id
profile_version
principal_class
lifecycle_class
isolation_class
ingress_profile
egress_profile
state_ports
secret_reference_classes
required placement/current-authority checks
resource/concurrency isolation
Phase 11 reliability bindings
Phase 12 health/signal/SLI bindings
recovery/fencing obligations
validation vectors
OPEN decisions
```

Omission is not `NO_APPLICABLE_CASE`. If a direct upstream reliability/health profile is genuinely not applicable, the manifest states the reason and names the enclosing outcome/evidence profile.

## Canonical runtime profiles and exact joins

| Runtime profile | Isolation / ingress / egress | Required ports / authority boundary | Accepted Phase 11 reliability bindings | Accepted Phase 12 evidence bindings | Required Phase 13 vectors |
|---|---|---|---|---|---|
| `runtime.web-bff@1` | `isolation.confidential-web@1`; public/browser; `egress.platform-bounded@1` | session/API/realtime-ticket authorities; no tenant DB owner | `rel.security-session-authority@1`, `rel.performance-cache@1` where cache used | `health.api-bff@1`, `health.security-authority@1`; `obs.request.outcome@1`, `obs.security.authority-freshness@1`; impact `sli.api.outcome@1`, `sli.api.latency@1` | `PRTV-001`, `PRTV-002`, `PRTV-003`, `PRTV-004`, `PRTV-013`, `PRTV-014`, `PRTV-016`, `PRTV-017`, `PRTV-035` |
| `runtime.api@1` | `isolation.application-serving@1`; authenticated API; `egress.platform-bounded@1` plus connector only through accepted adapter | `port.transactional@1`, `port.reliability-state@1`, `port.audit@1`, `port.observability@1`, bounded `port.ephemeral@1`; no migration owner | `rel.cell-transactional-store@1`, `rel.security-session-authority@1`, `rel.performance-cache@1`, `rel.configuration-authority@1` | `health.api-bff@1`, `health.cell@1`, `health.security-authority@1`; `obs.request.outcome@1`, `obs.configuration.generation@1`; `sli.api.outcome@1`, `sli.api.latency@1`, `sli.cell.admission@1` | `PRTV-002`, `PRTV-003`, `PRTV-004`, `PRTV-005`, `PRTV-008`, `PRTV-009`, `PRTV-010`, `PRTV-013`, `PRTV-014`, `PRTV-016`, `PRTV-027`, `PRTV-028`, `PRTV-030`, `PRTV-031`, `PRTV-035` |
| `runtime.worker@1` | `isolation.workload-bulkhead@1`; durable work transport; workload-specific platform/connector egress | `port.job-event-transport@1`, `port.reliability-state@1`, plus transactional/provider/artifact/telemetry ports only per workload | workload-specific subset of exact accepted profiles: `rel.outbox-publication@1`, `rel.broker-job-transport@1`, `rel.consumer-inbox-effect@1`, `rel.external-provider@1`, `rel.webhook-delivery@1`, `rel.customer-telemetry-acceptance@1`, `rel.artifact-storage@1`, `rel.reporting-derived@1` | `health.async-worker@1` plus exact specialized `health.provider-adapter@1`, `health.webhook-delivery@1`, `health.customer-telemetry@1`, `health.artifact@1`, `health.message-equivalence@1` only when owning workload requires them; `obs.async.progress@1`; impact `sli.async.progress@1` plus specialized SLI where applicable | `PRTV-004`, `PRTV-005`, `PRTV-011`, `PRTV-013`, `PRTV-014`, `PRTV-015`, `PRTV-016`, `PRTV-018`, `PRTV-026`, `PRTV-027`, `PRTV-028`, `PRTV-029`, `PRTV-030`, `PRTV-031`, `PRTV-034`, `PRTV-035` |
| `runtime.realtime@1` | `isolation.realtime@1`; protected realtime; `egress.platform-bounded@1` | replay/current-auth/placement/fanout/observability capabilities; no general DB owner | `rel.realtime-fanout@1`, `rel.security-session-authority@1`, `rel.replay-consume-state@1` where accepted connection-capability consumption state applies | `health.realtime@1`, `health.security-authority@1`; `obs.realtime.lifecycle@1`, `obs.security.authority-freshness@1`; `sli.realtime.delivery@1` | `PRTV-002`, `PRTV-003`, `PRTV-004`, `PRTV-005`, `PRTV-008`, `PRTV-012`, `PRTV-013`, `PRTV-014`, `PRTV-031`, `PRTV-033`, `PRTV-035` |
| `runtime.control-plane@1` | `isolation.control-plane@1`; privileged platform/API; `egress.platform-bounded@1` | `port.control-placement@1`, configuration/identity authorities; no universal tenant operational DB | `rel.control-plane-placement@1`, `rel.placement-reference-cache@1`, `rel.configuration-authority@1`, `rel.secret-key-authority@1` only for the secret/key dependencies this runtime actually uses | `health.control-plane@1`, `health.security-authority@1`; `obs.operation.state@1`, `obs.configuration.generation@1`, `obs.security.authority-freshness@1`; `sli.control-plane.admission@1` | `PRTV-005`, `PRTV-006`, `PRTV-007`, `PRTV-008`, `PRTV-009`, `PRTV-013`, `PRTV-014`, `PRTV-015`, `PRTV-016`, `PRTV-029`, `PRTV-030`, `PRTV-032`, `PRTV-033`, `PRTV-035`, `PRTV-036` |
| `runtime.automation@1` | `isolation.controlled-execution@1`; durable privileged operation; target-specific `egress.connector-bounded@1` or `egress.none@1` | target-scoped credentials, `port.reliability-state@1`, approved connector/artifact/observability ports only | `rel.privileged-operations@1`, plus `rel.external-provider@1` / `rel.artifact-storage@1` only when the accepted automation operation uses those capabilities | `health.async-worker@1`, `health.security-authority@1` and specialized provider/artifact health when applicable; `obs.operation.state@1`; impact `sli.async.progress@1` / specialized outcome SLI | `PRTV-003`, `PRTV-013`, `PRTV-014`, `PRTV-015`, `PRTV-016`, `PRTV-018`, `PRTV-021`, `PRTV-030`, `PRTV-031`, `PRTV-035` |
| `runtime.untrusted-parser@1` | `isolation.untrusted-content@1`; staged untrusted input; `egress.none@1` by default | temporary workspace + staged input/output; no general secrets/DB | direct durable reliability profile=`NO_APPLICABLE_CASE`: parser execution is subordinate to the enclosing import/artifact/operation profile, which owns durable responsibility; parser crash/timeout is reported to that owner | direct service SLI=`NO_APPLICABLE_CASE`; execution evidence uses enclosing `obs.operation.state@1` and, when scheduled as durable work, `health.async-worker@1` / `sli.async.progress@1`; resource pressure maps to `alert.capacity-saturation@1` | `PRTV-019`, `PRTV-020`, `PRTV-030`, `PRTV-031`, `PRTV-035` |
| `runtime.migration-admin@1` | `isolation.privileged-data-admin@1`; release/admin-authorized only; `egress.privileged-bounded@1` | dedicated schema/data-admin state port mapping + `port.audit@1`; not serving traffic | `rel.privileged-operations@1`, plus owning transactional/configuration reliability profiles for the migration scope | `health.security-authority@1`, `health.async-worker@1` for durable migration work; `obs.operation.state@1`, `obs.security.authority-freshness@1`; impact through `sli.async.progress@1` where durable | `PRTV-003`, `PRTV-013`, `PRTV-014`, `PRTV-015`, `PRTV-016`, `PRTV-022`, `PRTV-023`, `PRTV-024`, `PRTV-030`, `PRTV-031`, `PRTV-034`, `PRTV-035` |
| `runtime.recovery@1` | `isolation.recovery@1`; recovery-authorized only; `egress.privileged-bounded@1` | current recovery/security/governance authorities, `port.reliability-state@1`, `port.audit@1`, affected state ports by explicit recovery scope | `rel.privileged-operations@1`, `rel.control-plane-placement@1`, `rel.replay-consume-state@1`, `rel.secret-key-authority@1`, plus affected owning reliability profile | `health.recovery@1`, `health.security-authority@1`, specialized affected health profiles; `obs.recovery.reconciliation@1`, `obs.security.authority-freshness@1`, `obs.operation.state@1`; `sli.recovery.convergence@1` | `PRTV-005`, `PRTV-008`, `PRTV-009`, `PRTV-015`, `PRTV-016`, `PRTV-025`, `PRTV-026`, `PRTV-027`, `PRTV-029`, `PRTV-031`, `PRTV-033`, `PRTV-035` |
| `runtime.edge-optional@1` | `isolation.edge-untrusted-boundary@1`; Internet; bounded origin/platform egress | optional acceleration/filter/routing only; no business state-port authority | direct business reliability profile=`NO_APPLICABLE_CASE`: origin BFF/API/realtime reliability profiles own protected semantics; edge availability is an external implementation dependency only if selected | direct canonical service-health authority=`NO_APPLICABLE_CASE`; request/edge implementation diagnostics may feed `obs.request.outcome@1`, while customer impact remains in origin `health.api-bff@1`/service SLIs | `PRTV-001`, `PRTV-002`, `PRTV-004`, `PRTV-018`, `PRTV-030`, `PRTV-035`, `PRTV-036` |

Conditional specialized bindings in the table are closed only by the owning accepted workload/Product authority. Runtime implementation SHALL NOT activate a Phase 12 Product-gated SLI/alert whose applicability remains `OPEN-OBS-037`/`OPEN-OBS-035`.

## Canonical isolation profiles

- `isolation.confidential-web@1` — browser-session confidentiality without domain DB ownership.
- `isolation.application-serving@1` — normal application least privilege and tenant-scoped state access.
- `isolation.workload-bulkhead@1` — workload-specific concurrency/network/secret/state isolation.
- `isolation.realtime@1` — long-lived connection capacity separated from normal API/worker capacity.
- `isolation.control-plane@1` — global placement/lifecycle authority separated from tenant operational state.
- `isolation.controlled-execution@1` — target-scoped automation with explicit resource/credential/egress envelope.
- `isolation.untrusted-content@1` — parser/transform sandbox with no implicit network/secret/data authority.
- `isolation.privileged-data-admin@1` — migration/query/admin privilege unavailable to serving principals.
- `isolation.recovery@1` — recovery/reconciliation authority with current-state fencing.
- `isolation.edge-untrusted-boundary@1` — external traffic boundary, never business authorization authority.

## Canonical egress profiles

```text
egress.none@1
egress.platform-bounded@1
egress.connector-bounded@1
egress.privileged-bounded@1
```

A runtime's egress profile is a maximum capability; application-level destination/authorization checks still apply.

## Canonical lifecycle records

Per-generation cell/runtime lifecycle uses:

```text
provisioning
validating
admitted
active
draining
quarantined
retired
failed
```

Replacement is a multi-generation operation, not a single-generation lifecycle value. The predecessor and successor retain distinct lifecycle/generation evidence.

Phase 12 health values remain separate. Implementations SHALL NOT collapse lifecycle and health into one boolean or one vendor readiness field.

## Generation set

Phase 13 tracks distinct identities/generations as applicable:

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

These do not replace upstream authorization/revocation, schema, artifact-delivery, replay or cryptographic-verifier generations. A mapping must preserve which authority owns each generation.

## Canonical state ports

```text
port.control-placement@1
port.transactional@1
port.reliability-state@1
port.audit@1
port.customer-telemetry@1
port.artifact@1
port.ephemeral@1
port.job-event-transport@1
port.observability@1
port.secret-key@1
port.object-staging@1
```

Vendor client/endpoint/SDK identifiers never become canonical port IDs.

## Join completeness rules

- every canonical runtime profile row SHALL include an explicit Phase 11 disposition, Phase 12 evidence disposition and applicable PRTV vectors;
- a conditional specialized binding names the accepted owner that activates it; implementation presence is insufficient;
- `NO_APPLICABLE_CASE` may be used only with the reason and enclosing impact/evidence path recorded in the row;
- adding/changing an accepted Phase 11 reliability or Phase 12 health/profile relevant to a runtime is a Phase 13 compatibility input; the runtime join becomes incomplete until reviewed;
- vendor/orchestrator readiness/health fields are implementation adapters, never replacements for exact accepted Phase 12 profile meaning.

## Co-location decision record

Any implementation co-locating profiles that are separate here records evidence for:

```text
profiles co-located
combined effective principal
secret/state-port access union
network/egress union
resource/bulkhead enforcement
lifecycle/drain compatibility
failure blast radius
reason co-location does not weaken either profile
```

Absent this evidence, more privileged/risky profiles remain separated.

## Product applicability

Runtime implementation SHALL NOT resolve `OPEN-OBS-037` or other Product-scope OPEN decisions by deploying/not deploying a component. A prepared runtime profile may exist without proving Product enablement.

## Manifest blockers

Acceptance is blocked when:

- a runtime role lacks explicit principal/isolation/lifecycle/port/network bindings;
- a runtime row lacks explicit Phase 11/Phase 12/fault-vector dispositions;
- vendor resource names replace canonical runtime/port/profile identities;
- co-location creates a privilege/egress/state union broader than accepted profiles;
- network presence is treated as trust;
- lifecycle is collapsed into process liveness/readiness;
- replacement conflates predecessor and successor runtime generations;
- a runtime generation overrides placement/security/governance authority;
- state-port product behavior weakens accepted authority/failure semantics;
- a privileged/parser/automation profile inherits ordinary application or unrestricted infrastructure authority by convenience;
- physical topology enters canonical tenant/API/event/resource identity;
- Product scope/applicability is inferred from runtime deployment state.