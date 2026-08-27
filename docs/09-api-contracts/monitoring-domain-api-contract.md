# Monitoring Domain API Contract — Wave 4 Entry

**Status:** proposed baseline  
**API major:** v1  
**Owner:** Monitoring  
**Companion:** `docs/03-domains/monitoring-domain-contract.md`  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001`, `AC-003`, `AC-006`, `AC-012`, Phase 09 endpoint/collection contracts, Zabbix provider/normalization profiles

## Purpose

This document turns the Monitoring families reserved by `domain-api-surface-map.md` into exact endpoint/use-case contracts for the accepted core Monitoring product outcome. It uses the Phase 09 endpoint template by inheritance plus operation-specific declarations below.

It does not authorize implementation, close `OPEN-REL-030`, select physical storage/transport/security products, or create new Product capabilities.

## Surface and callers

Protected machine API namespace:

```text
/api/v1/tenants/{tenant_id}/...
```

First-party browser traffic reaches these use cases through the accepted BFF. Browser JS does not receive long-lived machine credentials.

Accepted logical caller classes:

```text
human browser principal through BFF
machine API principal
internal service principal under accepted workload identity
```

Provider payloads/tags/groups, callback URL possession and physical topology never become tenant authority.

## Shared HTTP/canonicalization profile

Every operation inherits `http-message-framing-and-canonicalization.md`, `endpoint-contract-template.md` and `collections-filtering-pagination-and-bulk.md`.

```text
method override              denied-by-default
security-sensitive trailers cannot introduce/override authority
request target/query         one canonical decode/multiplicity meaning
duplicate singleton query    reject
structured request body      canonical JSON
duplicate/alias JSON members reject
response headers             platform safe serialization profile
```

Ambiguous framing/target/query/header/entity semantics fail closed before protected logic or idempotency admission.

## Tenant/current authorization order

Every route is tenant-scoped from the canonical path. Caller-supplied physical placement is prohibited.

```text
canonical HTTP admission
 -> authenticate principal
 -> current trusted placement resolution/cell admission
 -> trusted TenantContext
 -> request/resource validation
 -> current owning authorization
 -> Monitoring use case
```

Every page/continuation and operation read re-establishes current authorization/placement. Hiding UI controls or holding a prior continuation never grants authority.

## Stable policy actions

```text
monitoring.source.read
monitoring.source.manage
monitoring.resource.read
monitoring.metric.read
monitoring.problem.read
monitoring.health.read
monitoring.sync.read
```

Roles/custom roles remain Organization & Access ownership; this contract does not hard-code role names.

## IDs, time and external references

Canonical IDs are opaque non-empty strings. Clients cannot parse provider/cell/topology meaning from them.

Timestamps use the accepted UTC Phase 09 time representation. Provider event time remains data, not authorization/current-ordering authority.

Provider-native IDs/metadata are optional bounded protected external evidence and never replace canonical IDs.

## Pagination — URL-safe non-sensitive cursor profile

Monitoring collection cursors use the accepted Phase 09 **`url_safe_non_sensitive_handle`** class.

This contract deliberately does **not** activate the C5 protected-continuation mechanism in `OPEN-API-019`.

Required cursor properties:

```text
opaque to client
binds endpoint/API major + tenant logical scope + canonical filters + sort + deterministic last key
contains/reveals no credential, protected search value, raw provider key, physical topology or confidential payload
possession grants no read/continuation authority
current authorization re-evaluated on every page
URL/history persistence acceptable under this non-sensitive-handle classification
normal logs may record only according to Phase 12 safe URL/query policy
```

The implementation may use a server-side random handle or a self-contained opaque encoding only if the **exposed token itself** remains non-sensitive and cannot be used as bearer authority. If a future endpoint needs protected cursor payload/token semantics, that separately activates the owning `OPEN-API-019` Product/governance path; this Monitoring contract cannot silently reclassify it.

Collection shape:

```json
{"items": [], "next_cursor": "opaque-or-null"}
```

All collections have deterministic stable ordering, finite default/max page size and explicit live/historical traversal semantics. Production page numerics remain evidence-driven; `OPEN` never means unlimited.

## Cache

Protected Monitoring data is never `public_shared`.

Read default:

```text
private_revalidate
shared cache prohibited
current authorization before reuse/page
TTL evidence-driven/OPEN where not fixed
```

Monitoring-source detail and mutation responses, and sync-operation detail, use `no_store`. BFF policy may be stricter.

## Errors

Stable classes include:

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

No raw provider exception/credential/internal topology is exposed. Provider omission/outage cannot turn a previously known resource into 404/removed/resolved by itself.

## Mutation idempotency + precondition ordering

Source mutations use current authorization, canonical request semantics, required `Idempotency-Key` and (for existing sources) `If-Match`.

Important response-loss rule:

- for a **new idempotency key**, the one logical executor validates the supplied current resource precondition before committing the mutation;
- for an **existing same-key/same-fingerprint claim**, the server observes the recorded/in-progress logical operation before treating the now-advanced resource revision as a fresh conflicting request;
- therefore retry after a successful-but-response-lost mutation can recover the original result rather than incorrectly returning `412` solely because that same mutation advanced the revision;
- same key with a different canonical fingerprint returns `409 idempotency.key_reused`;
- a different idempotency key is a new command and must satisfy the current `If-Match` revision.

Current authentication/authorization is still re-evaluated on replay; idempotency never freezes permission.

## Base URL/provider-endpoint safety

For the Zabbix profile, submitted base URL configuration uses a canonical HTTPS URI profile:

```text
scheme          https
host            required; validated under outbound SSRF/egress policy
port            optional allowed profile
path            allowed/bounded for reverse-proxy deployments
userinfo        prohibited
query           prohibited
fragment        prohibited
embedded secret prohibited
```

A syntactically accepted URL is revalidated against destination/DNS/redirect/egress policy at each provider use as required by the provider contract. URL validation never turns DNS/network location into tenant authority.

---

# Source operations

## `monitoring.listSources`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sources
action        monitoring.source.read
consistency   committed configuration + projected operational evidence
cache         no_store
pagination    live traversal, sort monitoring_source_id ASC
```

