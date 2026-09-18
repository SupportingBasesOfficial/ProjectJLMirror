# G4 Metrics — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@644b74d3277fd33bdfe705c135dba2a3b4ffde48`  
**Authorization ID:** `g4.metrics@1`

## Purpose

This is the separate implementation-authorization gate for the fourth AI-E2E product increment. It does not implement G4. It authorizes only the bounded user path required for an already-authorized tenant user to observe canonical metric definitions, current metric state and bounded metric history for an already-canonical Monitoring resource through protected BFF/API and browser UI.

G4 MUST reuse the accepted Wave 4 metric-definition, metric-current-state and metric-history substrate. It MUST NOT create a second metric store, reinterpret Zabbix `itemid` as platform identity, query provider history synchronously from the browser path, infer Health/Problem semantics, or broaden into G5+ capability.

## Authorization on acceptance

If this exact package is reviewed, accepted and separately merged:

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g4_metrics_only
```

Authorized slice:

```text
g4.metrics@1
```

Observable outcome: an authorized tenant user can open one canonical resource, list its canonical metric definitions, see accepted current state, and inspect a bounded historical window with truthful currentness/completeness semantics.

`merge_authorization = not_granted` remains separate.

## Dependency boundary

G4 depends on:

- canonical G1 protected identity/tenant/BFF implementation;
- canonical G2 Monitoring Source onboarding implementation;
- canonical G3 Resource Inventory implementation;
- accepted Wave 4 metric-definitions implementation;
- accepted Wave 4 metric-current-state implementation;
- accepted Wave 4 metric-history substrate;
- accepted Monitoring domain/API contracts.

The implementation MUST consume these authorities and MUST NOT modify or duplicate them without successor authorization.

## Existing substrate to reuse

Canonical existing substrate includes at minimum:

- `src/jlmirror_monitoring/**`;
- `sql/wave4/**`;
- accepted metric conformance tooling under `tools/wave4/**`;
- `implementation/wave-4-metric-definitions-authorization/**`;
- `implementation/wave-4-metric-current-state-authorization/**`;
- `implementation/wave-4-metric-history-authorization/**`;
- accepted Monitoring domain/API/Zabbix normalization contracts.

These shared paths are read-only under this authorization.

## Implementation path authority

Allowed prefixes:

- `apps/g4-metrics/`;
- `contracts/g4-metrics/`;
- `implementation/g4-metrics/`;
- `tests/g4/`;
- `tools/g4/`.

Allowed exact path:

- `.github/workflows/g4-metrics-runtime.yml`.

Required future implementation PR identity:

- branch prefix `impl/g4-metrics`;
- label `jlmirror-slice:g4-metrics`;
- claim file `implementation/g4-metrics/IMPLEMENTATION_CLAIM.json`;
- authorization ID `g4.metrics@1`;
- same repository;
- base equal to current default branch tip when trusted evidence is produced.

Path admission alone is insufficient. Executable G4 artifacts must be rejected if they introduce G5+ capability, parallel Monitoring persistence/domain truth, shared-substrate writes, provider-native authorization, direct provider passthrough, implicit health/problem interpretation, or production authority.

## Product behavior authorized

The later implementation may expose only the minimum G4 golden path required for:

1. current tenant admission through canonical G1;
2. current `monitoring.resource.read` and `monitoring.metric.read` authorization as required by the accepted API contract;
3. metric-definition list for one canonical `monitoring_resource_id`;
4. canonical current metric state for one or more returned metric definitions;
5. bounded history for one canonical `metric_definition_id` and finite `from/to` window;
6. active-generation current meaning by default;
7. visibly historical/non-current semantics for retained prior-generation evidence;
8. truthful `current|stale|incomplete|reconciliation_required|unavailable` current-state evidence;
9. truthful history completeness `complete|incomplete|gap_detected|reconciliation_required`;
10. bounded canonical value serialization for accepted value kinds;
11. bounded provider provenance only where the accepted detail surface permits it;
12. browser E2E proving allowed, forbidden, cross-tenant, stale/incomplete and history-window behavior;
13. exact runtime/container proof for G4-owned composition.

## Binding metric semantics

```text
METRIC_DEFINITION_ID = CANONICAL_PLATFORM_IDENTITY
ZABBIX_ITEMID != METRIC_DEFINITION_ID
METRIC_DEFINITION != METRIC_CURRENT_STATE
METRIC_CURRENT_STATE != METRIC_HISTORY
CURRENT_OBSERVATION_ID != METRIC_DEFINITION_ID
CURRENT_VALUE != HEALTH
MISSING_VALUE != ZERO
MISSING_VALUE != HEALTHY
STALE_OR_INCOMPLETE != CURRENT
HISTORICAL_GENERATION != CURRENT_OPERATIONAL_STATE
PROVIDER_EVENT_TIME != PLATFORM_AUTHORITY
HISTORY_COMPLETENESS_REQUIRES_EVIDENCE
CROSS_GENERATION_HISTORY_UNION = FORBIDDEN
```

G4 UI/BFF may project accepted metric truth; it may not reinterpret provider evidence into Health, Problems or Alerting.

## API/BFF authority

The protected browser path consumes the accepted Monitoring API contract.

Required stable action:

```text
monitoring.metric.read
```

Relevant canonical surfaces include:

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions
GET /api/v1/tenants/{tenant_id}/metric-definitions/{metric_definition_id}
GET /api/v1/tenants/{tenant_id}/metric-current-states
GET /api/v1/tenants/{tenant_id}/metric-current-states/{metric_definition_id}
GET /api/v1/tenants/{tenant_id}/metric-observations
```

The implementation MUST use the accepted endpoint/filter model. It must not invent a parallel aggregate endpoint that silently merges current and historical authority.

Every page/read re-establishes current tenant placement and authorization. Resource/metric ID possession, cursor possession, provider IDs and prior session admission never grant authority.

## Cache behavior

Accepted compatibility-sensitive cache classes remain binding:

- metric definitions list/detail: use the accepted Monitoring API cache profile;
- metric current state: `no_store`;
- metric observations/history: `no_store`;
- protected errors must not become shared/public cache entries.

G4 may be stricter only where the accepted contract explicitly permits it; it may never choose a more permissive cache class.

## Frontend authority

Implement only the bounded G4 metrics experience inside the protected resource detail journey:

- loading/empty/current/stale/incomplete/unavailable/forbidden states;
- metric definition name/value kind/unit;
- current value and evidence state;
- current observation timestamp/accepted timestamp where authorized;
- bounded historical chart/table for a finite explicit window;
- explicit history completeness state;
- visibly historical generation state where queried;
- no active HTML interpretation of untrusted text/log metric values.

The UI MUST NOT derive or display canonical `healthy|degraded|unhealthy` or Problem state from metric values under this gate.

## Explicit non-authority

This gate does not authorize:

- new canonical metric persistence;
- modification of accepted metric ingestion/current/history semantics;
- direct provider passthrough or browser/provider calls;
- unbounded or all-history queries;
- hidden cross-generation history union;
- Problem ingestion/read product surface;
- Health projection/read product surface;
- G5 Problem + Health;
- Monitoring→Alerting changes;
- Alert creation/policy;
- source replacement/cutover;
- canonical device taxonomy/classification;
- derived health thresholds or metric-to-problem rules;
- provider write-back;
- ITSM, Automation, AIOps, FinOps or Commercial behavior;
- concrete secret-manager/transport selection;
- production deployment/C3 numerics;
- raw unrestricted provider payload/value exposure;
- shared Monitoring/G1/G2/G3 substrate modification without successor authorization.

## Required proof before merge of the later implementation

- complete diff inside the canonical G4 allowlist;
- semantic-scope guard rejects G5+ and parallel Monitoring authority;
- current-authorization and cross-tenant tests;
- accepted Wave 4 metric definitions/current/history reuse proof;
- closed response-contract tests;
- active/historical generation truthfulness tests;
- current stale/incomplete/unavailable semantics tests;
- bounded history window/completeness/gap tests;
- value-kind and serialized-value bound tests;
- browser E2E from protected resource detail to current + history;
- runtime/container proof;
- exact-head CI green;
- trusted scope attestation/readiness evidence;
- panoramic/adversarial review with zero unresolved material findings;
- separate explicit owner merge authorization.

```text
G3_AUTHORIZED != G4_AUTHORIZED
G4_AUTHORIZED != G5_AUTHORIZED
METRICS != HEALTH
METRICS != PROBLEMS
IMPLEMENTED != PRODUCTION_READY
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
