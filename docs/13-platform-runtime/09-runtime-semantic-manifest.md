# Phase 13 — Runtime Semantic Manifest

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This manifest is the enforcement-oriented join for Phase 13. It binds runtime roles, identity, lifecycle, isolation, network, state ports, capacity, recovery and Phase 12 observability to stable canonical profile IDs.

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

## Canonical runtime profiles

| Runtime profile | Isolation profile | Ingress | Egress | Required ports / notes |
|---|---|---|---|---|
| `runtime.web-bff@1` | `isolation.confidential-web@1` | public/browser | `egress.platform-bounded@1` | API/session/realtime-ticket authorities; no tenant DB owner |
| `runtime.api@1` | `isolation.application-serving@1` | authenticated API | `egress.platform-bounded@1` plus connector only through accepted adapter | transactional, reliability, audit-intent, observability; bounded non-authoritative cache |
| `runtime.worker@1` | `isolation.workload-bulkhead@1` | durable work transport | workload-specific platform/connector egress | reliability/job-event/transactional/connector/artifact/telemetry as profile requires |
| `runtime.realtime@1` | `isolation.realtime@1` | protected realtime | `egress.platform-bounded@1` | replay/current-auth/placement/fanout/observability; no general DB owner |
| `runtime.control-plane@1` | `isolation.control-plane@1` | privileged platform/API | `egress.platform-bounded@1` | placement/global config/identity authorities; no universal tenant operational DB |
| `runtime.automation@1` | `isolation.controlled-execution@1` | durable privileged operation | target-specific `egress.connector-bounded@1` or none | target-scoped credentials, bounded result/artifact ports |
| `runtime.untrusted-parser@1` | `isolation.untrusted-content@1` | staged untrusted input | `egress.none@1` by default | temporary workspace + bounded staged input/output; no general secrets/DB |
| `runtime.migration-admin@1` | `isolation.privileged-data-admin@1` | release/admin-authorized only | `egress.privileged-bounded@1` | schema/data admin ports and audit; not serving traffic |
| `runtime.recovery@1` | `isolation.recovery@1` | recovery-authorized only | `egress.privileged-bounded@1` | recovery, current security/governance, reliability-state and audit authorities |
| `runtime.edge-optional@1` | `isolation.edge-untrusted-boundary@1` | Internet | bounded origin/platform | optional acceleration/filter/routing; core domain semantics cannot depend on edge-only feature |

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

Cell/runtime lifecycle uses:

```text
provisioning
validating
admitted
active
draining
replacing
quarantined
retired
failed
```

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

## Reliability and observability join

Runtime profiles SHALL expose the applicable accepted Phase 11/12 semantics rather than inventing new status classes. At minimum:

- API/BFF runtime -> API/control-plane/cell admission and current-authority health as applicable;
- worker runtime -> durable-progress/backlog/ambiguity/reconciliation health;
- realtime -> realtime admission/delivery/resync;
- Control Plane/cell -> placement/configuration freshness, draining, quarantine and saturation;
- state ports -> owning reliability profile + Phase 12 health/evidence profile;
- automation/parser/admin/recovery -> explicit operation state, resource saturation, security/trust and recovery signals.

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
- vendor resource names replace canonical runtime/port/profile identities;
- co-location creates a privilege/egress/state union broader than accepted profiles;
- network presence is treated as trust;
- lifecycle is collapsed into process liveness/readiness;
- a runtime generation overrides placement/security/governance authority;
- state-port product behavior weakens accepted authority/failure semantics;
- a privileged/parser/automation profile inherits ordinary application or unrestricted infrastructure authority by convenience;
- physical topology enters canonical tenant/API/event/resource identity;
- Product scope/applicability is inferred from runtime deployment state.