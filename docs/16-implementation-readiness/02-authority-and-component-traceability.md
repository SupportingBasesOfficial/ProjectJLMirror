# Implementation Readiness — Authority and Component Traceability

**Status:** proposed gate baseline

## Rule

Every implementation slice consumes an exact accepted authority chain. Local code/package/service names do not create new authority.

## Canonical implementation slices

| Slice | Primary responsibility | Mandatory upstream authority | Gate rule |
|---|---|---|---|
| `impl.contract-tooling@1` | machine-readable API/event/profile generation, lint, compatibility and assurance tooling | Phase 09/10 governance, Phase 11–15 manifests, Review & Assurance | may not redefine reviewed contracts |
| `impl.identity-bff@1` | browser confidential session boundary, authn/authz integration, TenantContext/current authority | Product/Security, Phase 09, Phase 11/13/15 | exact authentication/token profile must be closed before protected implementation |
| `impl.control-plane@1` | tenant placement, cell lifecycle/currentness, configuration and admission authority | System/Data, Phase 09, Phase 11–15 | generation/fence/currentness semantics are mandatory |
| `impl.cell-data-runtime@1` | transactional business truth, cell runtime, tenant-scoped state ports | System/Data, Phase 11–15 | one authoritative writer/current generation; no topology-derived identity |
| `impl.async-core@1` | outbox, transport adapter, inbox, idempotency, replay/quarantine/reconciliation | Phase 10, Phase 11, Phase 13–15 | at-least-once + durable responsibility + ambiguity rules mandatory |
| `impl.provider-integration@1` | provider adapter/callback/outbound calls | Product/domain, Phase 09/10, Phase 11–15 | provider-specific trust/auth profile must close before each effectful adapter |
| `impl.realtime@1` | BFF admission, subscription/fanout/resync | Phase 09/10, Phase 11–15 | ticket presentation/transport profile closes before browser realtime implementation |
| `impl.customer-telemetry@1` | durable acceptance and projections for customer monitoring observations | Product/domain/Data, Phase 10/11, Phase 12–15 | durable acceptance mechanism must be selected/conformed before path implementation |
| `impl.artifact@1` | artifact lifecycle, delivery, disclosure and protected processing | Product/Security, Phase 09, Phase 11–15 | Product-facing delivery/active-inline branches remain selector-gated |
| `impl.observability@1` | platform logs/metrics/traces/health/SLIs and diagnostic evidence | Phase 12 plus Phase 11/13–15 joins | telemetry never becomes business/security/recovery authority |
| `impl.platform-runtime@1` | runtime roles, environment mapping, workload identity, network/state-port boundaries | Phase 13 plus Security/Data | product/vendor choice must preserve logical profiles |
| `impl.release-supply-chain@1` | build, provenance, artifact promotion, deployment fencing and runtime verification | Phase 14 plus Phase 13/15 | untrusted source cannot enter privileged release context |
| `impl.operations-recovery@1` | incident/recovery/runbook/break-glass execution surfaces | Phase 15 plus Phase 11–14 | runbook/catalog/tool state never creates authority |

## Required per-slice record

Each slice SHALL materialize before canonical implementation begins:

```text
implementation_slice_id
accepted_product_scope_refs
accepted_requirement_refs
security_quality_refs
architecture_system_data_refs
api_contract_refs
event_contract_refs
reliability_profile_ids
observability_profile_ids
runtime_profile_ids
release_profile_ids
operations_owner/runbook_refs
data_authority
current_auth/tenant_boundary
failure/degradation behavior
recovery/compatibility behavior
applicable OPEN closure records
verification evidence plan
release blockers
```

Missing fields are blockers, not implementation TODOs.

## Authority non-substitution

```text
FRAMEWORK ROUTE != API CONTRACT
ORM MODEL != DATA AUTHORITY
BROKER TOPIC != EVENT CONTRACT
SERVICE NAME != DOMAIN OWNER
KUBERNETES/CONTAINER ID != PLATFORM IDENTITY
DEPLOYMENT DESIRED STATE != RUNNING-ARTIFACT PROOF
DASHBOARD HEALTH != RECOVERY AUTHORITY
RUNBOOK != AUTHORITY
```

## Product scope boundary

A prepared implementation slice may exist as architecture readiness without enabling a Product capability. Product-gated endpoint, webhook, artifact-delivery, privileged-query or future capability remains blocked until accepted Product/domain authority exists.
