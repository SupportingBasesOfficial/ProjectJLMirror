# Monitoring Domain API Contract — Wave 4 Entry

**Status:** proposed baseline  
**API major:** v1  
**Owner:** Monitoring  
**Companion:** `docs/03-domains/monitoring-domain-contract.md`  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001`, `AC-003`, `AC-006`, `AC-012`, Phase 09 endpoint/collection contracts, Zabbix provider/normalization profiles

## Purpose

This document turns the Monitoring families reserved by `domain-api-surface-map.md` into exact endpoint/use-case contracts for the accepted core Monitoring product outcome. It inherits Phase 09 canonical HTTP, authorization, idempotency, concurrency, collection, cache, error and recovery laws.

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

Timestamps use the accepted UTC Phase 09 representation. Provider event time remains data, not authorization/current-ordering authority.

Provider-native IDs/metadata are optional bounded protected external evidence and never replace canonical IDs.

## Pagination — URL-safe non-sensitive anchor cursor

Monitoring collection cursors use the accepted Phase 09 `url_safe_non_sensitive_handle` class and are further constrained to a non-sensitive **anchor cursor**. This contract deliberately does **not** activate the C5 protected-continuation mechanism in `OPEN-API-019`.

The exposed `cursor` is only an opaque anchor identity derived from an item already returned by the same collection contract. It SHALL NOT contain, encrypt, sign or indirectly reference hidden protected continuation payload such as tenant identity, confidential filters, provider secrets, physical topology, arbitrary database predicates or a reusable privileged query snapshot.

Continuation requests resubmit the same canonical non-sensitive filters/window parameters explicitly. The server:

1. re-establishes current authentication, tenant placement and authorization;
2. resolves the supplied anchor inside the current tenant/resource scope;
3. verifies that the anchor is eligible under the current endpoint's resubmitted filters/window;
4. derives deterministic sort position from the authoritative anchored row;
5. returns only rows after that position according to declared ordering.

Anchor classes:

```text
monitoring-sources          -> monitoring_source_id
monitoring-resources        -> monitoring_resource_id
metric-definitions          -> metric_definition_id
metric-current-states       -> metric_definition_id
health-projections          -> monitoring_resource_id
monitoring-sync-operations  -> monitoring_sync_operation_id; derive created_at tie position
problems                    -> problem_id; derive opened_at tie position
metric-observations         -> observation_id; validate metric/from/to and derive observed_at tie position
```

Required properties:

```text
opaque to client
anchor itself URL-safe/non-sensitive under response classification
no protected cursor payload or dedicated protected cursor state
possession grants no read/continuation authority
current authorization and current filter/window validation on every page
cross-tenant / wrong-filter / wrong-window anchors fail sparsely without existence leakage
```

A server implementation SHALL NOT replace this profile with an encrypted/signed protected payload or a server-side handle whose hidden state carries protected continuation/query data while still claiming `OPEN-API-019` is deferred.

Collection shape:

```json
{"items": [], "next_cursor": "opaque-anchor-or-null"}
```

All collections have deterministic stable ordering, finite row limits **and finite serialized response-byte budgets**. Production row/byte numerics remain evidence-driven; `OPEN` never means unlimited and mandatory safety/resource bounds must be selected before implementation.

## Response-cache profile by data class

Protected Monitoring data is never `public_shared`.

The initial profile is deliberately conservative:

| Surface | Cache class | Rationale |
|---|---|---|
| source list/detail/mutations | `no_store` | endpoint/config/credential-binding metadata |
| resource list | `private_revalidate` | bounded summary only; no unrestricted provider metadata |
| resource detail | `no_store` | protected external-reference metadata may appear |
| metric-definition list | `private_revalidate` | metadata only; no current value |
| metric-definition detail | `no_store` | protected external references may appear |
| metric-current-state list/detail | `no_store` | customer metric values may be sensitive |
| metric history | `no_store` | customer values/history may be sensitive and high-volume |
| problems list/detail | `no_store` | summaries/provider metadata may contain customer data |
| health projections | `private_revalidate` | bounded canonical status/IDs only |
| sync operations | `no_store` | operational/provider diagnostic metadata |

For `private_revalidate`, reuse requires server revalidation/current authorization under the accepted Phase 09 cache contract; it is not an authorization-bypassing freshness TTL. BFF policy may be stricter.

Protected authentication/authorization/existence-concealing error variants follow `no_store` or the stricter inherited private policy.

## Errors

Stable classes include:

```text
authentication.*
authorization.*
resource.not_found
validation.*
validation.cursor_invalid
concurrency.precondition_required
concurrency.revision_mismatch
idempotency.*
rate_limit.*
dependency.*
monitoring.provider_profile_unsupported
monitoring.source_instance_replacement_required
monitoring.replacement_candidate_invalid
monitoring.replacement_candidate_not_ready
monitoring.replacement_reconciliation_required
monitoring.source_visibility_degraded
monitoring.history_window_required
monitoring.history_incomplete
monitoring.history_gap
monitoring.reconciliation_required
```

No raw provider exception/credential/internal topology is exposed. Provider omission/outage cannot turn a previously known resource into 404/removed/resolved by itself.

## Mutation idempotency + precondition ordering

Source mutations use current authorization, canonical request semantics, required `Idempotency-Key` and, for existing sources, `If-Match`.

Response-loss rule:

- for a **new idempotency key**, the one logical executor validates supplied current resource precondition before committing;
- for an **existing same-key/same-fingerprint claim**, the server observes the recorded/in-progress logical operation before treating the now-advanced revision as a fresh conflicting request;
- retry after successful-but-response-lost mutation can therefore recover original logical result;
- same key with different canonical fingerprint returns `409 idempotency.key_reused`;
- a different idempotency key is a new command and must satisfy current `If-Match`.

Current authentication/authorization is re-evaluated on replay; idempotency never freezes permission.

## Base URL/provider-endpoint safety

For Zabbix, submitted base URL configuration uses a canonical HTTPS URI profile:

```text
scheme          https
host            required
port            optional allowed profile
path            allowed/bounded for reverse-proxy deployments
userinfo        prohibited
query           prohibited
fragment        prohibited
embedded secret prohibited
```

Source-command admission performs deterministic canonical URI/profile validation and static deny/allow checks that do not require external network resolution.

**DNS resolution, connection attempts, redirect evaluation and every network-dependent SSRF/egress validation SHALL NOT occur inside an ordinary source-configuration database transaction.**

Before each provider use, the outbound connector independently revalidates destination under accepted DNS/IP/protocol/redirect/egress policy and fails closed/degrades the relevant operation when authority cannot be proven safely.

URL/DNS/network location never becomes tenant, resource or authorization authority.

---

# Source operations

## `monitoring.listSources`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sources
action        monitoring.source.read
consistency   committed configuration + projected operational evidence
cache         no_store
pagination    live traversal, monitoring_source_id ASC
```

