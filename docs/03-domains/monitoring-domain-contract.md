# Monitoring Domain Contract — Wave 4 Entry

**Status:** proposed baseline  
**Owner:** Monitoring bounded context  
**Wave:** 4 — Product/domain vertical-slice prerequisite  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001`, `AC-003`, `AC-006`, `AC-012`, ADR-008, ADR-009, ADR-013, ADR-019, `docs/08-data/telemetry-plane.md`, `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md`, `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`

## Purpose

This document closes the Monitoring domain/use-case semantics that Wave 4 code is not allowed to invent: canonical identity, source-instance replacement, current metric state, historical observations, problem/health normalization, negative evidence, synchronization ownership, recovery and tenant authority.

The HTTP representation is defined by `docs/09-api-contracts/monitoring-domain-api-contract.md`.

## Non-goals and authority limits

Acceptance does **not**:

- authorize Wave 4 implementation by itself;
- close `OPEN-REL-030` or fabricate telemetry conformance evidence;
- select TimescaleDB, broker, cache, KMS, secret manager, cloud or orchestrator;
- move Alerting, ITSM acknowledgement/incident or AIOps ownership into Monitoring;
- force high-volume raw metric history through the general event broker;
- create a mutable `dashboard` domain;
- make Zabbix identifiers, severity, tags, acknowledgement, groups or clocks platform authority.

## Domain ownership

Monitoring owns:

```text
monitoring_source
monitoring_resource
metric_definition
metric_current_state
metric_observation
problem
health_projection
monitoring_sync_operation
provider external-reference mappings
synchronization/checkpoint/completeness evidence
```

Monitoring consumes trusted `TenantContext`, current placement/admission authority and provider-adapter evidence. It does not consume caller-supplied physical routing or provider-native tenant authority.

Monitoring does not own credentials/session authority, membership/role policy, Alerting lifecycle, ITSM lifecycle, AIOps findings, provider credential secret bytes or telemetry-store topology.

## Canonical identities

### Monitoring source

```text
monitoring_source_id = stable opaque JLMIRROR logical source identity
```

The source ID survives ordinary configuration and explicit provider-instance replacement. It identifies the logical configured source, not a URL/server/cell/database.

The source separately carries:

```text
provider_profile
source_instance_generation
configuration_revision
credential_binding_ref
configured_provider_scope
```

For Zabbix, `source_instance_generation` is `zabbix_instance_generation`.

### Provider-instance generation is an identity-domain boundary

Provider-native IDs are scoped by at least:

```text
tenant_id
monitoring_source_id
provider_profile
source_instance_generation
```

The same provider-native value in another tenant/source/generation is unrelated.

For the **initial Zabbix profile**, a successor `zabbix_instance_generation` establishes a distinct provider external-identity domain. Reused `hostid`, `itemid`, `triggerid` or `eventid` values across generations MUST project as independent generation-scoped mappings and MUST NOT be merged merely because native IDs, names, addresses or configuration look similar.

A future Product need may define an explicit cross-generation migration/linkage process, but it must preserve historical generation identity and requires a separately accepted identity-migration contract. This initial profile does not reuse canonical resource/metric/problem identity across generations as an implicit convenience.

### Monitoring resource

```text
monitoring_resource_id = stable opaque JLMIRROR identity inside one accepted canonical mapping
```

Provider host/device IDs remain external references. Physical placement never participates in the ID.

### Metric definition

```text
metric_definition_id = stable opaque JLMIRROR identity inside one accepted canonical mapping
```

It belongs to one canonical Monitoring resource. Provider item/key IDs remain external references.

### Metric observation

```text
observation_identity_scope + observation_id
```

For Zabbix history the native component is `itemid + clock + ns`, additionally scoped by tenant/source/provider/source-instance generation.

`observed_at` is provider/event time; `accepted_at` is platform durable-acceptance time. Neither is universal current-state ordering authority.

### Problem

```text
problem_id = stable opaque JLMIRROR identity inside one generation-scoped provider mapping
```

Provider event IDs remain external references.

### Health projection

Resource health is keyed by canonical `monitoring_resource_id` plus an opaque projection revision. It is derived Monitoring state, not provider identity.

### Synchronization operation

```text
monitoring_sync_operation_id = stable opaque operation identity
```

The operation follows common long-running-operation semantics. Its ID/URL is never bearer authority.

## Source semantics

Required logical source state:

```text
monitoring_source_id
provider_profile
source_instance_generation
configuration_revision
display_name
provider endpoint/configuration reference
credential_binding_ref
configured_provider_scope
operational_evidence_state
last_successful_sync_at
last_attempt_at
last_sync_operation_id
created_at
updated_at
```

Raw credential bytes are not ordinary Monitoring state.

Canonical operational evidence state:

```text
current
stale
incomplete
reconciliation_required
unavailable
```

This is a domain-facing projection of synchronization trust. It cannot invent successful/current evidence when Phase 11 dependency authority is stale or unavailable.

## Resource presence

`monitoring_resource` includes:

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
display_name
resource_kind
presence_state
external_references
last_observed_at
last_confirmed_present_at
created_at
updated_at
```

