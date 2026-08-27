# Monitoring Domain Contract — Wave 4 Entry

**Status:** proposed baseline  
**Owner:** Monitoring bounded context  
**Wave:** 4 — Product/domain vertical-slice prerequisite  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001`, `AC-003`, `AC-006`, `AC-012`, ADR-008, ADR-009, ADR-013, ADR-019, `docs/08-data/telemetry-plane.md`, `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md`, `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`

## Purpose

This document closes the Monitoring **domain/use-case semantics** required by the Wave 4 entry rule before implementation code is allowed to invent them.

The accepted Product already requires Monitoring-source integration, resource/device normalization, current state, metric definitions and samples, health, problems, synchronization, monitoring dashboards and tenant-independent failure containment. The accepted bounded-context and data documents already assign those concepts to Monitoring. What was still missing was the exact contract between those product requirements and an implementable vertical slice: canonical identities, lifecycle meaning, provider-evidence treatment, source replacement, current-state semantics, historical-observation semantics, negative evidence, problem/health normalization and synchronization ownership.

This document supplies that missing domain layer. The HTTP representation is defined separately by `docs/09-api-contracts/monitoring-domain-api-contract.md`.

## Non-goals and authority limits

Acceptance of this contract does **not**:

- authorize Wave 4 implementation by itself;
- close `OPEN-REL-030` or claim that customer-telemetry conformance evidence exists;
- select TimescaleDB, a broker, cache, KMS, secret manager, orchestrator, cloud or queue product;
- create Alerting, ITSM acknowledgement, notification, incident or AIOps ownership inside Monitoring;
- force raw/high-volume metric observations through the general integration-event broker;
- create a mutable `dashboard` domain; Monitoring dashboards may compose the read contracts below, while a dedicated cross-domain/dashboard projection remains Reporting & Experience ownership;
- make Zabbix identifiers, severities, tags, acknowledgement flags, host groups or trigger vocabulary canonical platform identity/authorization.

Implementation remains subordinate to accepted Product, Security, Quality, ADR, System/Data and Phase 09/10 semantics.

## Domain boundary

Monitoring owns:

```text
monitoring_source
monitoring_resource
metric_definition
metric_observation
problem
health_projection
monitoring_sync_operation
monitoring synchronization/checkpoint evidence
provider external-reference mappings
```

Monitoring consumes trusted `TenantContext`, current placement/admission authority and provider-adapter input. It does not consume caller-supplied physical routing or provider-native tenant authority.

Monitoring does not own:

```text
identity credentials / session authority
membership / permission policy definitions
alert lifecycle / notification policy
ITSM incident or ticket lifecycle
AIOps findings
provider credential secret bytes
physical telemetry-store topology
```

## Canonical identity rules

All protected domain identities are tenant-scoped logical identities and remain independent from provider/native and physical placement identity.

### Monitoring source

```text
monitoring_source_id = stable opaque JLMIRROR identity
```

`monitoring_source_id` remains stable across ordinary configuration edits and explicit provider-instance replacement. It identifies the configured logical Monitoring Source, not a particular database row, worker, URL, Zabbix server or cell.

The source also carries:

```text
provider_profile                e.g. zabbix
source_instance_generation      monotonic logical generation within the source
configuration_revision          opaque optimistic-concurrency revision
credential_binding_ref          secret-reference identity only; never secret bytes in normal reads
configured_provider_scope       bounded provider-specific scope through adapter-owned representation
```

For the Zabbix profile, `source_instance_generation` is the accepted `zabbix_instance_generation`.

### Monitoring resource

```text
monitoring_resource_id = stable opaque JLMIRROR identity
```

A provider-native host/device/resource identifier is only an external reference scoped by at least tenant, monitoring source, provider profile and provider-instance generation. The same provider-native value in two source generations does not prove the same resource.

Cross-generation continuity may preserve an existing `monitoring_resource_id` **only** when an explicit reconciliation rule establishes equivalence from trusted evidence. In the absence of such proof, the new generation receives a distinct canonical mapping rather than silently joining colliding provider identity domains.

### Metric definition

```text
metric_definition_id = stable opaque JLMIRROR identity
```

A definition belongs to one canonical Monitoring resource and describes the canonical value representation/unit metadata used by its observations. Provider item IDs/keys remain external references and cannot replace `metric_definition_id`.

### Metric observation

```text
observation_identity_scope + observation_id
```

The provider adapter supplies the stable scoped observation identity accepted by `telemetry-plane.md`. For Zabbix history, the provider-specific native component is `itemid + clock + ns`, additionally scoped by tenant/source/provider/source-instance generation.

`observed_at` is provider/event-time evidence. `accepted_at` is platform durable-acceptance time. Neither field, by itself, is a universal current-state ordering authority.

### Problem

```text
problem_id = stable opaque JLMIRROR identity
```

Provider event IDs are external references scoped to the source generation. The same numeric/native event ID in another tenant/source/generation is unrelated.

### Health projection

A health projection is owned by Monitoring and keyed by canonical resource identity plus an opaque projection revision. It is derived state, not a new source of provider truth.

### Synchronization operation

```text
monitoring_sync_operation_id = stable opaque operation identity
```

A sync operation follows the accepted common long-running-operation semantics. Its ID/URL is lookup identity, never bearer authority.

## Core resource semantics

### `monitoring_source`

Required logical fields:

```text
monitoring_source_id
provider_profile
source_instance_generation
configuration_revision
display_name
provider_endpoint_reference/configuration
credential_binding_ref
configured_provider_scope
operational_evidence_state
last_successful_sync_at
last_attempt_at
last_sync_operation_id
created_at
updated_at
```

`provider_endpoint_reference/configuration` is protected configuration data. Raw credentials are never part of ordinary Monitoring resource representation, logs, audit snapshots, events or query strings.

The initial operational evidence vocabulary is:

```text
current
stale
incomplete
reconciliation_required
unavailable
```

This vocabulary describes whether Monitoring can currently rely on synchronized provider evidence. It does not replace Phase 11 capability/dependency health profiles; implementation maps those richer reliability states into this domain-facing projection without inventing successful synchronization.

### `monitoring_resource`

Required logical fields:

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
display_name
resource_kind
presence_state
external_references (bounded/protected metadata)
last_observed_at
last_confirmed_present_at
created_at
updated_at
```