Filters: `provider_profile`, `operational_evidence_state`, `cursor`, `limit` — all singleton/canonically decoded.

`200` returns bounded `MonitoringSourceSummary[]` + `next_cursor`.

## `monitoring.createSource`

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources
action          monitoring.source.manage
audit           privileged
Idempotency-Key required strict singleton
cache            no_store
```

Canonical body:

```json
{
  "provider_profile": "zabbix",
  "display_name": "bounded non-empty string",
  "provider_configuration": {"base_url": "canonical HTTPS URL"},
  "credential_binding_ref": "opaque secret-binding reference",
  "configured_provider_scope": {"host_group_refs": ["bounded reference"]}
}
```

Rules:

- initial accepted provider profile is `zabbix`; unknown/unaccepted profiles reject;
- no raw API token/secret bytes in the Monitoring body;
- unknown body members reject;
- URL/profile/scope semantics validate before commit; provider network call is not held inside the local transaction;
- create persists source + first source-instance generation + revision + audit + durable validation/sync responsibility when ingestion is activated.

Idempotency scope:

```text
tenant_id + monitoring.createSource + key
```

Fingerprint covers canonical body. `201 Created` returns `MonitoringSourceDetail` + `Location`; repeated same key/fingerprint observes same logical source.

## `monitoring.getSource`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
action       monitoring.source.read
consistency  committed configuration + projected evidence
cache        no_store
```

Returns canonical ID, display/profile, source-instance generation, revision, safe endpoint/scope metadata, optional credential-binding reference metadata under policy, evidence state and sync timestamps/references. Never returns credential secret bytes.

## `monitoring.updateSource`

```text
PATCH /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
action          monitoring.source.manage
audit           privileged
If-Match         required
Idempotency-Key  required
cache            no_store
```

Allowed fields only:

```json
{
  "display_name": "optional",
  "credential_binding_ref": "optional",
  "configured_provider_scope": "optional profile-specific object"
}
```

At least one field required; unknown fields reject.

For Zabbix, base URL/provider-instance endpoint change here returns `409 monitoring.source_instance_replacement_required` without mutation. Credential rotation/scope edit remain same source-instance generation.

New-key executor validates `If-Match`; missing -> `428`, mismatch -> `412`. Idempotent replay follows the shared response-loss rule above.

`200` returns updated source/new revision. Provider revalidation/sync occurs through durable async responsibility after local commit.