`presence_state` is only:

```text
present
removed
```

There is deliberately no `missing == removed` state transition. Provider failure, missing scope, truncated snapshot, permission loss or recovery uncertainty leaves prior presence intact while evidence state degrades. `removed` requires accepted authoritative negative evidence.

## Metric definition and current metric state

`metric_definition` includes:

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
name
value_kind
unit
definition_state
external_references
created_at
updated_at
```

Canonical `value_kind`:

```text
number
integer
boolean
string
text
log
```

`definition_state`:

```text
active
retired
```

Retirement follows authoritative negative-evidence rules.

### `metric_current_state`

`FR-MON-003` requires an efficient current-state view distinct from high-volume history. Monitoring therefore owns a current metric projection per active metric definition:

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
current_observation_id
observed_at
accepted_at
value_kind
value
evidence_state
projection_revision
last_changed_at
```

This projection is not reconstructed by asking the historical store for “latest row” on each user request. It is maintained under the owner/provider current-state fencing contract and is queryable alongside the metric definition.

A later poll generation is **precedence/fence authority**, not semantic novelty. Re-observing the same canonical current observation/meaning does not advance `last_changed_at`, does not create a duplicate transition and does not emit another `current-state-changed` obligation just because the poll generation increased.

A genuinely different current observation may advance under a later valid fenced poll even if provider event time moved backwards.

If current provider evidence becomes stale/incomplete/reconciliation-required/unavailable, the last-known current value may remain visible with non-current `evidence_state`; it cannot masquerade as freshly proven current truth.

## Historical metric observation

`metric_observation` is immutable after canonical durable acceptance:

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

Every newly accepted observation owns one historical-projection obligation independent from whether it becomes `metric_current_state`.

Historical/backfill acceptance never gains current-state authority merely from later acceptance order or numerically larger provider timestamp.

Correction/recovery is modeled through explicit new/reconciled authority rather than silently rewriting an accepted observation's identity/value.

## Problems

Canonical `problem_state`:

```text
active
resolved
```

Canonical `severity_class`:

```text
unknown
informational
warning
degraded
critical
```

Problem logical fields include:

```text
problem_id
monitoring_source_id
source_instance_generation
monitoring_resource_id(s)
summary
problem_state
severity_class
opened_at
resolved_at
last_confirmed_at
external_references
bounded provider_metadata
```

`resolved` requires affirmative provider evidence or accepted complete/object-specific negative evidence. Uncertainty never resolves a problem.

Provider acknowledgement is metadata only and does not acknowledge/resolve Monitoring, Alerting or ITSM state. Provider tags are bounded metadata/evidence only unless a later accepted mapping promotes a specific namespace. Neither can choose tenant, authorization, placement or canonical identity.

## Health projection

Canonical `health_class`:

```text
unknown
healthy
degraded
unhealthy
```

A projection exposes:

```text
monitoring_resource_id
health_class
evidence_state
projection_revision
source_instance_generation
last_changed_at
last_evidence_at
bounded problem/reason references
```

Provider-neutral derivation is conservative:

- no trustworthy current evidence -> `unknown`, or last-known class with a non-current `evidence_state`;
- current complete evidence with no active health-affecting problem -> `healthy`;
- active `warning` or `degraded` problem -> at least `degraded`;
- active `critical` problem -> `unhealthy`;
- active `unknown`-severity problem cannot prove `healthy`;
- `informational` alone does not force degradation.