Filters: `provider_profile`, `operational_evidence_state`, `cursor`, `limit`.

`200` returns bounded `MonitoringSourceSummary[]` + `next_cursor`.

## `monitoring.createSource`

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources
action          monitoring.source.manage
audit           privileged
Idempotency-Key required
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

- initial accepted provider profile is `zabbix`;
- no raw API token/secret bytes in Monitoring body;
- unknown body members reject;
- deterministic URL/profile/scope syntax/static policy validates before commit;
- no DNS/provider/network call is held inside local transaction;
- create persists source + first active generation + revision + audit + durable validation/sync responsibility when ingestion is activated.

Idempotency scope:

```text
tenant_id + monitoring.createSource + key
```

`201 Created` returns `MonitoringSourceDetail` + `Location`; repeated same key/fingerprint observes same logical source. Success means local creation committed, not that external provider is reachable/trusted.

## `monitoring.getSource`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
action       monitoring.source.read
cache        no_store
```

Returns canonical ID, profile/display metadata, active generation, revision, safe endpoint/scope metadata, policy-safe credential-binding reference metadata, evidence state, replacement-candidate reference/state when present, and sync timestamps/references. Never returns credential secret bytes.

## `monitoring.updateSource`

```text
PATCH /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
action          monitoring.source.manage
audit           privileged
If-Match         required
Idempotency-Key  required
cache            no_store
```

Allowed fields:

```json
{
  "display_name": "optional",
  "credential_binding_ref": "optional",
  "configured_provider_scope": "optional profile-specific object"
}
```

At least one field required; unknown fields reject.

For Zabbix, base URL/provider-instance endpoint change here returns `409 monitoring.source_instance_replacement_required` without mutation.

### Scope-edit semantics

A configured-scope edit is local configuration authority, not provider negative evidence.

When the new scope excludes previously monitored objects:

- affected resources/metric definitions become `scope_state=out_of_scope` under the new configuration revision;
- their identities and retained history remain;
- exclusion alone cannot mark resources `removed`, metric definitions `retired`, or problems `resolved`;
- last-known current/health/problem evidence cannot be presented as freshly monitored after exclusion;
- re-inclusion requires provider evidence to re-establish currentness.

The source revision, scope-state transitions and required audit/transition intent commit under one local serialization boundary. Provider revalidation/sync occurs asynchronously afterwards.

New-key executor validates `If-Match`; missing -> `428`, mismatch -> `412`. Same-key replay follows shared response-loss rule.

`200` returns updated source/new revision.

## `monitoring.replaceSourceInstance` — create candidate

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}:replace-instance
action          monitoring.source.manage
audit           privileged
If-Match         required
Idempotency-Key  required
cache            no_store
consistency      committed replacement candidate + durable validation responsibility
```