## `monitoring.replaceSourceInstance`

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}:replace-instance
action          monitoring.source.manage
audit           privileged
If-Match         required
Idempotency-Key  required
cache            no_store
consistency      committed generation change + accepted async sync responsibility
```

Body contains successor provider configuration, credential binding and configured scope using the same canonical profiles as creation.

One logical command:

1. validates current auth/revision;
2. fences prior provider-instance/poll writer authority;
3. advances source-instance generation exactly once;
4. installs successor config/revision;
5. persists audit;
6. creates one durable successor sync/reconciliation responsibility;
7. never merges old/new provider-native mappings merely because IDs/names match.

`202 Accepted` returns `MonitoringSyncOperation` / common Operation specialization and updated-source link. Same idempotency key/fingerprint observes the same replacement.

Failure/ambiguity of later provider validation does not silently roll back to the retired generation; evidence becomes unavailable/reconciliation-required until governed recovery.

---

# Resource/current-state operations

## `monitoring.listResources`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources
action        monitoring.resource.read
consistency   committed local projection + evidence freshness
cache         private_revalidate
pagination    live traversal, monitoring_resource_id ASC
```

Filters (singleton): source ID, `presence_state=present|removed`, resource kind, health class/evidence state, cursor, limit.

Missing provider rows under stale/incomplete/visibility-degraded evidence do not disappear. `removed` means authoritative negative evidence already committed.

## `monitoring.getResource`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources/{monitoring_resource_id}
action monitoring.resource.read
cache  private_revalidate
```

Returns canonical identity/presence/source generation/last-observed evidence and bounded protected external references where authorized. Provider/cell identity never replaces resource identity.

---

# Metric definitions + current metric state

## `monitoring.listMetricDefinitions`

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions
action        monitoring.metric.read
consistency   committed definition + current-metric projection
cache         private_revalidate
pagination    live traversal, metric_definition_id ASC
```

Required singleton filter: `monitoring_resource_id`.

Optional singleton: `definition_state=active|retired`, cursor, limit.

Each item includes canonical definition fields **and its `current_state` projection**:

```json
{
  "metric_definition_id": "opaque",
  "monitoring_resource_id": "opaque",
  "name": "...",
  "value_kind": "number|integer|boolean|string|text|log",
  "unit": "nullable",
  "definition_state": "active|retired",
  "current_state": {
    "current_observation_id": "opaque-or-null",
    "observed_at": "timestamp-or-null",
    "accepted_at": "timestamp-or-null",
    "value_kind": "same canonical kind",
    "value": "tag-compatible value or null",
    "evidence_state": "current|stale|incomplete|reconciliation_required|unavailable",
    "projection_revision": "opaque",
    "last_changed_at": "timestamp-or-null"
  }
}
```

This is the efficient current-state surface required by `FR-MON-003`; clients do not need to query historical Tier 2 for “latest”. A last-known value with non-current evidence cannot be presented as freshly proven current state.

