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

Timestamps use accepted UTC Phase 09 representation. Provider event time remains data, not authorization/current-ordering authority.

Provider-native IDs/metadata are optional bounded protected external evidence and never replace canonical IDs.

## Generation-state response semantics

Every generation-scoped resource/metric/problem/health/current-state representation exposes:

```text
generation_state = active_generation | historical_generation
```

This value is derived by comparing the object's `source_instance_generation` with the source's currently authoritative `active_source_instance_generation`; it is not maintained by rewriting all child rows during cutover.

Rules:

- current operational collection endpoints default to `generation_state=active_generation`;
- explicit historical inclusion requires `generation_state=historical_generation` or another documented historical filter on endpoints that support it;
- direct lookup of a known historical-generation canonical ID may return retained evidence under current authorization, but the representation remains visibly historical;
- `historical_generation` is not serialized as `removed`, `retired` or `resolved` and cannot participate in current health/current-value/current-problem/provider-work authority;
- a prior-generation problem with `problem_state=active` remains historical unresolved evidence rather than a current problem;
- after cutover, successor current coverage may be incomplete until successor sync establishes it; the API does not fill that gap with prior-generation state.

## Pagination — URL-safe non-sensitive anchor cursor

Monitoring collection cursors use the accepted Phase 09 `url_safe_non_sensitive_handle` class and are further constrained to a non-sensitive **anchor cursor**. This contract deliberately does **not** activate the C5 protected-continuation mechanism in `OPEN-API-019`.

The exposed `cursor` is only an opaque anchor identity derived from an item already returned by the same collection contract. It SHALL NOT contain, encrypt, sign or indirectly reference hidden protected continuation payload such as tenant identity, confidential filters, provider secrets, physical topology, arbitrary database predicates or a reusable privileged query snapshot.

Continuation requests resubmit the same canonical non-sensitive filters/window parameters explicitly. The server:

1. re-establishes current authentication, tenant placement and authorization;
2. resolves supplied anchor inside current tenant/resource scope;
3. verifies anchor eligibility under current endpoint filters/window, including generation-state selection where applicable;
4. derives deterministic sort position from authoritative anchored row;
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
cross-tenant / wrong-filter / wrong-window / wrong-generation anchors fail sparsely without existence leakage
```

A server implementation SHALL NOT replace this profile with an encrypted/signed protected payload or server-side hidden query state while still claiming `OPEN-API-019` is deferred.

Collection shape:

```json
{"items": [], "next_cursor": "opaque-anchor-or-null"}
```

All collections have deterministic stable ordering, finite row limits **and finite serialized response-byte budgets**. Production row/byte numerics remain evidence-driven; `OPEN` never means unlimited and mandatory safety/resource bounds must be selected before implementation.

## Response-cache profile by data class

Protected Monitoring data is never `public_shared`.

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

For `private_revalidate`, reuse requires server revalidation/current authorization under the accepted Phase 09 cache contract; it is not an authorization-bypassing freshness TTL. Revalidation also recomputes/validates generation and scope currentness rather than replaying an old `active_generation`/`in_scope` classification blindly. BFF policy may be stricter.

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
monitoring.replacement_validation_stale
monitoring.replacement_reconciliation_required
monitoring.scope_reconciliation_required
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

- for a new idempotency key, the one logical executor validates supplied current resource precondition before committing;
- for an existing same-key/same-fingerprint claim, the server observes recorded/in-progress logical operation before treating advanced revision as a fresh conflicting request;
- retry after successful-but-response-lost mutation can recover original logical result;
- same key with different canonical fingerprint returns `409 idempotency.key_reused`;
- a different key is a new command and must satisfy current `If-Match`.

Current authentication/authorization is re-evaluated on replay; idempotency never freezes permission.

## Base URL/provider-endpoint safety

For Zabbix, submitted base URL uses a canonical HTTPS URI profile:

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

Before each provider use, outbound connector independently revalidates destination under accepted DNS/IP/protocol/redirect/egress policy and fails closed/degrades relevant operation when authority cannot be proven safely.

URL/DNS/network location never becomes tenant, resource or authorization authority.

---

# Source operations

## `monitoring.listSources`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sources
action        monitoring.source.read
consistency   committed configuration + projected operational evidence
cache         no_store
pagination    monitoring_source_id ASC
```

