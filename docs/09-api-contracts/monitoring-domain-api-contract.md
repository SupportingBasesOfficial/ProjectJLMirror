# Monitoring Domain API Contract — Wave 4 Entry

**Status:** proposed baseline  
**API major:** v1  
**Owner domain:** Monitoring  
**Companion domain contract:** `docs/03-domains/monitoring-domain-contract.md`  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001`, `AC-003`, `AC-006`, `AC-012`, `docs/09-api-contracts/endpoint-contract-template.md`, `docs/09-api-contracts/domain-api-surface-map.md`, `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md`

## Purpose

This document turns the Monitoring resource families previously reserved by `domain-api-surface-map.md` into exact Wave 4 endpoint/use-case contracts for the accepted Monitoring product scope.

It is an equivalent structured representation of the Phase 09 endpoint template: shared HTTP/security/tenant/pagination/error rules are declared once, then each operation declares its method/path/action/request/consistency/idempotency/success semantics. An implementation may split these operations into generated machine schemas, but it SHALL NOT invent materially different behavior from this contract.

This contract does not authorize implementation, does not close `OPEN-REL-030`, and does not select physical storage/transport/security products.

## API surface and browser boundary

All routes in this document are protected `machine-api` routes under:

```text
/api/v1/tenants/{tenant_id}/...
```

First-party browser traffic reaches these use cases through the accepted BFF boundary. Browser JavaScript does not receive long-lived API access/refresh credentials merely because these routes exist.

Accepted logical callers:

```text
human_browser_session through BFF
machine_api_principal
internal_service_principal under accepted workload identity
scheduled/system_process only through internal application use cases, not by forging public credentials
```

Rejected as tenant authority:

```text
provider payload tenant_id
provider tags/groups
physical cell/database identifiers
callback URL possession
raw provider/native IDs alone
```

## Shared HTTP message contract

Every operation inherits `http-message-framing-and-canonicalization.md` and `endpoint-contract-template.md` before authentication, placement, authorization, idempotency, cache or use-case execution.

Shared profile:

```text
HTTP message profile: platform canonical protected API
Method override: denied-by-default
Request trailers: cannot introduce/override auth, tenant, idempotency, conditional, CSRF/Origin or routing authority
Request target: canonical path/query profile
Query duplicate singleton values: reject
Structured request entity: canonical JSON for request bodies
Duplicate JSON members / canonical aliases: reject
Trusted proxy metadata: platform accepted profile only
Response headers: platform safe-response-header profile
```

Malformed/ambiguous framing, target/query interpretation, duplicate security-sensitive headers, structured-entity ambiguity or conflicting authority fails closed before protected logic.

## Shared tenant routing and authorization

For every route:

```text
Tenant requirement: required
Tenant source: canonical {tenant_id} path segment
Physical placement input from caller: prohibited
Owning authorization authority: current cell/Organization & Access authority through accepted TenantContext
```

Processing order for protected tenant work:

```text
canonical HTTP/path/query admission
 -> authenticate logical principal
 -> resolve current trusted tenant placement
 -> cell admission / placement-generation validation
 -> construct trusted TenantContext
 -> validate request/resource identifiers
 -> current owning authorization decision
 -> Monitoring use case
