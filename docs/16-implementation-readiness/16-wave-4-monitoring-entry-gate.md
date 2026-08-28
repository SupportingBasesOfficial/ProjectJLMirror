# Wave 4 Monitoring Entry Gate

**Status:** proposed gate record  
**Base authority:** `main@d63b435ffa26fba7794187ceafaf0d5a9773223b`  
**Scope:** first Monitoring vertical entry prerequisites; no implementation authorization  
**Depends on:** accepted Implementation Readiness Gate, Waves 0–3, `CAP-MONITORING`, `FR-MON-001..006`, Monitoring ownership/data, Phase 09/10 contracts, Zabbix provider contract, `OPEN-REL-030`

## Purpose

Wave 4 is not generic permission to start product code. The accepted sequencing rule requires exact Product/domain endpoint/event/data/authority contracts, while `impl.customer-telemetry@1` is separately blocked until `OPEN-REL-030` C2 selection/conformance evidence is accepted.

This gate prevents provider contracts, experimental code, broker schemas or infrastructure defaults from filling normative gaps silently.

## Canonical pre-state at base

At `main@d63b435ffa26fba7794187ceafaf0d5a9773223b` the repository already has:

- accepted Monitoring Product scope/requirements;
- Monitoring bounded-context/logical data ownership;
- generic Phase 09 Monitoring resource-family vocabulary;
- generic Phase 10 event/async envelope/publication/recovery laws;
- Phase 09/10 authority, transaction, async, recovery and collection laws;
- Waves 0–3 implementation substrate;
- accepted Zabbix trust/auth/poll/reconciliation profile;
- `OPEN-REL-030` with Tier 1 PostgreSQL pattern selected at mechanism level and TimescaleDB only a leading Tier 2 candidate pending evidence.

Still missing at that base:

- exact Monitoring canonical identity/lifecycle/generation/scope/negative-evidence/problem/health/current-metric semantics;
- exact endpoint/use-case contracts;
- exact applicable Monitoring event contracts;
- explicit Zabbix problem/value normalization destination;
- accepted `OPEN-REL-030` conformance evidence.

The first four are **normative contract gaps**. The last is a distinct **C2 evidence gap**.

`OPEN-API-016` remains the global incremental register item for endpoint-specific contracts across all domains. Acceptance of this package closes the Monitoring-core subset only.

## Mandatory two-track progression

```text
TRACK A — normative authority
  Monitoring domain contract
  + Monitoring API contract
  + Monitoring event contracts
  + Zabbix provider/normalization propagation
  + Monitoring surface-map propagation
  + this entry gate
  -> exact-HEAD adversarial review
  -> explicit merge authorization
  -> accepted contract base

TRACK B — C2 bounded evidence
  OPEN-REL-030 spike from exact accepted Track A base
  -> experimental/conformance code + reproducible evidence
  -> security/concurrency/recovery/capacity falsification
  -> reviewed C2 decision update
  -> explicit acceptance authorization

ONLY AFTER BOTH
  -> separate explicit Wave 4 implementation authorization
  -> canonical vertical implementation PR(s)
```

Track B cannot define missing Product/domain/event semantics by existing first. Track A cannot claim Track B evidence exists.

## Track A artifacts

### Monitoring domain contract

`docs/03-domains/monitoring-domain-contract.md` fixes:

- source/resource/metric/observation/problem/health/sync identities;
- strict provider-instance generation boundary for initial Zabbix mappings;
- active generation versus non-authoritative replacement candidate;
- finite/current candidate validation evidence versus permanent readiness;
- active-generation versus historical-generation operational semantics without O(N) cutover rewrite;
- configured scope revision versus provider absence;
- bounded scope reconciliation rather than O(N) source mutation;
- explicit `metric_current_state` separate from history;
- dedicated current-state read semantics rather than embedding all values in definition enumeration;
- current-state precedence versus semantic idempotency;
- exact durable publication obligations for generation/scope/current-metric transitions;
- authoritative negative evidence;
- severity/health/evidence vocabularies;
- historical completeness/gap/scope/generation semantics;
- dashboard/authorization/security/recovery/capacity boundaries.

### Monitoring API contract

`docs/09-api-contracts/monitoring-domain-api-contract.md` fixes:

```text
GET/POST    /monitoring-sources
GET/PATCH   /monitoring-sources/{source_id}
POST        /monitoring-sources/{source_id}:replace-instance
POST        /monitoring-sources/{source_id}/replacement-candidates/{candidate_generation}:activate
GET         /monitoring-resources
GET         /monitoring-resources/{resource_id}
GET         /metric-definitions
GET         /metric-definitions/{metric_definition_id}
GET         /metric-current-states
GET         /metric-current-states/{metric_definition_id}
GET         /metric-observations
GET         /problems
GET         /problems/{problem_id}
GET         /health-projections
GET         /health-projections/{resource_id}
GET         /monitoring-sync-operations
GET         /monitoring-sync-operations/{operation_id}
```

Metric-definition reads remain metadata-oriented. Efficient latest/current values are served from dedicated transactional `metric-current-states`; historical Tier 2 is never queried on each request to discover latest.

Current operational collections default to the source's active generation. Historical-generation evidence is explicitly classified and never silently unioned into current inventory/health/problem/current-value views.

The API fixes current auth/tenant routing, mutation idempotency + `If-Match`, staged source replacement with validation currentness, revisioned configured-scope semantics, endpoint-specific cache classes and finite row/byte/history bounds.

Network-dependent DNS/provider/redirect/egress validation is outside source mutation database transactions. Source commands validate deterministic URI/profile/static policy and outbound connector authority is revalidated immediately before provider use.

### Monitoring event contracts

`docs/10-event-contracts/monitoring-domain-event-contracts.md` fixes the applicable first-vertical async semantics:

```text
monitoring.source-generation.changed
monitoring.source-scope.changed
monitoring.metric-current-state.changed
```

All three are tenant-scoped provider-neutral `integration_event` contracts under the Phase 10 canonical envelope, at-least-once delivery and message-equivalence rules.

They are **minimal invalidation/resync signals**, not replicated owner state:

- no metric value;
- no provider payload/native ID;
- no endpoint URL;
- no credential/secret reference;
- no broker arrival order treated as current-state authority;
- consumer needing current protected state re-resolves current placement/authority and re-reads Monitoring owner state.

Publication boundaries are exact:

```text
source cutover commit
  -> exactly one durable source-generation.changed obligation

scope_revision commit
  -> exactly one durable source-scope.changed obligation

semantic metric_current_state advancement
  -> exactly one durable metric-current-state.changed obligation
```

The corresponding stable transition/message identity is committed atomically with the owner transition or recoverable deterministically from an equivalent durable advancement record. Publish-ack ambiguity republishes the same logical identity.

`metric-current-state.changed` does not fire for a later poll generation alone, same semantic current observation, historical/backfill acceptance or retired-generation replay.

Source generation/scope signals invalidate/resync current consumers without generating O(N) per-object remove/resolve events. Delayed/reordered events cannot regress owner state because consumers re-read current Monitoring authority.

The contracts do **not** force raw high-volume `metric_observation` history through the general event broker, do not automatically create realtime/webhook disclosure, and do not preselect Kafka/serializer/schema registry.

Per Phase 10 governance, the reviewed human-readable contract is canonical first. Before an implementation of these contracts becomes canonical, its reproducible package additionally includes machine-readable schema/semantic manifest/compatibility vectors as applicable; those artifacts may not redefine the reviewed semantics.

### Non-disruptive replacement invariant

A replacement request creates a non-authoritative candidate first:

```text
ACTIVE N
  -> replacement command
  -> CANDIDATE N+1 validating
       fail -> ACTIVE N remains active
       pass -> candidate ready_for_cutover (bounded current evidence)
                -> atomic cutover
                     fence N
                     active_generation := N+1
                     source-generation event obligation
                     successor sync/reconciliation responsibility
```

Required properties:

- candidate reachability/credentials/scope are validated outside source mutation transaction;
- candidate validation cannot mutate canonical current resource/metric/problem/health state;
- bad/unreachable candidate cannot retire a healthy active generation merely because replacement was requested;
- candidate config/scope/effective credential binding and validation policy/evidence generation are bound to readiness;
- changed candidate intent or invalidated credential/policy proof resets readiness rather than preserving stale validation;
- validation evidence has a finite evidence-driven freshness horizon; `OPEN` does not mean infinite;
- cutover revalidates current authority/revision/candidate fingerprint and current validation evidence generation/freshness;
- actual provider use still revalidates connector/credential authority, so validation does not freeze DNS/reachability/secret state;
- after cutover exactly one active generation exists;
- ambiguity/recovery cannot silently activate a failed/stale candidate or resurrect retired generation.