Body contains successor provider configuration, credential binding and configured scope using same canonical/static profiles as creation.

This command **does not immediately fence the active generation**.

One logical command:

1. validates current auth/revision and deterministic configuration shape;
2. reserves one collision-safe candidate generation;
3. persists candidate config/credential/scope references and audit evidence;
4. creates one durable bounded candidate-validation operation;
5. leaves active source generation/config and its writer authority unchanged.

`202 Accepted` returns `MonitoringSyncOperation` specialized as replacement validation plus candidate reference/state. Same idempotency key/fingerprint observes same candidate.

Candidate provider/DNS/credential/scope validation runs outside the local transaction. Candidate evidence cannot mutate tenant-facing resource/metric/problem/health/current state before cutover.

Validation failure leaves the healthy active generation in place and records a safe failure class. It never silently activates the candidate.

## `monitoring.activateReplacementCandidate` — atomic cutover

```text
POST /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}/replacement-candidates/{candidate_generation}:activate
action          monitoring.source.manage
audit           privileged
If-Match         required
Idempotency-Key  required
cache            no_store
consistency      serialized active-generation cutover + durable successor sync responsibility
```

The candidate must have accepted current `ready_for_cutover` validation evidence. If not, return `409 monitoring.replacement_candidate_not_ready` without changing active generation.

One logical cutover:

1. re-establishes current authorization;
2. validates expected source revision, candidate identity/state and validation evidence generation;
3. fences prior active provider-instance/poll writer authority;
4. atomically sets active generation/config/scope/credential refs to candidate;
5. advances source revision;
6. marks candidate activated and records prior-generation retirement/fence evidence;
7. persists required audit/transition intent;
8. creates exactly one durable successor synchronization/reconciliation responsibility;
9. never merges old/new provider-native mappings or deletes historical evidence.

`202 Accepted` returns successor sync operation + updated source link.

If cutover outcome is ambiguous across crash/PITR/relocation, further protected/effectful replacement admission is `reconciliation_required` until active-generation/fence/audit/idempotency/operation authorities prove the winner. There is never more than one active generation.

This two-step API intentionally prevents a bad URL, invalid credential or unreachable candidate from immediately taking down a healthy existing integration.

---

# Resource operations

## `monitoring.listResources`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources
action        monitoring.resource.read
consistency   committed local projection + evidence freshness
cache         private_revalidate
pagination    monitoring_resource_id ASC
```

Filters: source ID, `scope_state=in_scope|out_of_scope`, `presence_state=present|removed`, resource kind, health class/evidence state, cursor, limit.

Summary responses exclude unrestricted provider metadata. Missing provider rows under stale/incomplete/visibility-degraded evidence do not disappear. `removed` means authoritative negative evidence already committed. `out_of_scope` means local configuration no longer claims monitoring coverage.

## `monitoring.getResource`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources/{monitoring_resource_id}
action monitoring.resource.read
cache  no_store
```

Returns canonical identity, scope/presence/source generation/last-observed evidence and bounded protected external references where authorized.

---

# Metric definitions