```

A request whose current membership/permission/tenant access or placement authority cannot be proven fails closed. Current authorization is re-established on every collection page/cursor continuation and every operation-resource read.

## Stable Monitoring policy actions

The API asks authorization for stable actions; roles/custom roles remain Organization & Access ownership.

| Action | Operations |
|---|---|
| `monitoring.source.read` | source list/detail |
| `monitoring.source.manage` | source create/update/replace-instance |
| `monitoring.resource.read` | resource list/detail |
| `monitoring.metric.read` | metric-definition and observation/history reads |
| `monitoring.problem.read` | problem list/detail |
| `monitoring.health.read` | health list/detail |
| `monitoring.sync.read` | sync-operation list/detail |

Future resource/group refinement may narrow these actions without changing route identity. No action implies a permanently tenant-global role assignment.

## Shared identifiers and representations

Opaque IDs are serialized as non-empty case-sensitive strings under the repository's opaque-ID representation profile. They are never parsed by clients for physical topology/provider meaning.

Timestamps are UTC RFC 3339 representations under the accepted Phase 09 time profile. Provider nanosecond precision is preserved where the canonical observation representation supports it; clients must not use timestamp lexical ordering as authority outside the documented collection sort.

Protected provider-native/external references are returned only where the operation's authorization/profile permits them; they never replace canonical IDs.

## Shared pagination and cursor rules

Collection endpoints are bounded and cursor-based when multiple pages are possible.

```text
Cursor meaning: server-issued continuation bound to tenant + operation + canonical filter/sort shape
Client modification: not trusted
Authorization on continuation: current authorization re-evaluated
Physical topology in cursor: prohibited as caller-visible authority
Default page size / maximum page size: finite implementation policy; production numeric remains OPEN where not yet evidenced
```

The first Monitoring implementation that requires protected cursors activates the concrete mechanism decision previously deferred by `OPEN-API-019`. Until a reviewed C2 mechanism is selected, cursor representation is not canonical implementation authority. Semantics above are fixed regardless of whether the chosen mechanism is integrity-protected opaque state or server-side continuation state.

A cursor is never bearer authorization. Losing cursor state after restore does not broaden access; clients restart the query from canonical filters.

## Shared cache contract

Protected Monitoring data is never `public_shared`.

Default read profile:

```text
Class: private_revalidate
Shared cache: prohibited
Authorization re-evaluation: required
Sensitive/protected variants: private/no-store as applicable
TTL: OPEN evidence-driven policy
```

Monitoring-source configuration detail and all mutation responses use `no_store`. BFF/browser policy may choose `no_store` more broadly.

`Vary`, CDN keys or cursor possession never substitute for authorization.

## Shared error contract

Operations inherit the canonical problem representation and may emit these stable classes:

```text
authentication.*
authorization.*
resource.not_found
validation.*
concurrency.precondition_required
concurrency.revision_mismatch
idempotency.*
rate_limit.*
dependency.*
monitoring.provider_profile_unsupported
monitoring.source_instance_replacement_required
monitoring.source_visibility_degraded
monitoring.history_window_required
monitoring.history_incomplete
monitoring.history_gap
monitoring.reconciliation_required
```

Errors do not expose provider credentials, provider raw exception text, cell/database topology, internal stack traces or cross-tenant existence.

A provider failure is not mapped to `404` for previously known canonical resources merely because the provider currently omits them.

## Shared request limits

Every request/response/query is finite. Exact byte/page/time/query thresholds may remain C3/OPEN until evidence, but implementation cannot interpret `OPEN` as unlimited.

All collection queries use an accepted bounded complexity class. Historical observation queries additionally require a mandatory bounded time window and one canonical metric definition.

---

# Operation catalog

## `monitoring.listSources` — List Monitoring Sources

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/monitoring-sources
Action: monitoring.source.read
Consistency: committed_authoritative configuration + projected operational evidence
Cache: no_store
Default sort: (monitoring_source_id ASC)
```

Allowed filters:

```text
provider_profile        singleton
operational_evidence_state singleton
cursor                  singleton
page_size               singleton bounded policy
```

Response `200`:

```json
{
  "items": ["MonitoringSourceSummary"],
  "next_cursor": "opaque-or-null"
}
```

`MonitoringSourceSummary` exposes canonical source ID, display name, provider profile, source-instance generation, configuration revision, operational evidence state and safe last-sync timestamps. It does not expose credential secret material.

## `monitoring.createSource` — Create Monitoring Source

```text
Method: POST
Path: /api/v1/tenants/{tenant_id}/monitoring-sources
Action: monitoring.source.manage
Content-Type: application/json
Audit class: privileged
Idempotency: required
Cache: no_store
Consistency: committed_authoritative configuration
```

Headers:

```text
Idempotency-Key: strict singleton, required
X-Correlation-Id: accepted platform profile
```

Canonical body:

```json
{
  "provider_profile": "zabbix",
  "display_name": "bounded non-empty string",
  "provider_configuration": {
    "base_url": "provider-profile validated HTTPS URL"
  },
  "credential_binding_ref": "opaque secret-binding reference",
  "configured_provider_scope": {
    "host_group_refs": ["bounded provider-scope reference"]
  }
}
```