### Generation lifecycle invariant — O(1) cutover, no false currentness

Every generation-scoped object derives:

```text
generation_state =
  active_generation      if object.source_instance_generation == source.active_source_instance_generation
  historical_generation  otherwise
```

Required properties:

- cutover changes source active-generation authority, not every child row;
- prior-generation resources/metrics/problems/health/current values become historical immediately by derivation;
- generation retirement is not provider `removed`, metric `retired` or problem `resolved`;
- current operational collections default to active generation;
- historical-generation inclusion is explicit and visibly classified;
- a historical unresolved problem remains retained historical evidence but cannot feed current Monitoring/Alerting semantics;
- prior-generation health/current values cannot masquerade as current even if last stored evidence was current before cutover;
- successor current coverage remains incomplete/reconciliation-required until successor sync proves it;
- history for a generation remains addressable by generation-scoped canonical identity without implicit union across matching provider IDs/names;
- historical replay/backfill may repair retained history but cannot regain current-state authority;
- one generation-change event invalidates/resyncs current consumers instead of O(N) per-object lifecycle events.

### Configured-scope invariant — bounded at enterprise cardinality

Editing `configured_provider_scope` is local configuration authority, not provider negative evidence.

The source mutation SHALL be bounded independently of resource/metric cardinality:

```text
commit new configured_provider_scope
advance monotonic scope_revision
persist audit/accountability intent
persist one source-scope.changed event obligation
create one durable scope-reconciliation responsibility
COMMIT
```

It SHALL NOT synchronously rewrite every resource/metric row before returning success.

Per-object active-generation scope projection carries:

```text
scope_state = in_scope | out_of_scope
scope_projection_revision
scope_evidence_state = current | reconciliation_required
```

Required properties:

- per-object projection can reconcile asynchronously in bounded batches;
- `in_scope` is authoritative only when proven against current source `scope_revision` or equivalent current deterministic evaluation;
- stale scope projection cannot authorize provider work, negative inference, fresh health or current-value semantics;
- unreconciled membership fails safe as `scope_evidence_state=reconciliation_required`;
- historical-generation scope evidence remains historical and is not relabeled against successor scope revision;
- scope exclusion alone cannot cause resource `removed`, metric `retired`, problem `resolved` or fresh `healthy` status;
- scope event is only invalidation/resync and cannot claim child reconciliation finished;
- re-inclusion requires provider evidence before currentness returns;
- history exposes intentional scope gaps rather than fabricating completeness.

### Data classification and cache invariant

Protected Monitoring data is never shared/public cached.

```text
source/config/credential metadata          no_store
resource summary                           private_revalidate
resource detail/external refs              no_store
metric-definition summary                  private_revalidate
metric-definition detail                   no_store
metric current values                      no_store
metric history                             no_store
problem summary/detail                     no_store
health canonical summary                   private_revalidate
sync/replacement/scope operational detail  no_store
```

`private_revalidate` still requires server revalidation/current authorization and recomputation/validation of generation/scope currentness; it is not an authorization/currentness TTL.

Metric `string/text/log` values, problem summaries and provider metadata are protected customer data by default. Monitoring event payloads are `confidential_tenant` minimal signals and exclude metric values/provider payloads/credentials. Mandatory value/page/event/response byte bounds must be selected before implementation.

### Cursor governance

Monitoring continuation is constrained to Phase 09 `url_safe_non_sensitive_handle` semantics and narrowed to returned-row anchor cursors:

- exposed cursor is only a canonical item ID already eligible for response class;
- it embeds, encrypts, signs or indirectly references no hidden protected tenant/filter/query/provider/topology payload;
- filters/window/generation selection are resubmitted canonically every continuation;
- current tenant/resource authorization is re-established;
- server resolves anchor under current scope and derives deterministic sort position from authoritative row;
- cross-tenant/wrong-filter/wrong-window/wrong-generation anchors fail without existence leakage;
- possession grants no continuation authority.

Therefore this vertical does **not** activate/reclassify `OPEN-API-019`, which remains C5.

### Surface-map propagation

