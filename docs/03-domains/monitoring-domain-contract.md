# Monitoring Domain Contract — Wave 4 Entry

**Status:** proposed baseline  
**Owner:** Monitoring bounded context  
**Wave:** 4 — Product/domain vertical-slice prerequisite  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001`, `AC-003`, `AC-006`, `AC-012`, ADR-008, ADR-009, ADR-013, ADR-019, `docs/08-data/telemetry-plane.md`, `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md`, `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`

## Purpose

This document closes the Monitoring domain/use-case semantics that Wave 4 code is not allowed to invent: canonical identity, provider-instance replacement, source-generation lifecycle, configured scope, current metric state, historical observations, problem/health normalization, negative evidence, synchronization ownership, recovery and tenant authority.

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
monitoring_source_replacement_candidate
monitoring_resource
metric_definition
metric_current_state
metric_observation
problem
health_projection
monitoring_sync_operation
provider external-reference mappings
generation/scope/synchronization/checkpoint/completeness evidence
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
active_source_instance_generation
configuration_revision
scope_revision
credential_binding_ref
configured_provider_scope
```

For Zabbix, the active source-instance generation is the authoritative `zabbix_instance_generation`.

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

A replacement candidate may reserve a successor generation before activation, but that candidate generation is **not active authority**. Candidate validation cannot mutate tenant-facing current state, resolve/remove canonical objects, emit current-state transitions or supersede the active generation until the atomic cutover succeeds.

### Monitoring resource

```text
monitoring_resource_id = stable opaque JLMIRROR identity inside one accepted generation-scoped mapping
```

Provider host/device IDs remain external references. Physical placement never participates in the ID.

### Metric definition

```text
metric_definition_id = stable opaque JLMIRROR identity inside one accepted generation-scoped mapping
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
active_source_instance_generation
configuration_revision
scope_revision
display_name
active provider endpoint/configuration reference
credential_binding_ref
configured_provider_scope
operational_evidence_state
replacement_candidate_ref nullable
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

This is a domain-facing projection of synchronization trust. It cannot invent successful/current evidence when dependency authority is stale or unavailable.

## Source-generation operational lifecycle

Every generation-scoped Monitoring object derives an operational generation state from the authoritative source row:

```text
generation_state = active_generation | historical_generation
```

The value is **derived**, not a mass-updated lifecycle flag:

```text
object.source_instance_generation == source.active_source_instance_generation
  -> active_generation
otherwise
  -> historical_generation