`presence_state` is:

```text
present
removed
```

There is deliberately no `missing == removed` shortcut. Temporary absence, provider failure, truncated snapshot, lost visibility or unresolved recovery leaves the resource's prior presence state intact while source/synchronization evidence becomes stale/incomplete/reconciliation-required. `removed` requires accepted authoritative negative evidence.

### `metric_definition`

Required logical fields:

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
name
value_kind
unit (nullable)
definition_state
external_references (bounded/protected metadata)
created_at
updated_at
```

Initial `value_kind` is a closed canonical enum:

```text
number
integer
boolean
string
text
log
```

Provider adapters convert provider-native value classes into this enum. Adding a new value kind is a representation/compatibility change and is not silently inferred from provider SDK types.

`definition_state` is:

```text
active
retired
```

Retirement follows the same authoritative-negative-evidence rules as resource removal.

### `metric_observation`

Required logical fields:

```text
observation_id
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
observed_at
accepted_at
value
value_kind
```

`value` is a tagged value whose JSON representation must match `value_kind` under the Phase 09 representation contract. An observation is immutable after canonical durable acceptance. Correction of bad provider evidence creates new/reconciled authority according to the provider/domain recovery contract; it does not silently rewrite historical identity.

Every newly durably accepted observation owns exactly one historical-projection obligation. Whether that observation becomes current/latest state is a separate decision.

### `problem`

Required logical fields:

```text
problem_id
monitoring_source_id
source_instance_generation
monitoring_resource_id(s)
summary
problem_state
severity_class
opened_at
resolved_at (nullable)
last_confirmed_at
external_references (bounded/protected metadata)
provider_metadata (bounded/non-authoritative optional evidence)
```

`problem_state` is:

```text
active
resolved
```

`resolved` requires affirmative provider evidence or authoritative complete/individually revalidated negative evidence under the provider contract. Uncertainty never resolves a problem.

Canonical `severity_class` is:

```text
unknown
informational
warning
degraded
critical
```

Severity is operational classification, not authorization and not Alerting lifecycle. Provider adapters map their native scale into this finite vocabulary. Provider-native severity remains optional bounded external evidence.

Provider acknowledgement flags do **not** become JLMIRROR problem/alert/incident acknowledgement. They may be retained as bounded `provider_metadata` for diagnosis but cannot mutate Alerting or ITSM state.

Provider tags/labels are likewise bounded provider metadata unless a later accepted domain contract promotes a specific normalized label into platform semantics. Tags never select tenant, authorization, placement or trusted routing.

### `health_projection`

Required logical fields:

```text
monitoring_resource_id
health_class
evidence_state
projection_revision
source_instance_generation
last_changed_at
last_evidence_at
reason/problem references (bounded)
```

Canonical `health_class` is:

```text
unknown
healthy
degraded
unhealthy
```

`evidence_state` uses the source evidence vocabulary (`current`, `stale`, `incomplete`, `reconciliation_required`, `unavailable`). A last-known health value may remain visible for operator context while `evidence_state != current`; callers must not interpret the last-known value as freshly proven provider truth.

Initial provider-neutral derivation rules are deliberately conservative:

- no trustworthy current evidence -> `health_class=unknown` or a last-known class with non-current `evidence_state`;
- current evidence with no active health-affecting problem -> `healthy`;
- active `warning` or `degraded` problem -> at least `degraded`;
- active `critical` problem -> `unhealthy`;
- active `unknown`-severity problem cannot be used to prove `healthy`; the projection is at least `unknown` unless stronger current domain evidence establishes a class;
- `informational` problems do not by themselves require degradation.

Multiple problems combine by the most severe canonical health effect. A later richer health policy may refine this mapping only through an explicit compatibility-reviewed domain change; provider severity is never allowed to become the canonical health enum directly.

### `monitoring_sync_operation`

The operation records synchronization/reconciliation progress without becoming the authority for provider facts. Logical metadata includes:

```text
monitoring_sync_operation_id
monitoring_source_id
source_instance_generation
trigger_class
operation state/progress from common long-running-operation contract
started_at
updated_at
completed_at (nullable)
last_safe_checkpoint/reference
failure/degradation class (safe, non-secret)
correlation_id
```

`trigger_class` may distinguish system schedule, source configuration change, explicit instance replacement, webhook hint and recovery/reconciliation. This is diagnostic/operational metadata; it does not grant execution authority.

## Configuration mutation semantics

### Create source

Creating a Monitoring Source atomically establishes:

- new `monitoring_source_id`;
- `source_instance_generation = 1` (or equivalent first generation);
- initial configuration revision;
- provider profile, endpoint reference/configuration and configured provider scope;
- credential **reference/binding**, never raw secret in ordinary persisted domain fields;
- immutable audit intent required by governance;
- durable responsibility to perform provider validation/synchronization when the accepted implementation activates ingestion.

No provider network call is part of the ordinary local source-creation transaction.

### Ordinary source edit

Ordinary edit may change only configuration that does not redefine provider-instance identity, such as display metadata, credential binding rotation and provider scope configuration permitted by the provider profile.

It uses optimistic concurrency (`If-Match`/opaque revision at the API layer), current authorization and audit.

For Zabbix, changing the base URL is prohibited through ordinary edit.

### Replace source instance

Provider-instance replacement is an explicit governed command. It:

1. requires current source-management authorization and optimistic-concurrency precondition;
2. requires request idempotency;
3. fences prior poll/current-state writer authority;
4. atomically advances `source_instance_generation` and source configuration revision;
5. binds the new provider endpoint/credential/scope configuration to the successor generation;
6. creates durable synchronization/reconciliation responsibility for the successor generation;
7. never treats old provider IDs as equivalent to the new generation without explicit mapping evidence;
8. never deletes old historical evidence merely because the current source generation changed.

If external validation of the successor provider is unavailable or ambiguous, the local generation/configuration outcome remains whatever the committed domain command records; synchronization enters the corresponding unavailable/reconciliation state. An HTTP/network failure after commit cannot roll the authoritative generation backward implicitly.

## Provider normalization contract

Provider adapters terminate provider vocabulary before domain ownership.

For each provider profile, normalization must prove:

```text
trusted integration/source identity
source instance generation
canonical resource mapping
canonical metric definition/value kind
canonical observation identity
canonical problem lifecycle + severity class
health evidence inputs
sync/checkpoint evidence
```

Provider identity is evidence, never tenant authority.

### Zabbix severity normalization

The initial Zabbix profile maps Zabbix trigger/problem severity into the canonical `severity_class` as follows:

| Zabbix severity | JLMIRROR `severity_class` |
|---|---|
| Not classified | `unknown` |
| Information | `informational` |
| Warning | `warning` |
| Average | `degraded` |
| High | `critical` |
| Disaster | `critical` |

The mapping is intentionally many-to-one. JLMIRROR retains provider-native severity as optional external evidence when authorized, so losing provider-scale granularity in the canonical operational class does not destroy diagnostic provenance.

A provider acknowledgement field remains provider metadata only. Zabbix tags remain bounded provider metadata/labels only; neither is promoted to Alerting/ITSM state, tenant authority, permission scope or canonical resource identity.

## Current-state authority and semantic idempotency

Current-state projection uses the ordering/fencing authority defined by the provider profile. For Zabbix, that is:

```text
(source_instance_generation, zabbix_poll_epoch, zabbix_poll_generation)
```

The poll token determines whether a candidate is eligible to win against stale writers. It does not create semantic change on its own.

If a later valid poll observes the same canonical current observation/meaning already applied, current-state projection is idempotent and emits no duplicate `current-state-changed` transition merely because the poll generation advanced.

A genuinely different current observation may advance under the later fenced poll even if provider event time moved backwards.

Historical/backfill arrival never gains current-state authority solely from a larger timestamp or later platform acceptance order.

## Negative evidence and removal/resolution

`uncertainty != absence` is normative domain behavior.

The following never prove removal/resolution by themselves:

- provider timeout/unavailability;
- authentication/permission failure;
- missing provider scope anchor;
- truncated/limited/failed page;
- incomplete snapshot;
- stale poll/writer;
- restored checkpoint without continuity proof;
- absent row in a provider result whose visibility/coverage is uncertain.

`monitoring_resource.presence_state=removed`, `metric_definition.definition_state=retired` or `problem.problem_state=resolved` may be committed only when the provider profile supplies an accepted authoritative negative-evidence class, including complete current-scope evidence or object-specific authenticated reconciliation as applicable.

A destructive/resolve transition and its audit/transition signal intent are atomic under the owning transaction boundary. Recovery cannot revive an old snapshot-complete marker or retired writer generation as current evidence.

## Historical completeness and gaps

Historical telemetry exposes **what JLMIRROR can prove**, not an invented continuous timeline.

Every supported historical region is classified through accepted checkpoint/reconciliation evidence. If late provider insertion, retention loss, restore uncertainty or an unrecoverable gap prevents completeness, Monitoring records explicit incomplete/gap evidence. APIs expose that state rather than returning a page that implies the requested interval is fully known.

A fast cursor/high-water mark may optimize freshness; it is never permanent completeness proof.

## Event and outbox boundary

The following separation is mandatory:

```text
new canonical observation accepted
  -> one historical-projection obligation