`docs/09-api-contracts/domain-api-surface-map.md` reserves `metric-current-states` as the Monitoring-owned bounded current-value family, distinct from metric-definition metadata and historical observations. The surface map therefore matches the exact endpoint contract instead of retaining an older vocabulary snapshot.

### Zabbix provider + normalization propagation

The Zabbix provider contract is aligned with these semantics:

- current-state poll authority additionally requires that the poll's `zabbix_instance_generation` still equals the source's active generation;
- retired-generation polling may repair historical evidence only under explicit historical authority and cannot mutate current state;
- a JLMIRROR configured-scope edit is not provider negative evidence;
- snapshot-complete negative inference requires current poll, placement, active-generation and configured-scope authority;
- source cutover/scope revision invalidates stale snapshot-complete eligibility.

`zabbix-monitoring-normalization-profile.md` resolves the deferred normalization question:

```text
Not classified -> unknown
Information    -> informational
Warning        -> warning
Average        -> degraded
High           -> critical
Disaster       -> critical
```

Acknowledgement and tags remain bounded provider metadata only, never JLMIRROR Alerting/ITSM/tenant/authorization authority. Zabbix value classes map to canonical Monitoring value kinds.

## Product-scope exclusions

Track A does not create:

- source delete/retirement semantics;
- tenant-facing manual `:sync/:retry/:resume`;
- provider write-back;
- Alerting acknowledgement/lifecycle;
- ITSM mutation;
- AIOps product behavior;
- public SDKs;
- public/outbound Monitoring event subscription;
- browser realtime activation;
- a mutable Monitoring-dashboard aggregate.

Monitoring dashboards may compose active-generation inventory, dedicated current metric state, health, problems, history and sync/scope/generation evidence; persistent presentation/cross-domain projections remain Reporting & Experience ownership.

## Readiness matrix if Track A is accepted

| Slice/capability | Contract state | Evidence/mechanism state | Result |
|---|---|---|---|
| Monitoring domain semantics | exact | n/a | contract-ready |
| Monitoring-core endpoint subset (`OPEN-API-016`) | exact for this vertical | unrelated/future endpoints remain incremental | Monitoring subset contract-ready |
| Monitoring applicable event semantics | exact logical contracts | transport/serializer/equivalence mechanism still C2 | contract-ready; implementation package still required |
| source management API | exact | credential binding/secret mechanism still C2 | contract-ready, mechanism selection where used |
| replacement candidate/cutover | exact semantics incl. validation currentness | secret freshness representation + numeric horizon remain evidence/mechanism dependent | contract-ready |
| generation lifecycle/currentness | exact semantics | storage/query mechanism replaceable | contract-ready |
| configured-scope handling | exact revision/currentness semantics | batch/concurrency numerics C3 | contract-ready |
| Zabbix trust + normalization | exact | provider production numerics C3 | provider-contract-ready |
| current metric projection semantics/API | exact | backing acceptance path still depends on telemetry conformance | contract-ready, implementation blocked with customer telemetry |
| `impl.customer-telemetry@1` | exact domain/API/event semantics | `OPEN-REL-030` NOT conformed | **bounded-evidence-spike-only** |
| Tier 2 history | exact semantics | TimescaleDB only candidate | **not canonical** |
| protected cursor C5 | not required | remains deferred | **not activated** |
| raw telemetry general broker | not required | broker C2 independent | no forced dependency |
| Alerting/ITSM/AIOps | separate Product/domain authority | not activated | blocked by own vertical contracts |

## Track B — required bounded evidence program

After Track A acceptance, next mutation is a separate evidence branch/PR:

```text
base    exact accepted Track A squash
branch  evidence/open-rel-030-monitoring-conformance
class   C2 bounded spike / conformance evidence
product semantics unchanged
production authority none
```

### Tier 1 PostgreSQL / publication evidence

Prove with real multi-connection PostgreSQL:

- atomic create-or-observe;
- observation + exactly one history projection obligation;
- current-state candidate CAS independent from first acceptance;
- semantic no-op on repeated current observation;
- transition identity + exact current-state event obligation atomicity;
- duplicate/concurrent/replay behavior;
- event/outbox publish-ack ambiguity reuses stable logical identity;
- cutover/scope revision commit exact source invalidation event obligation;
- crash injection around transaction/outbox boundaries;
- downstream Tier 2 or event transport outage/backlog;
- restore/PITR `(R,F]` continuity.