```

Normative rules:

- a cutover changes the source's active-generation authority in one serialized transition; it SHALL NOT require rewriting every resource/metric/problem/health row from the prior generation;
- immediately after cutover, prior-generation objects are operationally historical by derivation even if their stored `presence_state`, `definition_state` or `problem_state` preserves the last provider fact observed before retirement;
- `historical_generation` is **not** equivalent to `removed`, `retired` or `resolved`; generation retirement cannot fabricate any of those provider/domain facts;
- prior-generation resources/problems/health/current-value projections remain available only under explicit historical/last-known semantics and current authorization/retention policy;
- prior-generation objects SHALL NOT participate in current inventory, current health, current metric-state, current problem/Alerting input, negative inference or provider synchronization unless a separately accepted migration/reconciliation contract explicitly grants such authority;
- current operational list/read composition defaults to the active generation; historical-generation inclusion is explicit and visibly classified;
- a direct lookup of a historical-generation canonical ID may return retained evidence, but the representation exposes `generation_state=historical_generation` and cannot describe it as currently monitored;
- a prior-generation problem may remain `problem_state=active` as historical evidence that it was unresolved when that generation retired; `generation_state=historical_generation` prevents it from masquerading as a current operational problem;
- prior-generation health/current-value projections preserve last-known evidence but have no current-authority meaning after cutover;
- the new active generation begins with incomplete/reconciliation-required current coverage until successor synchronization establishes new generation-scoped resources/metrics/problems/health evidence;
- replay/backfill for an historical generation may repair that generation's retained history only under accepted replay authority; it cannot regain current-state authority merely because it executes later.

This separation preserves history without forcing cross-generation identity reuse and makes cutover O(1) with respect to object cardinality.

## Configured scope is not provider absence

A source's configured provider scope is a JLMIRROR configuration boundary over what the adapter is allowed/expected to observe. Changing that scope is **not** provider negative evidence.

The active source generation carries a monotonic `scope_revision`. Resources and metric definitions expose a derived scope projection:

```text
scope_state = in_scope | out_of_scope
scope_projection_revision
scope_evidence_state = current | reconciliation_required
```

Normative rules:

- a scope edit atomically commits only the new source scope/configuration revision, required audit/transition intent and one durable bounded scope-reconciliation responsibility;
- a scope edit SHALL NOT require an O(number_of_resources + number_of_metrics) transaction that rewrites every affected object before the source mutation can commit;
- per-object scope projections may be materialized/reconciled asynchronously in bounded batches;
- for an **active-generation** object, a scope projection is authoritative as `current` only when it is proven against the source's current `scope_revision`, or an equivalent current deterministic scope evaluation proves the same result;
- a stale scope projection cannot authorize a positive `in_scope` claim, negative inference, fresh health/current-value claim or provider work merely because an old row still says `in_scope`;
- while active-generation scope membership has not been reconciled to the current source scope revision, the object exposes `scope_evidence_state=reconciliation_required` and current monitoring authority fails safe;
- historical-generation objects do not become subject to the successor/current generation's scope revision; their retained scope evidence is historical only and never current authority;
- removing a host group or equivalent selector may ultimately project affected active-generation objects as `out_of_scope` without rewriting their identity/history;
- `out_of_scope` preserves canonical identity, external mapping and retained history;
- scope exclusion alone MUST NOT mark a resource `removed`, a metric definition `retired`, or a problem `resolved`;
- active problems linked only to newly out-of-scope resources retain their last known state with non-current evidence until affirmative provider/domain evidence resolves them or governed retention removes their history;
- re-inclusion does not fabricate continuity: currentness is re-established only from provider evidence under the current scope revision;
- a scope edit cannot be laundered into an authoritative complete provider snapshot for objects no longer queried.

This distinction prevents an administrative filtering choice from being misrepresented as a fact about the monitored estate while keeping scope mutation bounded at enterprise cardinality.

## Resource presence

`monitoring_resource` includes:

```text
monitoring_resource_id
monitoring_source_id
source_instance_generation
display_name
resource_kind
scope_state
scope_projection_revision
scope_evidence_state
presence_state
external_references
last_observed_at
last_confirmed_present_at
created_at
updated_at
```

`generation_state` is derived at read/use time from source active-generation authority.

`presence_state` is only:

```text
present
removed
```

There is deliberately no `missing == removed` state transition. Provider failure, missing scope, truncated snapshot, permission loss, stale scope projection or recovery uncertainty leaves prior presence intact while evidence state degrades. `removed` requires accepted authoritative negative evidence while the object is within an evidence domain that can actually prove absence.

`scope_state=out_of_scope` is orthogonal to `presence_state`; `generation_state=historical_generation` is orthogonal to both.

## Metric definition

`metric_definition` includes:

```text
metric_definition_id
monitoring_resource_id
monitoring_source_id
source_instance_generation
name
value_kind
unit
scope_state
scope_projection_revision
scope_evidence_state
definition_state
external_references
created_at
updated_at
```

`generation_state` is derived at read/use time.

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

Retirement follows authoritative negative-evidence rules. Scope exclusion uses `scope_state=out_of_scope`; historical generation uses `generation_state=historical_generation`. Neither is retirement.

## Current metric state

`FR-MON-003` requires an efficient current-state view distinct from high-volume history. Monitoring therefore owns a current metric projection per accepted metric definition:

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

This projection is not reconstructed by asking the historical store for “latest row” on each user request. It is maintained under the owner/provider current-state fencing contract.

The API exposes current metric state through a **dedicated bounded current-state surface**. Metric-definition enumeration is metadata-oriented and does not have to carry every current value. BFF/dashboard composition may join definitions and current state after current authorization.

A later poll generation is **precedence/fence authority**, not semantic novelty. Re-observing the same canonical current observation/meaning does not advance `last_changed_at`, does not create a duplicate transition and does not emit another `current-state-changed` obligation merely because the poll generation increased.

A genuinely different current observation may advance under a later valid fenced poll even if provider event time moved backwards.

If current provider evidence becomes stale/incomplete/reconciliation-required/unavailable, the last-known current value may remain visible with non-current `evidence_state`; it cannot masquerade as freshly proven current truth.

A metric whose current scope cannot be proven under the current `scope_revision` cannot present its last value as currently monitored. A metric from `historical_generation` likewise cannot be presented as current regardless of its stored last-known evidence. Retained values may remain visible under authorized historical/last-known semantics with explicit generation/scope/evidence classification.

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

Every newly accepted observation owns one historical-projection obligation independent from whether it becomes current state.

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

`generation_state` is derived at read/use time.

`resolved` requires affirmative provider evidence or accepted complete/object-specific negative evidence. Uncertainty never resolves a problem. Scope exclusion, stale scope membership or generation retirement never resolves a problem by itself.

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

`generation_state` is derived at read/use time.

Provider-neutral derivation is conservative:

- no trustworthy current evidence -> `unknown`, or last-known class with a non-current `evidence_state`;
- current complete evidence with no active health-affecting problem -> `healthy`;
- active `warning` or `degraded` problem -> at least `degraded`;
- active `critical` problem -> `unhealthy`;
- active `unknown`-severity problem cannot prove `healthy`;
- `informational` alone does not force degradation;
- an object whose current scope cannot be proven cannot be advertised as freshly proven `healthy` merely from last-known evidence;
- a historical-generation projection has no current-health authority even if its last stored class was `healthy`.

Multiple active-generation active problems combine by the strongest canonical health effect. Provider severity itself is not the health enum.

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
source_instance_generation or candidate_generation
trigger_class
last safe checkpoint/reference
safe failure/degradation class
correlation_id
```