## `monitoring.listMetricDefinitions`

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions
action        monitoring.metric.read
consistency   committed definition metadata
cache         private_revalidate
pagination    metric_definition_id ASC
```

Required singleton filter: `monitoring_resource_id`.

Optional: `scope_state=in_scope|out_of_scope`, `definition_state=active|retired`, cursor, limit.

Each item contains metadata only:

```json
{
  "metric_definition_id": "opaque",
  "monitoring_resource_id": "opaque",
  "name": "...",
  "value_kind": "number|integer|boolean|string|text|log",
  "unit": "nullable",
  "scope_state": "in_scope|out_of_scope",
  "definition_state": "active|retired"
}
```

Current metric values are deliberately **not embedded in every definition row**. This keeps definition enumeration bounded as metric cardinality/value size grows.

## `monitoring.getMetricDefinition`

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions/{metric_definition_id}
action monitoring.metric.read
cache  no_store
```

Returns `MetricDefinitionDetail` plus bounded protected external references where authorized. It may link to current-state and history surfaces; it does not query history to synthesize latest value.

---

# Current metric state

## `monitoring.listMetricCurrentStates`

```text
GET /api/v1/tenants/{tenant_id}/metric-current-states
action        monitoring.metric.read
consistency   committed transactional current-state projection
cache         no_store
pagination    metric_definition_id ASC
```

Required singleton filter:

```text
monitoring_resource_id
```

Optional singleton filters: `metric_definition_id`, evidence state, `scope_state`, cursor, limit.

Each row:

```json
{
  "metric_definition_id": "opaque",
  "monitoring_resource_id": "opaque",
  "monitoring_source_id": "opaque",
  "source_instance_generation": "opaque",
  "scope_state": "in_scope|out_of_scope",
  "current_observation_id": "opaque-or-null",
  "observed_at": "timestamp-or-null",
  "accepted_at": "timestamp-or-null",
  "value_kind": "number|integer|boolean|string|text|log",
  "value": "bounded canonical value or null",
  "evidence_state": "current|stale|incomplete|reconciliation_required|unavailable",
  "projection_revision": "opaque",
  "last_changed_at": "timestamp-or-null"
}
```

This is the efficient current-state surface required by `FR-MON-003`; it never queries historical Tier 2 for “latest”.

A last-known value with non-current evidence cannot be presented as freshly proven current state. An out-of-scope metric cannot be presented as currently monitored even if a last value is retained.

Response admission is bounded by both row count and serialized byte budget. Every value kind has a mandatory accepted serialized-value bound before implementation; an oversized provider value cannot turn one request into unbounded memory/response consumption.

## `monitoring.getMetricCurrentState`

```text
GET /api/v1/tenants/{tenant_id}/metric-current-states/{metric_definition_id}
action monitoring.metric.read
cache  no_store
```

Returns one current-state projection if authorized. Resource/metric IDs do not bypass current tenant/resource authorization.

---

# Historical metric observations

## `monitoring.listMetricObservations`

```text
GET /api/v1/tenants/{tenant_id}/metric-observations
action        monitoring.metric.read
consistency   historical_window
cache         no_store
pagination    sort (observed_at ASC, observation_id ASC)
```

Required singleton query:

```text
metric_definition_id
from  inclusive UTC timestamp
to    exclusive UTC timestamp
```

Optional: cursor, limit.

Exactly one metric definition per request in this initial contract.

Rules:

- `from < to` and duration satisfy finite accepted policy;
- no missing-window fallback to all history;
- cursor is observation-ID anchor only; request resubmits exact metric/from/to window;
- every page reauthorizes current metric/resource scope;
- provider event time is historical data, not current authority;
- response is bounded by row count, time window and serialized byte budget;
- accepted per-value bounds apply to historical values as well.

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
  "next_cursor": "opaque-observation-anchor-or-null"
}
```

`complete` requires accepted lateness/retention/reconciliation evidence, not merely successful query execution. Configured out-of-scope intervals or known/uncertain provider gaps cannot be fabricated as continuous complete coverage.

---

# Problems

## `monitoring.listProblems`

```text
GET /api/v1/tenants/{tenant_id}/problems
action        monitoring.problem.read
cache         no_store
pagination    (opened_at DESC, problem_id ASC)
```

Filters: source ID, resource ID, `problem_state=active|resolved`, canonical severity, opened_from/to, cursor, limit.

Missing provider row is never implicit resolution. Scope exclusion is never implicit resolution. Items expose canonical state/severity, resource/source, timestamps and evidence state. Zabbix acknowledgement/tags may appear only as bounded non-authoritative provider metadata where policy permits.

## `monitoring.getProblem`

```text
GET /api/v1/tenants/{tenant_id}/problems/{problem_id}
action monitoring.problem.read
cache  no_store
```

Returns `ProblemDetail`; may link resources/health. Monitoring does not own Alerting/ITSM acknowledgement or incident state.

---

# Health

## `monitoring.listHealthProjections`

```text
GET /api/v1/tenants/{tenant_id}/health-projections
action        monitoring.health.read
cache         private_revalidate
pagination    monitoring_resource_id ASC
```

Filters: source ID, `health_class=unknown|healthy|degraded|unhealthy`, evidence state, resource scope state, cursor, limit.

Items expose only canonical health + scope/evidence state + revision/times/bounded problem IDs. A last-known `healthy` with stale evidence or out-of-scope coverage is visibly non-current.

## `monitoring.getHealthProjection`

```text
GET /api/v1/tenants/{tenant_id}/health-projections/{monitoring_resource_id}
action monitoring.health.read
cache  private_revalidate
```

Resource ID is projection identity. Provider severity is not serialized as health enum.

---

# Synchronization operations

## `monitoring.listSyncOperations`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sync-operations
action        monitoring.sync.read
cache         no_store
pagination    created_at DESC, operation_id ASC
```