### Replacement/generation/scope evidence

The eventual implementation profile must falsify:

- bad candidate cannot fence healthy active generation;
- candidate cannot write canonical state before activation;
- candidate config/scope/effective credential/policy mutation invalidates old readiness;
- validation expiry/restored stale readiness cannot authorize cutover;
- concurrent candidate/cutover commands produce one active-generation winner;
- crash after fence/before response remains reconcilable and idempotent;
- old writer cannot regain current authority after cutover;
- cutover does not require O(number of old objects) rewrite/events;
- old objects become historical by active-generation authority and cannot leak into current operational views;
- reordered generation/scope invalidations cannot regress a consumer because consumer re-reads owner state;
- unresolved old-generation problem cannot feed current problem/Alerting input;
- scope edit remains bounded regardless of resource/metric cardinality;
- stale scope projection cannot grant `in_scope` currentness or negative-inference authority;
- scope exclusion/event cannot synthesize provider absence/retirement/resolution;
- re-inclusion cannot relabel stale last-known evidence as fresh;
- one tenant's candidate-validation/event/scope-reconciliation/historical workload cannot stall unrelated tenants.

These semantics are fixed by Track A; concrete implementation evidence belongs to implementation/conformance rather than being fabricated in docs.

### Zabbix/current/history evidence

- single-winner fenced poll epoch/generation across scheduled/hint work;
- stale poll/retired placement/historical-generation current-state rejection;
- clock rollback without current-state freeze;
- same current observation without duplicate semantic transition/event;
- historical/backfill observation creates no current-state event from later delivery/event time alone;
- current metric event contains no metric value and reordered invalidations cannot regress owner state;
- current metric state remains last-known + explicitly stale when authority is stale;
- same-second history saturation/checkpoint safety;
- delayed insertion beyond fast overlap recovered by independent bounded sweep;
- provider/proxy outage widening/reconciliation;
- visibility-anchor loss blocks negative inference;
- incomplete snapshot blocks remove/retire/resolve;
- new Zabbix generation cannot alias reused native IDs with old mappings;
- PITR/relocation poll/generation/event-authority continuity.

### Tier 2 candidate security

If TimescaleDB remains candidate, attack exact intended features/roles:

```text
raw hypertables
compression/columnar states used
continuous aggregates/materializations
projection worker
application/reporting/read roles
background refresh/compression/retention jobs
migration/DDL/ops/recovery roles
SET/set_config/SET ROLE/session authorization/search_path/helper-function abuse
backup/PITR restored role/policy/object state
```

One Tenant B row reachable under Tenant A's normal trust class rejects that profile.

### Tier 2 capacity under same security profile

Measure representative multi-tenant ingest/skew, bounded time-range queries, compression/retention/rollup, background-job load, downstream outage/backlog/drain and storage/cost dimensions **without disabling required isolation**.

Security-weakened benchmark results are invalid evidence.

### Mandatory API/event/resource bounds

Before canonical implementation, evidence/decision records must select finite values for required safety/resource bounds including:

```text
normalized metric value bytes by kind
provider/body bytes
page rows and serialized response bytes
history maximum time window/rows/bytes
Monitoring event payload/backlog/coalescing bounds
replacement-validation freshness horizon/refresh workload
source generations retained/historical query envelope
scope selector count/size
scope-reconciliation batch/backlog/concurrency
problem metadata count/size
replacement candidate retention/count
per-tenant/source sync/concurrency/backlog
```

`OPEN` may represent an unresolved numeric during Track A, but runtime implementation cannot interpret it as unlimited.

## Evidence artifacts

Track B must retain machine/reviewer-consumable provenance:

```text
exact base/head
candidate/version/config
schema/migration
repo-owned test/fault harness
security matrix
workload/dataset definition
measured output
known failures/limits
cleanup/no-production-authority statement
C2 conclusion: accept | reject | further bounded evidence
```

Unit-green != capacity proof; benchmark-green != security/concurrency/recovery proof.

Before event implementation becomes canonical, Phase 10 contract packaging additionally requires machine-readable payload/envelope schema, semantic manifest/compatibility metadata and examples/test vectors as applicable, all derived from rather than redefining the accepted logical contracts.

## Decisions intentionally not made