`trigger_class` may identify schedule, configuration change, scope reconciliation, replacement validation, replacement cutover, webhook hint or recovery/reconciliation. It is diagnostic metadata, not execution authorization.

## Source mutation semantics

### Create

Creation atomically establishes a new logical source, first active source-instance generation, configuration revision, initial scope revision, provider profile/config/scope, credential reference, audit intent and durable responsibility for validation/synchronization when the ingestion implementation is activated.

No provider network call is held inside the ordinary local source transaction.

A newly created source may remain `unavailable`/`reconciliation_required` until asynchronous provider validation succeeds; local creation success never claims external reachability.

### Ordinary edit

Ordinary edit may change only fields that do not redefine provider-instance identity, such as display metadata, credential-binding rotation and profile-permitted configured scope.

It requires current authorization, optimistic concurrency and mutation idempotency at the API boundary.

For Zabbix, base-URL change is prohibited here.

A configured-scope edit atomically advances the source `scope_revision`, commits the new scope definition, audit/transition intent and one durable scope-reconciliation responsibility. It does **not** synchronously rewrite every resource/metric row. Derived active-generation object scope projections reconcile in bounded batches and cannot claim current `in_scope` authority until proven against the new revision.

### Replace instance — staged candidate, then atomic cutover

Replacing the provider instance is intentionally **non-disruptive for a healthy active generation until the successor proves basic admissibility**.

A replacement request first creates or observes one durable replacement candidate:

```text
monitoring_source_id
candidate_generation
candidate_configuration_revision
candidate_scope_revision
candidate provider endpoint/configuration
candidate credential_binding_ref
candidate configured_provider_scope
candidate_state
validation_operation_id
created_at / updated_at
```

Candidate states are logically:

```text
validating
ready_for_cutover
validation_failed
reconciliation_required
activated
superseded
```

Candidate creation:

1. requires current source-management authorization, optimistic concurrency and idempotency;
2. reserves a collision-safe successor generation without making it active;
3. stores successor config/credential/scope references and required audit evidence;
4. creates exactly one durable bounded validation responsibility;
5. leaves the current active generation/configuration and its poll authority unchanged.

Candidate validation runs outside the ordinary source mutation transaction through the accepted outbound/SSRF boundary. It may perform bounded authenticated capability/scope checks required to prove the candidate can be used safely. Validation evidence is candidate-scoped and cannot mutate tenant-facing current resource/metric/problem/health truth.

A failed candidate does **not** fence or retire the active generation. Failure is durable/auditable and may be superseded by a new explicitly authorized replacement command.

Only a candidate with accepted current validation evidence is eligible for cutover. Cutover is one local serialized authority transition that:

1. re-establishes current source-management authorization when human authority participates in the delayed effect;
2. verifies expected current source revision, candidate identity/state and candidate validation generation/evidence;
3. fences prior active provider-instance/poll writer authority;
4. atomically advances `active_source_instance_generation` to candidate generation and installs successor config/scope/credential references;
5. advances source configuration and scope revisions;
6. records candidate `activated` and prior generation retirement/fence evidence;
7. persists required audit/transition intent;
8. creates exactly one durable successor synchronization/scope-reconciliation responsibility;
9. marks the source operational evidence at least `reconciliation_required` until successor current coverage is established;
10. never merges old/new provider-native mappings or deletes old historical evidence.