Rules:

- `provider_profile` is a supported provider-profile registry key; initial accepted profile is `zabbix`; unknown/unaccepted profiles are rejected.
- raw API token/credential bytes are **not** part of this Monitoring body. `credential_binding_ref` points to the accepted secret/credential-binding mechanism selected outside this domain contract.
- provider configuration is validated syntactically/semantically and against outbound destination policy before it can be activated; DNS/egress policy is also revalidated at use time by the adapter.
- unknown body fields are rejected.
- source creation commits local configuration/audit/durable sync responsibility; it does not hold the local transaction open while calling Zabbix.

Idempotency scope/fingerprint:

```text
scope = tenant_id + monitoring.createSource + Idempotency-Key
fingerprint = canonical provider_profile + display_name + provider_configuration + credential_binding_ref + configured_provider_scope
```

Success `201 Created` returns `MonitoringSourceDetail` and a `Location` for the source. If an initial sync operation has already been durably created, its canonical reference is included as metadata; the source creation result is not undone if later provider validation/synchronization fails.

Same-key/same-fingerprint replay returns the completed source result without creating a second logical source. Same-key/different-fingerprint returns `409 idempotency.key_reused`.

## `monitoring.getSource` — Get Monitoring Source

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
Action: monitoring.source.read
Consistency: committed_authoritative configuration + projected operational evidence
Cache: no_store
```

Response `200` `MonitoringSourceDetail` includes:

```text
monitoring_source_id
display_name
provider_profile
source_instance_generation
configuration_revision
safe provider endpoint/configuration metadata
configured_provider_scope
credential_binding_ref metadata/reference only where policy permits; never secret bytes
operational_evidence_state
last_successful_sync_at
last_attempt_at
last_sync_operation_id
created_at
updated_at
```

Existence concealment follows current tenant/resource authorization policy; a known cross-tenant source ID never leaks another tenant's configuration.

## `monitoring.updateSource` — Ordinary Monitoring Source Edit

```text
Method: PATCH
Path: /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
Action: monitoring.source.manage
Audit class: privileged
If-Match: required
Idempotency-Key: required
Cache: no_store
```

Allowed mutable fields:

```json
{
  "display_name": "optional bounded string",
  "credential_binding_ref": "optional opaque reference",
  "configured_provider_scope": "optional provider-profile object"
}
```

At least one allowed field is required. Unknown fields are rejected.

For the Zabbix profile, `base_url`/provider-instance-defining endpoint changes are forbidden here. Attempting to change such a field returns `409 monitoring.source_instance_replacement_required` and creates no mutation/idempotency effect beyond the safe rejected-request evidence required by the platform.

`If-Match` compares the opaque source configuration revision. Missing -> `428`; mismatch -> `412`.

Idempotency fingerprint includes canonical body + source ID + expected revision. Successful update returns `200 MonitoringSourceDetail` with a new configuration revision. Credential rotation and host-group scope edits do not automatically advance Zabbix source-instance generation.

No provider network call is held inside the configuration transaction. Any required revalidation/synchronization becomes durable async responsibility after commit.

## `monitoring.replaceSourceInstance` — Replace Provider Instance

```text
Method: POST
Path: /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}:replace-instance
Action: monitoring.source.manage
Audit class: privileged
If-Match: required
Idempotency-Key: required
Cache: no_store
Consistency: committed authoritative generation change + accepted async synchronization
```

Canonical body:

```json
{
  "provider_configuration": {
    "base_url": "provider-profile validated HTTPS URL"
  },
  "credential_binding_ref": "opaque secret-binding reference",
  "configured_provider_scope": {
    "host_group_refs": ["bounded provider-scope reference"]
  }
}
```

The command atomically:

1. validates current tenant/source authorization and source revision;
2. fences prior provider-instance/poll writer authority;
3. advances source-instance generation exactly once;
4. installs successor configuration and configuration revision;
5. persists required audit evidence;
6. creates one durable successor synchronization/reconciliation responsibility.

It does not infer cross-generation canonical resource equivalence from matching provider IDs.

Response `202 Accepted` returns `MonitoringSyncOperation` (or the common Operation representation specialized with `operation_type=monitoring_source_instance_replacement`) and links the updated source. The operation URL is not bearer authority.

Idempotency protects response loss/concurrent retry. Same key/fingerprint observes the same logical replacement; different fingerprint conflicts. A provider validation failure after the local generation command does not silently roll the source back to the retired generation; the operation/source exposes unavailable/reconciliation evidence and an explicit later governed recovery path.

---

# Inventory and current-state reads

## `monitoring.listResources` — List Monitoring Resources

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/monitoring-resources
Action: monitoring.resource.read
Consistency: committed local projection with explicit evidence freshness
Cache: private_revalidate
Default sort: (monitoring_resource_id ASC)
```