Multiple active problems combine by the strongest canonical health effect. Provider severity itself is not the health enum.

## Zabbix normalization destination

The companion `zabbix-monitoring-normalization-profile.md` instantiates these canonical classes.

Initial severity mapping:

| Zabbix | JLMIRROR |
|---|---|
| Not classified | `unknown` |
| Information | `informational` |
| Warning | `warning` |
| Average | `degraded` |
| High | `critical` |
| Disaster | `critical` |

Provider-native severity may be retained as bounded external evidence. Zabbix acknowledgement/tags remain provider metadata only.

Zabbix logical value classes map to `number`, `integer`, `string`, `text`, `log`; boolean is used only where an explicit metric-definition mapping establishes boolean semantics rather than assuming every `0/1` is boolean.

## Synchronization operation

A Monitoring sync operation records progress/reconciliation but never becomes provider fact authority. It includes common operation state plus:

```text
monitoring_sync_operation_id
monitoring_source_id
source_instance_generation
trigger_class
last safe checkpoint/reference
safe failure/degradation class
correlation_id
```

`trigger_class` may identify schedule, configuration change, explicit instance replacement, webhook hint or recovery/reconciliation. It is diagnostic metadata, not execution authorization.

## Source mutation semantics

### Create

Creation atomically establishes a new logical source, first source-instance generation, configuration revision, provider profile/config/scope, credential reference, audit intent and durable responsibility for validation/synchronization when the ingestion implementation is activated.

No provider network call is held inside the ordinary local source transaction.

### Ordinary edit

Ordinary edit may change only fields that do not redefine provider-instance identity, such as display metadata, credential-binding rotation and profile-permitted configured scope.

It requires current authorization, optimistic concurrency and mutation idempotency at the API boundary.

For Zabbix, base-URL change is prohibited here.

### Replace instance

Explicit replacement:

1. requires current source-management authorization, optimistic concurrency and idempotency;
2. fences prior provider-instance/poll writer authority;
3. atomically advances `source_instance_generation` and source revision;
4. binds successor endpoint/credential/scope configuration;
5. persists required audit evidence;
6. creates exactly one durable successor synchronization/reconciliation responsibility;
7. does not merge old/new provider IDs or delete old historical evidence.

Provider validation runs outside the local transaction. Failure/ambiguity after commit degrades/reconciles the successor; it does not silently resurrect the retired generation.

## Current-state fencing

Provider profiles provide ordering/fencing authority. Zabbix uses:

```text
(source_instance_generation, zabbix_poll_epoch, zabbix_poll_generation)
```

The token decides whether a candidate is eligible against stale writers. It does not create semantic change by itself.

Poll epoch continuity across PITR/failover/relocation follows the accepted `(R,F]` and placement-fence model. A restored/local-lower sequence cannot make itself current.

## Negative evidence

`uncertainty != absence` is normative.

None of these alone prove remove/retire/resolve:

```text
provider timeout/unavailability
authentication/permission failure
missing configured scope anchor
truncated/limited/failed page
incomplete snapshot
stale/lost-fence poll
restore without continuity proof
missing row under uncertain visibility
```

`removed`, `retired` and `resolved` require a provider-profile accepted negative-evidence class: complete current-scope evidence, bounded authenticated object-specific reconciliation or a stronger explicit provider primitive.

The negative transition and required audit/transition signal intent are atomic. Recovery cannot restore stale snapshot-complete/visibility markers as current authority.

## Historical completeness and gaps

Historical telemetry exposes what JLMIRROR can prove.

If late provider insertion, retention loss, restore uncertainty or another gap prevents completeness, Monitoring records explicit incomplete/gap/reconciliation evidence. A fast high-water mark is only a freshness optimization and never permanent completeness proof.

## Event/outbox boundary

```text
new canonical observation accepted
  -> exactly one historical-projection obligation

semantic current-state transition
  -> stable transition identity + current-state-changed obligation
```

The second is not emitted for an identical repeated current observation.

High-volume raw observations are not required to traverse the general integration-event broker. Physical dispatch remains Phase 10/C2 implementation authority.

## Dashboard boundary