semantic current-state transition
  -> transition identity + current-state-changed obligation
```

The second obligation is not emitted for an identical repeated current observation.

High-volume raw metric history is **not required to be published through the general integration-event broker**. A later Alerting/AIOps/Reporting consumer receives deliberately contracted normalized transition/event/read-model inputs, not provider-native raw streams by default.

This contract does not select the physical dispatch transport. ADR-008/009 and Phase 10 remain authoritative.

## Dashboard boundary

`CAP-MONITORING`/`FR-MON-005` require monitoring dashboards as a product outcome. The initial domain contract satisfies the Monitoring-owned data side through inventory, health, problems and bounded metric-history queries.

A browser/BFF may compose those read contracts into a Monitoring view. A persistent dashboard/read model becomes Reporting & Experience ownership when it stores presentation-oriented cross-resource/cross-domain projection state. Monitoring does not gain a generic mutable dashboard aggregate merely to satisfy UI composition.

## Authorization boundary

Monitoring exposes stable **policy actions**, not hard-coded roles. Roles/custom roles remain Organization & Access ownership.

Initial action vocabulary:

```text
monitoring.source.read
monitoring.source.manage
monitoring.resource.read
monitoring.metric.read
monitoring.problem.read
monitoring.health.read
monitoring.sync.read
```

The API/domain service asks the current authorization authority whether the principal may perform the action in the current tenant/resource scope. This vocabulary does not prescribe which named role receives an action.

Provider-native group/tag/severity/acknowledgement fields never choose policy action or scope.

## Transaction and effect boundaries

- source configuration mutations are ordinary local authoritative transactions with required audit intent and any accepted outbox obligation;
- provider HTTP calls occur outside ordinary local database transactions;
- customer observation durable acceptance/projection remains blocked on `OPEN-REL-030` conformance;
- current-state transition + stable transition identity + required signal/outbox intent are atomic;
- source replacement fences prior generation/writer authority before successor current-state mutation is eligible;
- ambiguous or incomplete provider reads create degraded/reconciliation state, not invented success/absence;
- provider failure for Tenant A is isolated from unrelated tenant progress.

## Recovery and relocation

Monitoring inherits `(R,F]` recovery continuity and tenant placement fencing.

Before recovered/relocated Monitoring write authority resumes, applicable source-generation, poll-epoch/generation, accepted-observation, historical-projection, current-state, sync/checkpoint, negative-evidence and transition/outbox continuity is reconciled.

Missing state after restore is uncertainty, not permission to reaccept/retry/resolve/remove blindly.

A source-cell writer from a retired placement cannot become current merely because it can still reach the provider.

## Security and privacy

- every pooled protected row includes immutable tenant identity and accepted tenant isolation/RLS defenses;
- provider endpoint/configuration and external references are protected metadata;
- credential secret bytes are not ordinary Monitoring state;
- metric/log/text values may contain confidential/restricted customer data and inherit data-classification/redaction/retention controls;
- provider tags, names and problem text are untrusted external data and are bounded/escaped under output and observability contracts;
- normal logs/traces never emit unrestricted metric/log/problem payloads or credentials;
- one tenant/provider cannot use cardinality, history, webhook hints or sync backlog to consume unbounded unrelated capacity.

## Capacity and cost

Correctness is independent of current scale, but implementation must support the dimensions already accepted by ADR-019 and capacity overlays:

```text
tenants/cell
sources/tenant
resources/source
metric definitions/resource
observation ingest rate/cardinality
history retention/query window
active/historical problems
sync/backfill/reconciliation backlog
provider API limits
per-tenant skew/noisy-neighbor pressure
```

Exact production numerics remain C3/evidence decisions. Absence of accepted numbers never means unbounded requests, unbounded history queries, unbounded provider pages or unbounded recovery work.

## Compatibility

Breaking changes include, at minimum:

- changing canonical identity scope;
- treating provider ID as platform identity;
- changing `presence_state`, `problem_state`, `severity_class`, `health_class`, `evidence_state` meaning;
- changing source-instance replacement/generation semantics;
- changing negative-evidence eligibility;
- changing current-state ordering/fencing semantics;
- changing observation identity/value representation;
- turning provider acknowledgement/tag metadata into domain authority;
- changing historical completeness/gap semantics;
- changing which domain owns dashboard, alert or incident state.

Such changes require owning-contract compatibility review even when database/API shapes remain syntactically compatible.

## Validation / falsification vectors

Before a Monitoring implementation slice can claim conformance, tests must prove at least:

1. Tenant A cannot read/mutate Tenant B source/resource/metric/problem/health/sync state using known B identifiers.
2. The same provider-native host/item/event ID in two tenants/sources/source generations never aliases canonical identity.
3. Ordinary source edit cannot change a provider-identity-defining field that the provider profile reserves for explicit replacement.
4. Concurrent source replacement uses optimistic concurrency/idempotency and produces one successor generation/effect responsibility.
5. A stale prior poll cannot mutate current state after losing its fence/placement authority.
6. A provider clock rollback does not freeze newer current state.
7. Re-reading the same current observation under a later poll generation emits no duplicate semantic transition.
8. History/backfill acceptance does not by itself grant current-state authority.
9. Incomplete/truncated/visibility-degraded snapshots never remove/retire/resolve by omission.
10. Recovery/PITR/relocation cannot restore stale negative-evidence or poll authority.
11. A metric observation is immutable and historical projection is idempotent by canonical identity.
12. Accepted observations that do not advance current state still retain historical projection obligation.
13. Historical gaps/late-arrival uncertainty are represented explicitly, never silently hidden behind a high-water mark.
14. Provider acknowledgement/tag fields cannot mutate Alerting/ITSM state or authorization.
15. Zabbix severity normalization produces only the canonical severity enum and preserves native severity as external evidence when retained.
16. Provider failure/backlog for one tenant cannot stall unrelated tenant synchronization.
17. Logs/traces/errors contain no provider credential secret or unrestricted sensitive metric/log payload.

## Remaining OPENs / implementation blockers

This domain contract intentionally leaves **mechanism/numeric** choices open while closing semantic ownership:

- `OPEN-REL-030` C2 customer-monitoring durable acceptance/projection conformance;
- Tier 2 telemetry-store selection/conformance;
- concrete secret-manager/KMS/credential-binding mechanism;
- concrete protected cursor implementation when activated by the API slice;
- broker/outbox physical dispatch mechanism;
- provider timeout/retry/page/history/backfill/reconciliation numerics;
- production capacity/retention/SLO/RPO/RTO numerics.

Those OPENs cannot change the fixed semantics above. A bounded C2 evidence spike is the next distinct governance track; it does not make experimental code canonical by existing.