Allowed filters:

```text
monitoring_source_id   singleton
presence_state         singleton present|removed
resource_kind          singleton
health_class           singleton (join/projection filter under bounded plan)
evidence_state         singleton
cursor                  singleton
page_size               singleton bounded policy
```

Response resources include canonical identity, source ID/generation, display name, resource kind, presence state, last-observed/confirmed timestamps and a safe health summary/reference where available.

A stale/incomplete source does not cause missing resources to disappear from this collection. `presence_state=removed` means Monitoring already accepted authoritative negative evidence.

## `monitoring.getResource` — Get Monitoring Resource

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/monitoring-resources/{monitoring_resource_id}
Action: monitoring.resource.read
Consistency: committed local projection with evidence freshness
Cache: private_revalidate
```

Response `200 MonitoringResourceDetail`. External provider references are bounded protected metadata and are included only when the action/profile permits them. Current placement/provider endpoint topology is never exposed as resource identity.

---

# Metric-definition and historical-observation reads

## `monitoring.listMetricDefinitions` — List Metric Definitions

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/metric-definitions
Action: monitoring.metric.read
Consistency: committed local projection
Cache: private_revalidate
Default sort: (metric_definition_id ASC)
```

Required filter:

```text
monitoring_resource_id = strict singleton
```

Optional:

```text
definition_state = active|retired
cursor
page_size
```

Each item returns canonical definition ID, canonical resource/source identity, name, value kind, unit, definition state and safe bounded external-reference metadata when policy permits.

## `monitoring.getMetricDefinition` — Get Metric Definition

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/metric-definitions/{metric_definition_id}
Action: monitoring.metric.read
Consistency: committed local projection
Cache: private_revalidate
```

Response `200 MetricDefinitionDetail` using the canonical value-kind vocabulary from the Monitoring domain contract.

## `monitoring.listMetricObservations` — Query Bounded Metric History

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/metric-observations
Action: monitoring.metric.read
Consistency: historical_window
Cache: private_revalidate
Default sort: (observed_at ASC, observation_id ASC)
```

Required singleton query fields:

```text
metric_definition_id
from     inclusive UTC timestamp
to       exclusive UTC timestamp
```

Optional singleton fields:

```text
cursor
page_size
```

Rules:

- exactly one canonical metric definition is queried per request in this initial contract; a future bounded multi-series query is a separately reviewed complexity/capacity extension, not an unbounded repeated parameter default;
- `from < to` and the requested duration must satisfy the accepted bounded historical-query policy;
- confidential/restricted ad-hoc filters are not placed in query strings;
- the endpoint never falls back to an unbounded “all history” query when `from`/`to` is absent;
- every page re-establishes current tenant/resource authorization;
- the cursor is bound to metric ID, time window, deterministic order and query profile;
- provider event time is data, not authorization or current-state authority.

Response `200`:

```json
{
  "metric_definition_id": "opaque",
  "window": {"from": "...", "to": "..."},
  "completeness": {
    "state": "complete|incomplete|gap_detected|reconciliation_required",
    "covered_through": "timestamp-or-null",
    "gap_refs": ["opaque bounded ref"]
  },
  "items": ["MetricObservation"],
  "next_cursor": "opaque-or-null"
}
```

`complete` is allowed only under the accepted provider lateness/retention/reconciliation contract. If JLMIRROR cannot prove complete coverage, it returns the known observations with explicit non-complete state where policy permits, or `409 monitoring.history_incomplete` when the caller explicitly requires complete evidence through a future accepted query profile. It never silently fabricates continuity.