Filters: `provider_profile`, `operational_evidence_state`, cursor, limit.

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
- create persists source + first active generation + first scope revision + audit + durable validation/sync responsibility when ingestion is activated.

Idempotency scope:

```text
tenant_id + monitoring.createSource + key
```

`201 Created` returns `MonitoringSourceDetail` + `Location`; repeated same key/fingerprint observes same logical source. Success means local creation committed, not that external provider is reachable/trusted.

## `monitoring.getSource`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-sources/{monitoring_source_id}
action monitoring.source.read
cache  no_store
```

Returns canonical ID, profile/display metadata, active generation, configuration revision, scope revision, safe endpoint/scope metadata, policy-safe credential-binding reference metadata, evidence state, replacement-candidate state/validation age where present, and sync references. Never returns credential secret bytes.

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

### Scope-edit semantics — revisioned and bounded

A configured-scope edit is local configuration authority, not provider negative evidence.

The local source transaction:

1. validates current auth, source revision and canonical scope shape;
2. commits new `configured_provider_scope` and monotonically advances `scope_revision`;
3. persists required audit/transition intent;
4. creates one durable bounded scope-reconciliation responsibility;
5. **does not synchronously rewrite every resource/metric row**.

Per-object scope state for the active generation is a derived projection carrying:

```text
scope_state = in_scope | out_of_scope
scope_projection_revision
scope_evidence_state = current | reconciliation_required
```

An active-generation object may claim current `in_scope` only when its projection is proven against the source's current `scope_revision`, or an equivalent current deterministic scope evaluation proves it. A stale projection fails safe with `scope_evidence_state=reconciliation_required`; it cannot authorize provider work, fresh current-value/health semantics, or negative inference.

Historical-generation objects retain their historical scope evidence and are not relabeled against the successor/current generation's scope revision.

When reconciliation establishes exclusion:

- affected active-generation resources/metric definitions project `out_of_scope`;
- identity/history remain;
- exclusion alone cannot mark resource `removed`, metric `retired`, or problem `resolved`;
- re-inclusion requires provider evidence to re-establish currentness.

This makes the mutation O(1)/bounded with respect to source configuration rather than O(number_of_resources + number_of_metrics). Derived projection work is bounded/partitioned asynchronously.

New-key executor validates `If-Match`; missing -> `428`, mismatch -> `412`. Same-key replay follows shared response-loss rule.

`200` returns updated source/new revision plus scope-reconciliation operation/reference when scope changed.

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
2. reserves one collision-safe candidate generation and candidate scope revision;
3. persists immutable candidate config/credential/scope references and audit evidence;
4. creates one durable bounded candidate-validation operation;
5. leaves active source generation/config and writer authority unchanged.

`202 Accepted` returns replacement validation operation + candidate state. Same idempotency key/fingerprint observes same candidate.

Candidate provider/DNS/credential/scope validation runs outside local transaction. Candidate evidence cannot mutate tenant-facing resource/metric/problem/health/current state before cutover.

### Candidate validation currentness

`ready_for_cutover` is bounded evidence, not a permanent flag. The durable readiness proof is bound to the candidate generation/configuration revision/scope revision, canonical configuration fingerprint, a mechanism-specific credential-binding freshness/generation reference once the C2 secret mechanism exists, validation policy/profile generation, validation-evidence generation and `validated_at`.

Any candidate configuration/scope/effective credential-binding/policy change that invalidates the proof resets readiness and requires revalidation. Candidate payload is not edited in place while preserving prior evidence; a changed replacement intent creates/supersedes through new candidate revision/generation semantics.

Validation freshness has a finite accepted horizon selected by evidence; expired/unprovable freshness yields `409 monitoring.replacement_validation_stale` (or an in-progress validation operation) and cannot activate. Exact duration remains evidence-driven but cannot be infinite.

Actual provider use still revalidates egress/credential authority immediately before use; candidate readiness does not freeze DNS/reachability/secret state.

Validation failure leaves healthy active generation in place and records safe failure class.

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

Candidate must have accepted **currently valid** `ready_for_cutover` validation evidence. Otherwise return `409 monitoring.replacement_candidate_not_ready` or `monitoring.replacement_validation_stale` without changing active generation.

One logical cutover:

1. re-establishes current authorization;
2. validates expected source revision, candidate identity/state, immutable candidate revisions/fingerprint and current validation evidence generation/freshness;
3. fences prior active provider-instance/poll writer authority;
4. atomically sets active generation/config/scope/credential refs to candidate;
5. advances source configuration and scope revisions;
6. marks candidate activated and records prior-generation retirement/fence evidence;
7. persists required audit/transition intent;
8. creates exactly one durable successor synchronization/scope-reconciliation responsibility;
9. moves source operational evidence to at least `reconciliation_required` until successor current coverage is established;
10. never merges old/new provider-native mappings or deletes historical evidence.

The active-generation pointer change immediately makes all old generation-scoped objects `historical_generation` by derivation. The cutover SHALL NOT synchronously rewrite those rows.

`202 Accepted` returns successor sync operation + updated source link.

If cutover outcome is ambiguous across crash/PITR/relocation, further protected/effectful replacement admission is `reconciliation_required` until active-generation/fence/audit/idempotency/operation authorities prove the winner. There is never more than one active generation. Restored/expired validation state without current evidence cannot authorize cutover.

---

# Resource operations

## `monitoring.listResources`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources
action        monitoring.resource.read
consistency   committed local projection + evidence freshness
cache         private_revalidate
pagination    monitoring_resource_id ASC
default        generation_state=active_generation
```