Filters: source ID, source/candidate generation, common operation state, trigger class, cursor, limit.

Returns safe progress/checkpoint/failure/degradation/correlation metadata without credentials or physical worker/queue/database topology.

## `monitoring.getSyncOperation`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sync-operations/{monitoring_sync_operation_id}
action monitoring.sync.read
cache  no_store
```

Current authorization is re-established. Operation ID is never bearer authority.

No tenant-facing manual `:sync/:retry/:resume` command is invented here. Schedule, webhook hint, configuration, replacement and recovery workflows own execution until Product explicitly authorizes a manual command contract.

---

# Canonical response types

## Monitoring source

```text
monitoring_source_id
display_name
provider_profile
active_source_instance_generation
configuration_revision
safe provider configuration/scope metadata
credential_binding_ref metadata only where authorized
operational_evidence_state
replacement_candidate_ref/state where present
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
scope_state in_scope|out_of_scope
presence_state present|removed
bounded external_references only on permitted detail surface
last_observed_at
last_confirmed_present_at
created_at / updated_at
```

## Metric definition

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
name
value_kind
unit
scope_state in_scope|out_of_scope
definition_state active|retired
bounded external_references only on permitted detail surface
```

## Metric current state

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
scope_state
current_observation_id
observed_at
accepted_at
value_kind
value
evidence_state
projection_revision
last_changed_at
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
scope_state
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

`complete` is evidence-backed; gap/incomplete/out-of-scope coverage is not hidden by pagination.

## Sync operation

Common operation representation + source/generation/trigger/checkpoint/safe dependency-failure/correlation metadata.

# Transaction/effect summary

| Class | Local authority | Idempotency/precondition | Provider call inside tx | Audit |
|---|---|---|---|---|
| source create | source + first active generation + sync responsibility | required key | prohibited | privileged |
| source edit | source revision + scope state + revalidation/sync responsibility | key + If-Match | prohibited | privileged |
| replacement candidate | candidate + validation responsibility | key + If-Match | prohibited | privileged |
| replacement cutover | active-generation fence/config + successor responsibility | key + If-Match | prohibited | privileged |
| reads | local authoritative/projection reads | intrinsic | no provider passthrough | access telemetry |

The API serves local accepted state/evidence; it is not an unbounded synchronous proxy to Zabbix.

# Data-size / abuse boundary

Before implementation, the accepted profile SHALL provide finite values for every mandatory resource bound used by this vertical, including:

```text
provider response/body bytes
provider string/text/log value bytes
normalized metric value serialized bytes
collection page rows
collection serialized response bytes
history time-window maximum
history rows/bytes per response
provider scope-selector count/size
problem metadata count/size
replacement candidates retained per source
sync/concurrency/backlog per tenant/source
```

The runtime may return fewer rows than the nominal row limit to honor the byte budget. A single oversized provider value is rejected/quarantined/degraded according to the accepted normalization/ingress profile; it is never admitted as an unbounded payload merely because the provider sent it.

`SEC-ABUSE-001/002` tenant/principal/route/integration controls apply independently from pagination.

# Observability

Every operation propagates correlation context. Safe telemetry captures route/operation, bounded attribution, auth outcome class, latency/status/error class, sync correlation and history window/cost class without raw credentials, unrestricted metric/log values, provider payloads/tags or raw external errors.