Each `MetricObservation` contains canonical observation/metric/resource/source IDs, source-instance generation, observed/accepted time, `value_kind` and tagged canonical `value`. Provider-native history IDs remain bounded external evidence, not primary API identity.

---

# Problem reads

## `monitoring.listProblems` — List Problems

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/problems
Action: monitoring.problem.read
Consistency: committed current/historical local projection with source evidence status
Cache: private_revalidate
Default sort: (opened_at DESC, problem_id ASC)
```

Allowed singleton filters:

```text
monitoring_source_id
monitoring_resource_id
problem_state = active|resolved
severity_class = unknown|informational|warning|degraded|critical
opened_from
opened_to
cursor
page_size
```

A missing provider row does not make an active problem resolved. `resolved` means accepted resolution/negative evidence already passed the provider/domain contract.

Response items expose canonical problem/resource/source IDs, state, canonical severity class, summary, open/resolve timestamps, last-confirmed time and evidence state. Provider acknowledgement/tags may appear only as bounded non-authoritative metadata when permitted and never as JLMIRROR Alerting/ITSM acknowledgement.

## `monitoring.getProblem` — Get Problem

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/problems/{problem_id}
Action: monitoring.problem.read
Consistency: committed local projection
Cache: private_revalidate
```

Response `200 ProblemDetail`. The response may link related resource and health projection. It does not embed mutable Alerting or ITSM lifecycle state as Monitoring ownership.

---

# Health reads

## `monitoring.listHealthProjections` — List Resource Health

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/health-projections
Action: monitoring.health.read
Consistency: current local projection + explicit evidence freshness
Cache: private_revalidate
Default sort: (monitoring_resource_id ASC)
```

Allowed singleton filters:

```text
monitoring_source_id
health_class = unknown|healthy|degraded|unhealthy
evidence_state = current|stale|incomplete|reconciliation_required|unavailable
cursor
page_size
```

Response items include resource/source identity, canonical health class, evidence state, projection revision, last-change/evidence times and bounded problem/reason references.

A last-known `healthy` class with `evidence_state=stale` is not a claim of fresh health. Client presentation must preserve the evidence state.

## `monitoring.getHealthProjection` — Get Resource Health

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/health-projections/{monitoring_resource_id}
Action: monitoring.health.read
Consistency: current local projection + evidence freshness
Cache: private_revalidate
```

The resource ID is the projection identity for this initial contract. Response `200 HealthProjectionDetail` follows the domain health derivation rules and does not expose provider severity as the health enum.

---

# Synchronization operation reads

## `monitoring.listSyncOperations` — List Monitoring Synchronization Operations

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/monitoring-sync-operations
Action: monitoring.sync.read
Consistency: committed_authoritative operation state
Cache: no_store
Default sort: (created_at DESC, monitoring_sync_operation_id ASC)
```

Allowed singleton filters:

```text
monitoring_source_id
source_instance_generation
operation_state (common operation vocabulary)
trigger_class
cursor
page_size
```

Response exposes safe progress/checkpoint/failure/degradation/correlation metadata. It never returns provider credential secrets or physical worker/queue/database routing.

## `monitoring.getSyncOperation` — Get Monitoring Synchronization Operation

```text
Method: GET
Path: /api/v1/tenants/{tenant_id}/monitoring-sync-operations/{monitoring_sync_operation_id}
Action: monitoring.sync.read
Consistency: committed_authoritative operation state
Cache: no_store
```

Each read re-establishes current authorization. The operation may expose links to the source and safe reconciliation/gap evidence.

This contract deliberately does **not** add a tenant-facing `:retry`, `:resume` or manual `:sync` command without separate accepted Product authority. Scheduled sync, webhook-hint acceleration, configuration-triggered sync and recovery/reconciliation are owned by accepted internal/provider/operations workflows. Future manual product commands require explicit action/idempotency/abuse semantics rather than piggybacking on operation URL possession.

---

# Resource schemas

## `MonitoringSourceDetail`

Logical JSON fields:

```text
monitoring_source_id: opaque string
display_name: bounded string
provider_profile: registry key
source_instance_generation: non-negative integer/generation
configuration_revision: opaque revision
provider_configuration: safe profile-specific configuration metadata
configured_provider_scope: safe bounded profile-specific scope
credential_binding_ref: optional opaque reference metadata under policy, never secret bytes
operational_evidence_state: current|stale|incomplete|reconciliation_required|unavailable
last_successful_sync_at: timestamp|null
last_attempt_at: timestamp|null
last_sync_operation_id: opaque|null
created_at: timestamp
updated_at: timestamp
```

## `MonitoringResourceDetail`

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
display_name
resource_kind
presence_state: present|removed
external_references: bounded protected list
last_observed_at
last_confirmed_present_at
created_at
updated_at
```