Filters: source ID, `generation_state=active_generation|historical_generation`, scope state/evidence, `presence_state=present|removed`, resource kind, health/evidence state, cursor, limit.

Summary responses exclude unrestricted provider metadata. Missing provider rows under stale/incomplete/visibility/scope-reconciliation uncertainty do not disappear. `removed` means authoritative negative evidence already committed.

A returned `scope_state=in_scope` with `scope_evidence_state=current` has current monitoring meaning only for `generation_state=active_generation`. Historical-generation rows are explicitly historical regardless of retained scope/presence evidence.

## `monitoring.getResource`

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources/{monitoring_resource_id}
action monitoring.resource.read
cache  no_store
```

Returns canonical identity, `generation_state`, scope state/evidence/revision, presence/source generation/last-observed evidence and bounded protected external references where authorized. A historical-generation direct lookup is permitted as retained evidence but cannot be represented as current inventory.

---

# Metric definitions

## `monitoring.listMetricDefinitions`

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions
action        monitoring.metric.read
consistency   committed definition metadata
cache         private_revalidate
pagination    metric_definition_id ASC
default        generation_state=active_generation
```

Required singleton filter: `monitoring_resource_id`.

Optional: generation state, scope state/evidence, `definition_state=active|retired`, cursor, limit.

Each item contains metadata only:

```json
{
  "metric_definition_id": "opaque",
  "monitoring_resource_id": "opaque",
  "source_instance_generation": "opaque",
  "generation_state": "active_generation|historical_generation",
  "name": "...",
  "value_kind": "number|integer|boolean|string|text|log",
  "unit": "nullable",
  "scope_state": "in_scope|out_of_scope",
  "scope_evidence_state": "current|reconciliation_required",
  "definition_state": "active|retired"
}
```

Current metric values are deliberately **not embedded in every definition row**. Historical-generation definitions remain metadata/history anchors, not current metric definitions.

## `monitoring.getMetricDefinition`

```text
GET /api/v1/tenants/{tenant_id}/metric-definitions/{metric_definition_id}
action monitoring.metric.read
cache  no_store
```

Returns `MetricDefinitionDetail` plus `generation_state` and bounded protected external references. It may link to current-state/history surfaces; it does not query history to synthesize latest value.

---

# Current metric state

## `monitoring.listMetricCurrentStates`

```text
GET /api/v1/tenants/{tenant_id}/metric-current-states
action        monitoring.metric.read
consistency   committed transactional current-state projection
cache         no_store
pagination    metric_definition_id ASC
default        generation_state=active_generation
```

Required singleton filter: `monitoring_resource_id`.

Optional filters: `metric_definition_id`, `generation_state`, evidence state, scope state/evidence, cursor, limit.

Each row:

```json
{
  "metric_definition_id": "opaque",
  "monitoring_resource_id": "opaque",
  "monitoring_source_id": "opaque",
  "source_instance_generation": "opaque",
  "generation_state": "active_generation|historical_generation",
  "scope_state": "in_scope|out_of_scope",
  "scope_evidence_state": "current|reconciliation_required",
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

This is the efficient current-state surface required by `FR-MON-003`; it never queries historical Tier 2 for latest.

Only active-generation rows may carry current operational meaning. If an explicitly requested historical-generation row is returned, its value is last-known retained evidence and SHALL NOT be presented as currently monitored; API/BFF representation treats its operational evidence as non-current even if stored pre-cutover evidence had been current.

An active-generation metric with stale/unreconciled scope cannot be presented as currently monitored. Response admission is bounded by row count and serialized byte budget. Every value kind has mandatory accepted serialized-value bound before implementation.

## `monitoring.getMetricCurrentState`

```text
GET /api/v1/tenants/{tenant_id}/metric-current-states/{metric_definition_id}
action monitoring.metric.read
cache  no_store
```

Returns one last-known current-state projection if authorized, including derived `generation_state`. A historical-generation result is explicitly historical/non-current. Resource/metric IDs do not bypass current tenant/resource authorization.

---

# Historical metric observations

## `monitoring.listMetricObservations`

```text
GET /api/v1/tenants/{tenant_id}/metric-observations
action        monitoring.metric.read
consistency   historical_window
cache         no_store
pagination    (observed_at ASC, observation_id ASC)
```

Required query:

```text
metric_definition_id
from  inclusive UTC timestamp
to    exclusive UTC timestamp
```

Optional: cursor, limit.

Exactly one canonical metric definition per request. Because metric identity is generation-scoped, requested definition fixes the historical source generation; cross-generation history is never silently unioned by matching provider item/name.

Rules:

- `from < to` and duration satisfy finite accepted policy;
- no missing-window fallback to all history;
- cursor is observation-ID anchor only; request resubmits exact metric/from/to window;
- every page reauthorizes current metric/resource scope;
- provider event time is historical data, not current authority;
- response is bounded by row count, time window and serialized byte budget;
- accepted per-value bounds apply to historical values.

`200`:

```json
{
  "metric_definition_id": "opaque",
  "source_instance_generation": "opaque",
  "generation_state": "active_generation|historical_generation",
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

`complete` requires accepted lateness/retention/reconciliation evidence for that generation. Configured out-of-scope, generation-cutover or unreconciled intervals and known/uncertain provider gaps cannot be fabricated as continuous complete coverage.

---

# Problems

## `monitoring.listProblems`

```text
GET /api/v1/tenants/{tenant_id}/problems
action        monitoring.problem.read
cache         no_store
pagination    (opened_at DESC, problem_id ASC)
default        generation_state=active_generation
```

Filters: source ID, resource ID, generation state, problem state, canonical severity, opened_from/to, cursor, limit.

Missing provider row is never implicit resolution. Scope exclusion/stale scope membership and source-generation retirement are never implicit resolution. Items expose canonical state/severity, source generation, derived `generation_state`, resource/source, timestamps and evidence state. Zabbix acknowledgement/tags may appear only as bounded non-authoritative provider metadata where policy permits.

A historical-generation problem with `problem_state=active` means “unresolved in retained evidence when that generation ceased to be active”; it is excluded from current operational problem/Alerting input by generation state.

## `monitoring.getProblem`

```text
GET /api/v1/tenants/{tenant_id}/problems/{problem_id}
action monitoring.problem.read
cache  no_store
```

Returns `ProblemDetail` including derived `generation_state`; may link resources/health. Monitoring does not own Alerting/ITSM acknowledgement or incident state.

---

# Health

## `monitoring.listHealthProjections`

```text
GET /api/v1/tenants/{tenant_id}/health-projections
action        monitoring.health.read
cache         private_revalidate
pagination    monitoring_resource_id ASC
default        generation_state=active_generation
```

Filters: source ID, generation state, health class, evidence state, scope state/evidence, cursor, limit.

Items expose canonical health + source generation + derived generation state + scope/evidence state + revision/times/bounded problem IDs. A historical-generation projection never has current-health authority even if its retained class was `healthy`.

## `monitoring.getHealthProjection`

```text
GET /api/v1/tenants/{tenant_id}/health-projections/{monitoring_resource_id}
action monitoring.health.read
cache  private_revalidate
```

Resource ID is projection identity. Response includes derived `generation_state`. Provider severity is not serialized as health enum.

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

No tenant-facing manual `:sync/:retry/:resume` command is invented here. Schedule, webhook hint, configuration, scope reconciliation, replacement and recovery workflows own execution until Product explicitly authorizes a manual command contract.

---

# Canonical response types

## Monitoring source

```text
monitoring_source_id
display_name
provider_profile
active_source_instance_generation
configuration_revision
scope_revision
safe provider configuration/scope metadata
credential_binding_ref metadata only where authorized
operational_evidence_state
replacement_candidate_ref/state/validation age where present
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
generation_state active_generation|historical_generation
display_name
resource_kind
scope_state
scope_projection_revision
scope_evidence_state
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
generation_state active_generation|historical_generation
name
value_kind
unit
scope_state
scope_projection_revision
scope_evidence_state
definition_state active|retired
bounded external_references only on permitted detail surface
```

## Metric current state

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
generation_state active_generation|historical_generation
scope_state
scope_evidence_state
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
generation_state active_generation|historical_generation
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
generation_state active_generation|historical_generation
scope_state
scope_evidence_state
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

`complete` is evidence-backed; provider/scope/generation gaps are not hidden by pagination.

## Sync operation

Common operation representation + source/generation/trigger/checkpoint/safe dependency-failure/correlation metadata.

# Transaction/effect summary

| Class | Local authority | Idempotency/precondition | Provider call inside tx | Audit |
|---|---|---|---|---|
| source create | source + first active generation/scope revision + sync responsibility | required key | prohibited | privileged |
| source metadata edit | source revision + revalidation responsibility | key + If-Match | prohibited | privileged |
| source scope edit | source scope revision + scope-reconciliation responsibility | key + If-Match | prohibited | privileged |
| replacement candidate | immutable candidate + validation responsibility | key + If-Match | prohibited | privileged |
| replacement cutover | active-generation/config/scope fence + current candidate-validation evidence + successor responsibility | key + If-Match | prohibited | privileged |
| reads | local authoritative/projection reads | intrinsic | no provider passthrough | access telemetry |

Neither source scope edit nor generation cutover is an unbounded child-row rewrite transaction. The API serves local accepted state/evidence; it is not an unbounded synchronous proxy to Zabbix.

# Data-size / abuse boundary

Before implementation, accepted profile SHALL provide finite values for every mandatory resource bound used by this vertical, including:

```text
provider response/body bytes
provider string/text/log value bytes
normalized metric value serialized bytes
collection page rows
collection serialized response bytes
history time-window maximum
history rows/bytes per response
provider scope-selector count/size
replacement-validation freshness horizon / refresh workload
source generations retained / historical-query envelope
scope-reconciliation batch/backlog/concurrency
problem metadata count/size
replacement candidates retained per source
sync/concurrency/backlog per tenant/source
```

Runtime may return fewer rows than nominal row limit to honor byte budget. A single oversized provider value is rejected/quarantined/degraded according to accepted normalization/ingress profile; it is never admitted as unbounded payload merely because provider sent it.

`SEC-ABUSE-001/002` tenant/principal/route/integration controls apply independently from pagination.

# Observability

Every operation propagates correlation context. Safe telemetry captures route/operation, bounded attribution, auth outcome class, latency/status/error class, sync/scope/generation/candidate-validation correlation and history window/cost class without raw credentials, unrestricted metric/log values, provider payloads/tags or raw external errors.

Monitoring operational evidence includes source sync age/evidence state, replacement candidate/validation age/currentness, active generation/cutover, scope revision/reconciliation lag, dependency state, backlog/gaps, historical projector lag, current-state transition failures and tenant fairness/saturation.

# Recovery / relocation

After PITR/relocation:

- active source generation/configuration/scope revisions reconcile before mutation;
- replacement candidate/cutover winner and validation-evidence generation/freshness reconcile before further activation;
- restored `ready_for_cutover` without current validation continuity is not activation authority;
- candidate reachability alone cannot become active authority;
- historical generation cannot be reclassified active from stale restored state;
- stale scope projection cannot claim current `in_scope` or authorize negative inference;
- retired placement/poll authority cannot mutate current state;
- missing observation/history/checkpoint is uncertainty;
- current metric values may remain last-known but expose non-current generation/provider/scope evidence until reconciled;
- historical completeness may downgrade;
- cursor anchors re-resolve under current tenant/filter/window/generation state;
- idempotency/replacement outcomes reconcile through `(R,F]` before repeat execution.

# Dashboard composition

No mutable `/monitoring-dashboards` aggregate is created. Initial Monitoring dashboard composes **active-generation** resources, metric definitions, dedicated current-state reads, health, problems, bounded history and sync/scope/generation evidence via BFF/read composition. Historical-generation evidence requires explicit historical/drill-down use. Persistent presentation/cross-domain projections remain Reporting & Experience ownership.

# Compatibility-sensitive changes

Security/compatibility review is required for changes to tenant/action scope, source-generation operational lifecycle, replacement candidate/validation-currentness/cutover semantics, configured-scope revision/currentness semantics, canonical identity/generation, current metric semantics/surface, negative evidence, severity/health/evidence state, historical completeness, cursor classification/anchor rules, idempotency/precondition replay, provider metadata authority, cache classification or recovery fencing.

# Falsification matrix

1. Known Tenant B IDs cannot disclose/mutate through any route under Tenant A.
2. Same-key create replay creates one source; fingerprint mismatch conflicts.
3. PATCH stale revision cannot overwrite current state; successful-response-loss same-key replay recovers prior result instead of false `412`.
4. Zabbix base URL with userinfo/query/fragment/embedded credential rejects; DNS/provider validation is never held inside write transaction.
5. Bad replacement candidate cannot fence/degrade healthy active generation solely by being requested.
6. Candidate config/scope/credential/policy change or validation expiry invalidates old readiness; stale validation cannot activate.
7. Candidate generation cannot write canonical Monitoring state before activation.
8. Concurrent cutover attempts result in at most one active-generation winner and one successor responsibility.
9. Cutover does not rewrite every prior-generation child row; generation currentness changes by authoritative active-generation pointer/fence.
10. Prior-generation resources/metrics/problems/health/current values are excluded from current operational collections by default.
11. Prior-generation unresolved problem remains historical evidence and cannot feed current problem/Alerting semantics.
12. New Zabbix generation never merges same-looking native IDs with old mappings.
13. Scope edit commits without O(N) resource/metric row rewrite.
14. Stale scope projection cannot claim current `in_scope`, fresh health/value, provider-work eligibility or negative inference.
15. Scope exclusion never becomes provider removal/retirement/resolution by itself.
16. Re-inclusion requires fresh provider evidence before currentness is restored.
17. Provider outage/visibility loss never turns known state into 404/removed/retired/resolved.
18. Metric-definition listing does not embed all current values.
19. Current metric API reads transactional current projection without querying historical latest per request.
20. Current/history/problem payloads are `no_store` and cannot become shared/public cache entries.
21. Same current observation under later poll causes no duplicate transition/current `last_changed_at` advancement.
22. Provider clock rollback cannot freeze genuinely newer fenced current state.
23. History requires metric/from/to and finite window; no all-history fallback or implicit cross-generation union.
24. Every history page reauthorizes and non-completeness remains explicit.
25. Cursor is only authorized-row anchor, contains/references no protected continuation payload/state, and possession grants no authority.
26. Cross-tenant/wrong-filter/wrong-window/wrong-generation cursor anchors fail without existence leakage.
27. Zabbix severity maps only to canonical classes; acknowledgement/tags remain metadata.
28. Last-known health/current metric with non-current generation/provider/scope evidence remains visibly non-current.
29. Sync operation ID cannot grant authority or reveal topology.
30. One tenant's history/sync/validation/scope-reconciliation/cardinality pressure is bounded and cannot starve unrelated tenants.
31. Oversized provider metric/log/text/problem values are bounded before memory/storage/response exhaustion.
32. Recovery invalidates stale placement/poll/idempotency/candidate-validation/scope/generation assumptions rather than reopening authority.

# OPENs preserved

This contract closes endpoint/use-case semantics but does not close:

- `OPEN-REL-030` customer telemetry C2 conformance;
- Tier 2 telemetry store selection;
- secret-manager/KMS/credential-binding mechanism;
- broker/outbox physical dispatch;
- provider timeout/retry/page/history/reconciliation numerics;
- replacement-validation freshness numeric horizon and mechanism-specific credential freshness representation;
- mandatory per-value/page/window/scope-batch/generation-retention/candidate/concurrency bounds;
- production retention/capacity/SLO numerics.

`OPEN-API-019` remains C5 and is **not activated** because this Monitoring profile uses only returned-row anchor cursors with no hidden protected continuation payload/state.

No source `DELETE`, tenant manual sync/retry/resume, provider write-back, Alerting acknowledgement, ITSM mutation or dashboard mutation endpoint is authorized implicitly.