Monitoring operational evidence includes source sync age/evidence state, replacement candidate/validation state, dependency state, backlog/reconciliation/gaps, historical projector lag, current-state transition failures and tenant fairness/saturation.

# Recovery / relocation

After PITR/relocation:

- active source generation/revision reconciles before mutation;
- replacement candidate/cutover winner reconciles before further activation;
- candidate reachability alone cannot become active authority;
- retired placement/poll authority cannot mutate current state;
- missing observation/history/checkpoint is uncertainty;
- current metric values may remain last-known but expose non-current evidence until reconciled;
- configured scope revision/state is reconciled before absence inference;
- historical completeness may downgrade;
- cursor anchors are re-resolved under current tenant/filter/window state;
- idempotency/replacement outcomes reconcile through `(R,F]` before repeat execution.

# Dashboard composition

No mutable `/monitoring-dashboards` aggregate is created. The initial Monitoring dashboard composes resources, metric definitions, dedicated current-state reads, health, problems, bounded history and sync evidence via BFF/read composition. Persistent presentation/cross-domain projections remain Reporting & Experience ownership.

# Compatibility-sensitive changes

Security/compatibility review is required for changes to tenant/action scope, replacement candidate/cutover semantics, configured-scope semantics, canonical identity/generation, current metric semantics/surface, negative evidence, severity/health/evidence state, historical completeness, cursor classification/anchor rules, idempotency/precondition replay, provider metadata authority, cache classification or recovery fencing.

# Falsification matrix

1. Known Tenant B IDs cannot disclose/mutate through any route under Tenant A.
2. Same-key create replay creates one source; fingerprint mismatch conflicts.
3. PATCH stale revision cannot overwrite current state; successful-response-loss same-key replay recovers prior result instead of false `412`.
4. Zabbix base URL with userinfo/query/fragment/embedded credential rejects; DNS/provider validation is never held inside write transaction.
5. Bad replacement candidate cannot fence/degrade healthy active generation solely by being requested.
6. Candidate generation cannot write canonical Monitoring state before activation.
7. Concurrent cutover attempts result in at most one active-generation winner and one successor responsibility.
8. New Zabbix generation never merges same-looking native IDs with old mappings.
9. Scope exclusion produces out-of-scope state and never provider removal/retirement/resolution by itself.
10. Re-inclusion requires fresh provider evidence before currentness is restored.
11. Provider outage/visibility loss never turns known state into 404/removed/retired/resolved.
12. Metric-definition listing does not embed all current values.
13. Current metric API reads transactional current projection without querying historical latest per request.
14. Current/history/problem payloads are `no_store` and cannot become shared/public cache entries.
15. Same current observation under later poll causes no duplicate transition/current `last_changed_at` advancement.
16. Provider clock rollback cannot freeze genuinely newer fenced current state.
17. History requires metric/from/to and finite window; no all-history fallback.
18. Every history page reauthorizes and non-completeness remains explicit.
19. Cursor is only authorized-row anchor, contains/references no protected continuation payload/state, and possession grants no authority.
20. Cross-tenant/wrong-filter/wrong-window cursor anchors fail without existence leakage.
21. Zabbix severity maps only to canonical classes; acknowledgement/tags remain metadata.
22. Last-known health/current metric with non-current evidence or out-of-scope state remains visibly non-current.
23. Sync operation ID cannot grant authority or reveal topology.
24. One tenant's history/sync/cardinality pressure is bounded and cannot starve unrelated tenants.
25. Oversized provider metric/log/text/problem values are bounded before memory/storage/response exhaustion.
26. Recovery invalidates stale placement/poll/idempotency/candidate assumptions rather than reopening authority.

# OPENs preserved

This contract closes endpoint/use-case semantics but does not close:

- `OPEN-REL-030` customer telemetry C2 conformance;
- Tier 2 telemetry store selection;
- secret-manager/KMS/credential-binding mechanism;
- broker/outbox physical dispatch;
- provider timeout/retry/page/history/reconciliation numerics;
- mandatory per-value/page/window/candidate/concurrency bounds;
- production retention/capacity/SLO numerics.

`OPEN-API-019` remains C5 and is **not activated** because this Monitoring profile uses only returned-row anchor cursors with no hidden protected continuation payload/state.

No source `DELETE`, tenant manual sync/retry/resume, provider write-back, Alerting acknowledgement, ITSM mutation or dashboard mutation endpoint is authorized implicitly.