This gate does not select IdP/session/CSRF, general async broker/topology, message-equivalence crypto/backend, protected cursor C5, production topology/counts, production numerics, Alerting/ITSM/AIOps, manual tenant sync controls, source delete/retirement, public Monitoring event/webhook disclosure, realtime activation or cross-domain dashboard persistence.

## Track A acceptance criteria

Exact-final-HEAD review must prove:

1. every Monitoring concept has one owner/canonical identity;
2. Zabbix generation boundary cannot merge reused native IDs;
3. source ordinary edit cannot bypass explicit replacement;
4. replacement request cannot retire healthy active generation before candidate admissibility is proven;
5. candidate readiness is finite/current and bound to candidate config/scope/credential/policy evidence rather than permanent;
6. candidate cannot mutate canonical current state before atomic cutover;
7. cutover has one serialized winner and leaves exactly one active generation;
8. cutover changes child operational currentness by derived generation authority, not O(N) rewrites/events;
9. cutover atomically creates one stable source-generation invalidation event obligation;
10. historical-generation objects cannot masquerade as current inventory/health/current-value/problem state;
11. generation retirement cannot fabricate `removed`, `retired` or `resolved`;
12. scope edit commits without O(N) resource/metric rewrite;
13. scope revision atomically creates one stable scope invalidation event plus bounded reconciliation responsibility;
14. stale scope projection cannot claim current `in_scope`, fresh health/value, provider-work eligibility or negative-inference authority;
15. configured scope exclusion/event cannot masquerade as provider negative evidence;
16. Zabbix poll current-state/negative-inference authority requires current source-instance generation in addition to poll/placement/scope authority;
17. semantic current metric advancement creates exactly one stable minimal current-state event; duplicate poll/history/backfill does not;
18. Monitoring event payloads are confidential/minimal and cannot become owner-state/broker-order authority;
19. base URL cannot embed credentials/query/fragment; DNS/provider/redirect/egress work stays outside DB mutation transaction and is revalidated before provider use;
20. current metric state is explicitly separate from history and from metric-definition enumeration;
21. current/history/problem responses use conservative `no_store`, while private metadata/status reuse revalidates current authorization plus generation/scope currentness;
22. value/page/history/event/validation/generation-retention/scope-reconciliation resource sizes are bounded as mandatory pre-implementation obligations;
23. fenced poll progress does not manufacture semantic state changes;
24. history acceptance is independent from current candidacy and does not implicitly union generations;
25. incomplete/uncertain snapshots cannot create absence/resolution;
26. severity/ack/tags/native IDs cannot become tenant/domain authority;
27. history completeness is evidence-backed and scope/generation gaps are explicit;
28. Phase 09 current-auth/idempotency/precondition/cache/error/collection laws are preserved;
29. Phase 10 identity/equivalence/outbox/at-least-once/recovery laws are preserved;
30. cursor is only a non-sensitive returned-row anchor and C5 is not silently reclassified;
31. Monitoring surface map includes the dedicated current-state family and matches endpoint vocabulary;
32. Monitoring-core endpoint contracts satisfy incremental `OPEN-API-016` responsibility without pretending unrelated families are closed;
33. `OPEN-REL-030` remains open and TimescaleDB remains non-canonical;
34. no Waves 0–3 implementation substrate changes;
35. exact final HEAD has P0/P1/P2=0 and no unresolved review thread.

A clean Track A gate still requires separate explicit user merge authorization.

## Advancement state machine

```text
CURRENT BASE d63b435f...
  Wave 4 Monitoring entry          BLOCKED ON CONTRACT + C2 EVIDENCE

AFTER TRACK A ACCEPTED
  Monitoring domain/API/events     READY
  OPEN-REL-030                     STILL C2 OPEN
  customer telemetry               BOUNDED EVIDENCE SPIKE ONLY
  protected cursor C5              UNCHANGED / NOT ACTIVATED
  canonical Wave 4 implementation  NOT AUTHORIZED

AFTER TRACK B ACCEPTED
  Monitoring contract authority    READY
  OPEN-REL-030                     SELECTED + CONFORMED FOR ACCEPTED PROFILE
  Wave 4 implementation            ELIGIBLE FOR SEPARATE EXPLICIT AUTHORIZATION
```

No CI result, candidate code, external reviewer or AI output can skip a transition.