## `MetricDefinitionDetail`

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
name
value_kind: number|integer|boolean|string|text|log
unit: bounded string|null
definition_state: active|retired
external_references: bounded protected list
created_at
updated_at
```

## `MetricObservation`

```text
observation_id
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
observed_at
accepted_at
value_kind
value (tag-compatible with value_kind)
```

Observation values are immutable once durably accepted. Output encoding/escaping never permits metric/log text to become executable browser content.

## `ProblemDetail`

```text
problem_id
monitoring_source_id
source_instance_generation
monitoring_resource_ids: bounded list
summary: bounded untrusted-provider-derived text
problem_state: active|resolved
severity_class: unknown|informational|warning|degraded|critical
opened_at
resolved_at|null
last_confirmed_at
operational_evidence_state
external_references: bounded protected list
provider_metadata: bounded optional map/profile, non-authoritative
```

## `HealthProjectionDetail`

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
health_class: unknown|healthy|degraded|unhealthy
evidence_state: current|stale|incomplete|reconciliation_required|unavailable
projection_revision
last_changed_at
last_evidence_at
problem_refs: bounded list
```

## `MonitoringSyncOperation`

Uses the accepted common long-running-operation representation plus:

```text
monitoring_sync_operation_id
monitoring_source_id
source_instance_generation
trigger_class
last_safe_checkpoint/reference (safe opaque metadata)
provider/dependency failure class (safe enum, no raw exception)
correlation_id
```

## Historical completeness representation

The historical query completeness state is a query/evidence result, not a fake observation:

```text
complete
incomplete
gap_detected
reconciliation_required
```

`complete` means the accepted provider lateness/retention/reconciliation contract proves the requested interval under current authoritative evidence. `gap_detected` means a known interval cannot be proven/recovered. `incomplete` means coverage is not yet complete but may still converge. `reconciliation_required` means recovery/provider uncertainty blocks a completion claim.

# Transaction/effect/idempotency summary

| Operation class | Local transaction | Idempotency | External provider call inside tx | Audit |
|---|---|---|---|---|
| source create | authoritative source + audit + durable sync obligation | required | prohibited | privileged |
| ordinary source edit | source revision + audit + durable revalidation/sync obligation as required | required | prohibited | privileged |
| replace instance | fence/generation/config/audit + one durable successor operation | required | prohibited | privileged |
| reads | none beyond read transaction/snapshot | intrinsic read | no synchronous provider authority required | normal access telemetry |

Provider reads occur through the adapter asynchronously/currently according to synchronization responsibility. Public API reads serve accepted local authoritative/projection state and explicitly represent staleness/incompleteness; they do not turn an interactive API request into an unbounded provider passthrough.

# Observability and SLI bindings

Every operation propagates the accepted correlation context. Safe telemetry records at least:

```text
operation_id / route profile
tenant-safe attribution (never high-cardinality tenant label where forbidden by Phase 12 profile)
authorization outcome class
source/resource class when permitted
latency/status/error class
sync operation correlation for mutations that schedule work
history query window/page/cost class without raw values
```

Provider payloads, metric/log values, tags, API tokens and raw external exceptions are excluded from normal signal fields unless an explicit safe bounded diagnostic profile allows a redacted value.

Required Monitoring operational evidence includes source sync age/evidence state, provider dependency state, backlog/reconciliation/gap state, historical projector lag, current-state transition failures and per-tenant fairness/saturation signals under accepted Phase 12/11 profiles.

# Recovery / relocation behavior