Monitoring dashboards are a Product outcome composed from Monitoring inventory, current metric state, health, problems, history and sync evidence.

BFF/read composition may build the initial view. Persistent presentation-oriented/cross-domain dashboard projections remain Reporting & Experience ownership and do not gain Monitoring mutation ownership.

## Authorization

Stable actions, not fixed roles:

```text
monitoring.source.read
monitoring.source.manage
monitoring.resource.read
monitoring.metric.read
monitoring.problem.read
monitoring.health.read
monitoring.sync.read
```

Organization & Access maps roles/custom roles to actions/resource scope. Provider group/tag/severity/ack fields never select actions or scope.

## Security/privacy

- every pooled protected row uses immutable tenant identity and accepted RLS/tenant isolation;
- provider endpoint/config/external references are protected metadata;
- raw credential bytes are not ordinary Monitoring state;
- metric/log/text/problem/provider metadata may contain sensitive customer data and inherit classification/redaction/retention;
- provider strings are untrusted data and are bounded/safely encoded;
- logs/traces do not emit unrestricted observation/problem payloads or credentials;
- tenant/provider cardinality, history, webhook hints, reconciliation and backlog are bounded/attributable.

## Recovery/relocation

Before recovered/relocated Monitoring write authority resumes, applicable source generation, poll authority, observation acceptance, historical projection, current metric state, sync/checkpoint, negative evidence and transition/outbox continuity is reconciled through `(R,F]`.

Missing state is uncertainty, not permission to reaccept/retry/remove/resolve. A retired-placement writer cannot become current merely because it can still reach the provider.

## Capacity dimensions

Implementation measures/bounds at least:

```text
tenants/cell
sources/tenant
resources/source
metrics/resource
current-metric projection size
observation ingest/cardinality
history retention/query window
problem volume
sync/reconciliation/backfill backlog
provider limits
per-tenant skew/noisy-neighbor pressure
```

Production numerics remain C3/evidence-driven; `OPEN` never means unbounded.

## Compatibility-sensitive semantics

Breaking/security-sensitive changes include identity scope, cross-generation mapping, source replacement, current-state fencing/idempotency, current metric state meaning, observation value representation, negative evidence, problem severity/health/evidence vocabularies, provider metadata authority, history completeness or domain ownership.

## Validation / falsification vectors

Before implementation conformance:

1. Tenant A cannot read/mutate Tenant B Monitoring state using known B IDs.
2. Same Zabbix native IDs in two tenants/sources/generations remain independent mappings.
3. Ordinary edit cannot change Zabbix base URL.
4. Concurrent replacement produces one successor generation/responsibility; stale competitor loses.
5. Stale poll/placement cannot mutate current state.
6. Provider clock rollback does not freeze a genuinely newer current observation.
7. Same current observation under a later poll emits no duplicate semantic transition.
8. Current metric reads use `metric_current_state`, not per-request “latest history row” inference.
9. History/backfill acceptance does not grant current authority.
10. Incomplete/visibility-degraded snapshots never remove/retire/resolve by omission.
11. PITR/relocation cannot revive stale negative-evidence/poll authority.
12. Observations are immutable and historical projection is idempotent by canonical identity.
13. Accepted non-latest observations still retain historical-projection obligation.
14. Historical gap/late-arrival uncertainty is explicit.
15. Provider acknowledgement/tags cannot mutate Alerting/ITSM/authorization.
16. Zabbix severity maps only to canonical classes and retains native severity only as external evidence.
17. One tenant's provider failure/backlog does not stall unrelated tenant synchronization.
18. Logs/traces/errors contain no credential secret or unrestricted sensitive observation payload.

## Remaining OPENs / blockers

Semantic ownership above is fixed by this proposed contract; mechanism/numeric choices remain:

- `OPEN-REL-030` C2 customer-monitoring durable acceptance/projection conformance;
- Tier 2 telemetry-store selection/conformance;
- secret-manager/KMS/credential-binding mechanism;
- broker/outbox physical dispatch mechanism;
- provider timeout/retry/page/history/backfill/reconciliation numerics;
- production capacity/retention/SLO/RPO/RTO numerics.

The next distinct governance track is the bounded C2 evidence spike after this contract package is accepted. Candidate spike code is not canonical by existing.