There is never more than one active source-instance generation. The active-generation pointer change immediately makes all prior-generation objects historical by derivation; no O(N) object rewrite is required. If cutover outcome is ambiguous across recovery/failure, admission remains reconciliation-required until active-generation/fence/audit/operation authorities prove the winner. A failed validation cannot silently activate, and recovery cannot silently reactivate the retired generation.

This staged design prevents a typo, bad credential or unreachable replacement endpoint from taking down an otherwise healthy source before the candidate has proved minimum admissibility.

## Current-state fencing

Provider profiles provide ordering/fencing authority. Zabbix uses:

```text
(active_source_instance_generation, zabbix_poll_epoch, zabbix_poll_generation)
```

The token decides whether a candidate observation is eligible against stale writers. It does not create semantic change by itself.

A replacement candidate that has not completed atomic cutover has no current-state write authority even if it can reach Zabbix successfully. An historical-generation poll/replay likewise has no current-state write authority.

Poll epoch continuity across PITR/failover/relocation follows the accepted `(R,F]` and placement-fence model. A restored/local-lower sequence cannot make itself current.

## Negative evidence

`uncertainty != absence` is normative.

None of these alone prove remove/retire/resolve:

```text
provider timeout/unavailability
authentication/permission failure
configured scope exclusion
stale/unreconciled scope projection
source-generation retirement
missing configured scope anchor
truncated/limited/failed page
incomplete snapshot
stale/lost-fence poll
candidate validation result before activation
restore without continuity proof
missing row under uncertain visibility
```

`removed`, `retired` and `resolved` require a provider-profile accepted negative-evidence class: complete current-scope evidence, bounded authenticated object-specific reconciliation or a stronger explicit provider primitive.

The negative transition and required audit/transition signal intent are atomic. Recovery cannot restore stale snapshot-complete/visibility/scope/generation markers as current authority.

## Historical completeness and gaps

Historical telemetry exposes what JLMIRROR can prove.

If late provider insertion, retention loss, restore uncertainty or another gap prevents completeness, Monitoring records explicit incomplete/gap/reconciliation evidence. A fast high-water mark is only a freshness optimization and never permanent completeness proof.

Configured scope changes and generation cutovers are represented as explicit coverage boundaries. Periods intentionally excluded from monitoring, and gaps between successor activation and successor evidence establishment, are not fabricated as complete provider history/current coverage.

## Event/outbox boundary

```text
new canonical observation accepted
  -> exactly one historical-projection obligation

semantic current-state transition
  -> stable transition identity + current-state-changed obligation
```

The second is not emitted for an identical repeated current observation.

High-volume raw observations are not required to traverse the general integration-event broker. Physical dispatch remains Phase 10/C2 implementation authority.

Replacement candidate validation, generation retirement and scope-reconciliation progress do not masquerade as provider facts. A cutover may emit its own stable source-generation transition under the accepted integration-event contract, but it does not synthesize remove/resolve events for every prior-generation object.

## Dashboard boundary

Monitoring dashboards are a Product outcome composed from active-generation Monitoring inventory, current metric state, health, problems, history and sync/scope/generation evidence.

BFF/read composition may build the initial view. Historical-generation evidence is included only through explicit historical/drill-down semantics. Persistent presentation-oriented/cross-domain dashboard projections remain Reporting & Experience ownership and do not gain Monitoring mutation ownership.

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
- metric values, especially `string`, `text` and `log`, problem summaries and provider metadata are protected customer data by default unless a stronger accepted classification proves otherwise;
- current/history/problem payloads therefore receive a conservative non-shared/non-persistent response treatment at the API boundary;
- provider strings are untrusted data and are bounded/safely encoded;
- logs/traces do not emit unrestricted observation/problem payloads or credentials;
- accepted per-value byte limits, page byte budgets and parser limits are mandatory before implementation; `OPEN` cannot mean unbounded;
- stale scope projection or historical-generation state cannot be used as authorization, current monitoring proof or negative-evidence authority;
- tenant/provider cardinality, generation cutover, scope reconciliation, history, webhook hints, reconciliation and backlog are bounded/attributable.

## Recovery/relocation

Before recovered/relocated Monitoring write authority resumes, applicable active source generation, replacement-candidate state, configuration/scope revisions, scope reconciliation, poll authority, observation acceptance, historical projection, current metric state, sync/checkpoint, negative evidence and transition/outbox continuity is reconciled through `(R,F]`.

Missing state is uncertainty, not permission to reaccept/retry/remove/resolve/activate a candidate, claim current `in_scope`, or reclassify an historical generation as active. A retired-placement writer cannot become current merely because it can still reach the provider.