API success and reads never bypass the accepted recovery quarantine/placement model.

After PITR/restore/relocation:

- source/config generations and optimistic revisions are reconciled before source mutations resume;
- old placement/poll authority cannot mutate current state;
- missing observation/history/checkpoint state is uncertainty, not proof of absence;
- historical completeness may downgrade to reconciliation-required/incomplete/gap until continuity is proven;
- source/resource/problem/health reads expose current evidence state rather than silently claiming freshness;
- idempotency/replacement operation outcome survives/reconciles across `(R,F]` before the same logical effect can execute again.

# Dashboard composition contract

The API intentionally provides no mutable `/monitoring-dashboards` aggregate in this initial domain contract.

A Monitoring dashboard may compose:

```text
monitoring-resources
health-projections
problems
metric-definitions
metric-observations
monitoring-sync-operations
```

through BFF/read composition. If performance/cross-domain needs later require persistent dashboard/NOC projections, those are accepted under Reporting & Experience and cannot gain mutation ownership over Monitoring state.

# Compatibility and versioning

A change is compatibility/security-sensitive when it changes:

- tenant/action/authorization scope;
- source-instance replacement semantics;
- canonical resource/metric/observation/problem identity;
- negative-evidence/removal/resolution rules;
- health/severity/evidence-state meaning;
- historical completeness/gap meaning;
- cursor binding/current-authorization behavior;
- source mutation idempotency or optimistic-concurrency rules;
- provider metadata authority status;
- recovery/relocation fencing;
- which domain owns dashboard/alert/incident state.

Such a change cannot be shipped as an invisible implementation detail merely because JSON fields remain parseable.

# Contract tests / falsification matrix

The first implementation must prove at least:

1. Cross-tenant known-ID requests fail without leaking Tenant B existence/data for every resource family.
2. Source create retry with same idempotency key creates one source; fingerprint mismatch conflicts.
3. Concurrent source PATCH uses `If-Match`; stale revision cannot overwrite current configuration.
4. Zabbix base URL mutation through ordinary PATCH is rejected and cannot silently reuse source generation.
5. Replace-instance retry creates one successor generation/operation; stale concurrent replacement loses.
6. Raw provider/API credentials never appear in source responses/logs/traces/errors/events/audit snapshots.
7. Provider outage does not turn known resources/problems into 404/removed/resolved state.
8. Resource/metric/problem collections expose only accepted `removed`/`retired`/`resolved` states backed by domain negative evidence.
9. Historical query without metric/from/to fails; oversized/unbounded window never falls back to all history.
10. Every historical page reauthorizes current tenant/resource scope.
11. Historical incomplete/gap/reconciliation state is explicit and cannot be hidden by pagination.
12. Repeated same current observation under a later poll does not emit duplicate semantic transition.
13. Provider clock rollback does not freeze genuinely newer fenced current state.
14. Zabbix severity maps only to canonical severity; ack/tags remain non-authoritative metadata.
15. Health `evidence_state` remains visible when last-known health is stale/incomplete/unavailable.
16. Sync operation ID cannot be used as bearer authority and cannot leak worker/queue/cell topology.
17. One tenant's high-cardinality/history/sync pressure is bounded and does not starve unrelated tenants.
18. Recovery/relocation invalidates stale placement/poll/cursor/idempotency assumptions rather than reopening authority.

# OPEN decisions and blockers preserved

This API contract closes endpoint/use-case semantics for the accepted Monitoring core but preserves evidence/mechanism gates:

- `OPEN-REL-030` must be selected/conformed before `impl.customer-telemetry@1` canonical ingestion/projection implementation;
- concrete protected cursor mechanism must be selected/reviewed before paginated implementation depends on it;
- credential binding/secret-manager/KMS mechanism remains C2;
- provider timeout/retry/page/history/reconciliation numerics remain evidence-driven;
- Tier 2 telemetry storage remains candidate/evidence-gated;
- production page/window/retention/capacity/SLO numbers remain C3.

No `DELETE`, tenant-facing manual `:sync/:retry/:resume`, provider write-back, alert acknowledgement, incident creation or dashboard mutation endpoint is implicitly authorized by this contract. Those behaviors require their own accepted Product/domain contracts.