## `monitoring.getMetricDefinition`

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions/{metric_definition_id}
action monitoring.metric.read
cache  private_revalidate
```

Returns `MetricDefinitionDetail` + the same `current_state` projection and bounded external references where authorized.

---

# Historical metric observations

## `monitoring.listMetricObservations`

```text
GET /api/v1/tenants/{tenant_id}/metric-observations
action        monitoring.metric.read
consistency   historical_window
cache         private_revalidate
pagination    historical window; sort (observed_at ASC, observation_id ASC)
```

Required singleton query:

```text
metric_definition_id
from  inclusive UTC timestamp
to    exclusive UTC timestamp
```

Optional singleton: cursor, limit.

Exactly one metric definition per request in this initial contract. Multi-series query is a future separately bounded complexity extension.

Rules:

- `from < to` and duration must satisfy finite accepted policy;
- no missing-window fallback to “all history”;
- cursor binds metric/window/sort and is the URL-safe non-sensitive handle class;
- every page reauthorizes current metric/resource scope;
- provider event time is historical data, not current authority.

`200`:

```json
{
  "metric_definition_id": "opaque",
  "window": {"from": "...", "to": "..."},
  "completeness": {
    "state": "complete|incomplete|gap_detected|reconciliation_required",
    "covered_through": "timestamp-or-null",
    "gap_refs": ["opaque bounded reference"]
  },
  "items": ["MetricObservation"],
  "next_cursor": "opaque-or-null"
}
```

`complete` requires accepted lateness/retention/reconciliation evidence, not merely successful query execution. Known/uncertain gaps remain explicit. The API never fabricates continuous history.

Observation fields: canonical observation/metric/resource/source IDs, source generation, observed/accepted times, canonical value kind/value. Immutable after acceptance.

---

# Problems

## `monitoring.listProblems`

```text
GET /api/v1/tenants/{tenant_id}/problems
action        monitoring.problem.read
cache         private_revalidate
pagination    live/historical local projection; (opened_at DESC, problem_id ASC)
```

Singleton filters: source ID, resource ID, `problem_state=active|resolved`, canonical severity, opened_from/to, cursor, limit.

Missing provider row is never implicit resolution. Items expose canonical state/severity, resource/source, timestamps and evidence state. Zabbix acknowledgement/tags may appear only as bounded non-authoritative provider metadata where policy permits.

## `monitoring.getProblem`

```text
GET /api/v1/tenants/{tenant_id}/problems/{problem_id}
action monitoring.problem.read
cache  private_revalidate
```

Returns `ProblemDetail`; may link resources/health. Monitoring does not own Alert/ITSM acknowledgement or incident state.

---

# Health

## `monitoring.listHealthProjections`

```text
GET /api/v1/tenants/{tenant_id}/health-projections
action        monitoring.health.read
cache         private_revalidate
pagination    live projection; monitoring_resource_id ASC
```

Filters: source ID, `health_class=unknown|healthy|degraded|unhealthy`, evidence state, cursor, limit.

Items expose canonical health + evidence state + revision/times/bounded problem references. A last-known `healthy` with stale evidence is visibly stale.

## `monitoring.getHealthProjection`

```text
GET /api/v1/tenants/{tenant_id}/health-projections/{monitoring_resource_id}
action monitoring.health.read
cache  private_revalidate
```

Resource ID is projection identity. Provider severity is not serialized as the health enum.

---

# Synchronization operations

## `monitoring.listSyncOperations`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sync-operations
action        monitoring.sync.read
consistency   committed operation authority
cache         no_store
pagination    created_at DESC, operation_id ASC
```

Filters: source ID, source generation, common operation state, trigger class, cursor, limit.

Returns safe progress/checkpoint/failure/degradation/correlation metadata without credentials or physical worker/queue/database topology.

## `monitoring.getSyncOperation`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sync-operations/{monitoring_sync_operation_id}
action monitoring.sync.read
cache  no_store
```

Current authorization is re-established. Operation ID is never bearer authority.

No tenant-facing manual `:sync/:retry/:resume` command is invented here. Schedule, webhook hint, configuration and recovery workflows own execution until Product explicitly authorizes a manual command contract.

---

# Canonical response types

## Monitoring source

```text
monitoring_source_id
display_name
provider_profile
source_instance_generation
configuration_revision
safe provider configuration/scope metadata
credential_binding_ref metadata only where authorized
evidence_state
last_successful_sync_at
last_attempt_at
last_sync_operation_id
created_at / updated_at
```

## Monitoring resource

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
display_name
resource_kind
presence_state present|removed
bounded external_references
last_observed_at
last_confirmed_present_at
created_at / updated_at
```

## Metric definition/current state

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
name
value_kind
unit
definition_state active|retired
bounded external_references
current_state { current_observation_id, observed_at, accepted_at, value_kind, value, evidence_state, projection_revision, last_changed_at }
```

## Metric observation

```text
observation_id
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
observed_at
accepted_at
value_kind
value
```

Untrusted text/log values are data and cannot become active browser content.

## Problem

```text
problem_id
monitoring_source_id
source_instance_generation
monitoring_resource_ids (bounded)
summary
problem_state active|resolved
severity_class unknown|informational|warning|degraded|critical
opened_at / resolved_at / last_confirmed_at
evidence_state
bounded external_references/provider_metadata
```

## Health

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
health_class unknown|healthy|degraded|unhealthy
evidence_state current|stale|incomplete|reconciliation_required|unavailable
projection_revision
last_changed_at / last_evidence_at
bounded problem refs
```

## Historical completeness

```text
complete
incomplete
gap_detected
reconciliation_required
```

`complete` is evidence-backed; gap/incomplete is not hidden by pagination.

## Sync operation

Common operation representation + source/generation/trigger/checkpoint/safe dependency-failure/correlation metadata.

# Transaction/effect summary