Recovery must prove which source generation/scope revision is active and which replacement candidate/cutover outcome won before protected/effectful Monitoring writes resume. Historical-generation retained evidence remains historical after recovery unless a distinct currently authorized migration decision changes identity/lifecycle semantics.

## Capacity dimensions

Implementation measures/bounds at least:

```text
tenants/cell
sources/tenant
replacement candidates/source
source generations retained/source
resources/source/generation
metrics/resource/generation
scope-reconciliation backlog/rate
current-metric projection size
current-state rows/read page and serialized response bytes
per-value serialized byte size by value_kind
observation ingest/cardinality
history retention/query window/history response bytes
problem volume
sync/reconciliation/backfill backlog
provider limits
per-tenant skew/noisy-neighbor pressure
```

Production numerics remain C3/evidence-driven; `OPEN` never means unlimited and implementation is blocked until mandatory safety/resource bounds are selected.

## Compatibility-sensitive semantics

Breaking/security-sensitive changes include identity scope, cross-generation mapping, source-generation operational lifecycle, replacement candidate/cutover semantics, configured-scope revision/currentness semantics, current-state fencing/idempotency, current metric state meaning/surface, observation value representation, negative evidence, problem severity/health/evidence vocabularies, provider metadata authority, history completeness or domain ownership.

## Validation / falsification vectors

Before implementation conformance:

1. Tenant A cannot read/mutate Tenant B Monitoring state using known B IDs.
2. Same Zabbix native IDs in two tenants/sources/generations remain independent mappings.
3. Ordinary edit cannot change Zabbix base URL.
4. Replacement candidate with bad URL/credential cannot fence or degrade healthy active generation solely by being requested.
5. Concurrent replacement commands produce one idempotent candidate per command and at most one serialized cutover winner.
6. Candidate generation cannot mutate canonical current state before cutover.
7. Atomic cutover leaves exactly one active generation and one successor synchronization responsibility.
8. Cutover does not require O(number of prior-generation objects) rewrites; prior objects become historical by derived generation state.
9. Historical-generation resources/problems/health/current values cannot appear as current operational state by default.
10. An unresolved prior-generation problem remains historical evidence rather than being falsely resolved or treated as a current problem.
11. Scope edit commits without an O(N) resource/metric rewrite transaction.
12. Stale per-object scope projection cannot claim current `in_scope`, current health/value or authorize negative inference.
13. Scope exclusion never becomes provider `removed`/metric `retired`/problem `resolved` by itself.
14. Re-inclusion re-establishes currentness from provider evidence rather than restoring stale current evidence as fresh.
15. Stale poll/placement/historical generation cannot mutate current state.
16. Provider clock rollback does not freeze a genuinely newer current observation.
17. Same current observation under a later poll emits no duplicate semantic transition.
18. Current metric reads use `metric_current_state`, not per-request “latest history row” inference.
19. Metric-definition enumeration does not require embedding all current values.
20. History/backfill acceptance does not grant current authority.
21. Incomplete/visibility-degraded snapshots never remove/retire/resolve by omission.
22. PITR/relocation cannot revive stale negative-evidence/poll/candidate/scope/generation authority.
23. Observations are immutable and historical projection is idempotent by canonical identity.
24. Accepted non-latest observations still retain historical-projection obligation.
25. Historical gap/late-arrival/scope/generation uncertainty is explicit.
26. Provider acknowledgement/tags cannot mutate Alerting/ITSM/authorization.
27. Zabbix severity maps only to canonical classes and retains native severity only as external evidence.
28. One tenant's provider/scope-reconciliation failure/backlog does not stall unrelated tenants.
29. Logs/traces/errors contain no credential secret or unrestricted sensitive observation payload.
30. Current/history/problem responses cannot become shared/public cache entries and sensitive value responses follow stricter API cache class.
31. Oversized provider values/history pages are bounded before memory/storage/response exhaustion rather than treated as unlimited valid payloads.

## Remaining OPENs / blockers

Semantic ownership above is fixed by this proposed contract; mechanism/numeric choices remain:

- `OPEN-REL-030` C2 customer-monitoring durable acceptance/projection conformance;
- Tier 2 telemetry-store selection/conformance;
- secret-manager/KMS/credential-binding mechanism;
- broker/outbox physical dispatch mechanism;
- provider timeout/retry/page/history/backfill/reconciliation numerics;
- mandatory per-value/page byte and cardinality bounds;
- production capacity/retention/SLO/RPO/RTO numerics.

The next distinct governance track is the bounded C2 evidence spike after this contract package is accepted. Candidate spike code is not canonical by existing.