| Class | Local authority | Idempotency/precondition | Provider call inside tx | Audit |
|---|---|---|---|---|
| source create | source + first generation + sync responsibility | required key | prohibited | privileged |
| source edit | source revision + revalidation/sync responsibility | required key + If-Match | prohibited | privileged |
| replace instance | fence/generation/config + successor operation | required key + If-Match | prohibited | privileged |
| reads | local authoritative/projection reads | intrinsic | no interactive provider passthrough | access telemetry |

The API serves local accepted state/evidence; it is not an unbounded synchronous proxy to Zabbix.

# Observability

Every operation propagates correlation context. Safe telemetry captures route/operation, bounded attribution, auth outcome class, latency/status/error class, sync correlation and history window/cost class without raw credentials, unrestricted metric/log values, provider payloads/tags or raw external errors.

Monitoring operational evidence includes source sync age/evidence state, dependency state, backlog/reconciliation/gaps, historical projector lag, current-state transition failures and tenant fairness/saturation under Phase 11/12 profiles.

# Recovery / relocation

After PITR/relocation:

- source generation/revision reconciles before mutation;
- retired placement/poll authority cannot mutate current state;
- missing observation/history/checkpoint is uncertainty;
- current metric values may remain last-known but expose non-current evidence until reconciled;
- historical completeness may downgrade;
- source/resource/problem/health reads preserve evidence state;
- idempotency/replacement outcomes reconcile through `(R,F]` before repeat execution.

# Dashboard composition

No mutable `/monitoring-dashboards` aggregate is created. The initial Monitoring dashboard composes resources, metric definitions/current state, health, problems, bounded history and sync evidence via BFF/read composition. Persistent presentation/cross-domain projections remain Reporting & Experience ownership.

# Compatibility-sensitive changes

Security/compatibility review is required for changes to tenant/action scope, source replacement, canonical identity/generation, current metric semantics, negative evidence, severity/health/evidence state, historical completeness, cursor classification/binding, idempotency/precondition replay, provider metadata authority or recovery fencing.

# Falsification matrix

1. Known Tenant B IDs cannot disclose/mutate through any route under Tenant A.
2. Same-key create replay creates one source; fingerprint mismatch conflicts.
3. PATCH stale revision cannot overwrite current state; successful-response-loss same-key replay recovers prior result instead of false `412`.
4. Zabbix base URL with userinfo/query/fragment/embedded credential rejects; ordinary PATCH cannot change base URL.
5. Replace-instance concurrency/idempotency produces one successor generation/operation.
6. New Zabbix generation never merges same-looking native IDs with old mappings.
7. Provider outage/visibility loss never turns known state into 404/removed/retired/resolved.
8. Current metric API returns transactional current projection and evidence state without querying historical latest per request.
9. Same current observation under later poll causes no duplicate transition/current `last_changed_at` advancement.
10. Provider clock rollback cannot freeze genuinely newer fenced current state.
11. History requires metric/from/to and finite window; no all-history fallback.
12. Every history page reauthorizes and non-completeness remains explicit.
13. Cursor exposed value contains no protected payload/topology/credential and possession grants no authority; this slice does not activate protected-continuation C5 semantics.
14. Zabbix severity maps only to canonical classes; acknowledgement/tags remain metadata.
15. Last-known health/current metric with non-current evidence remains visibly non-current.
16. Sync operation ID cannot grant authority or reveal topology.
17. One tenant's history/sync/cardinality pressure is bounded and cannot starve unrelated tenants.
18. Recovery invalidates stale placement/poll/idempotency assumptions rather than reopening authority.

# OPENs preserved

This contract closes endpoint/use-case semantics but does not close:

- `OPEN-REL-030` customer telemetry C2 conformance;
- Tier 2 telemetry store selection;
- secret-manager/KMS/credential-binding mechanism;
- broker/outbox physical dispatch;
- provider timeout/retry/page/history/reconciliation numerics;
- production page/window/retention/capacity/SLO numerics.

`OPEN-API-019` remains C5 and is **not activated** because Monitoring cursors are constrained to `url_safe_non_sensitive_handle` semantics. If a future Monitoring query requires a protected continuation token/payload, that is a new owning-governance decision, not an implementation shortcut.

No source `DELETE`, tenant manual sync/retry/resume, provider write-back, Alerting acknowledgement, ITSM mutation or dashboard mutation endpoint is authorized implicitly.
