# 66 — Application Error Ingest and Incident Response Orchestration Proposal

**Status:** proposed — candidate cross-domain extension under adversarial review; grants no Alert, ITSM, Notification, Automation, API, or production authority  
**Decision class:** mixed C1/C2 proposal; any accepted implementation authority must be split into bounded gates before code is admitted  
**Drivers:** `ADR-005`, `ADR-013`, `ADR-019`, accepted G7 Alert Policy/Lifecycle, G8 Human Operations, G9 Notification Delivery, G10 ITSM

This record proposes two future capabilities:

1. a new monitored-application signal, `ApplicationErrorEvent`, as a candidate additional source for Alert evaluation; and
2. a tenant-scoped response-orchestration policy that may request downstream ITSM, Notification, or future Automation effects after an accepted Alert decision.

This proposal does **not** modify current G7/G8/G9/G10 authority while its status is proposed.

## Existing authority that this proposal must preserve

The accepted repository state remains authoritative:

- G7 Alert lifecycle is `active | resolved`; G8 acknowledgement/responsibility/visibility are orthogonal human-operation facts and are **not** Alert lifecycle states.
- G7 currently admits `monitoring_problem` and `monitoring_health_projection` source kinds. A new `ApplicationErrorEvent` source kind requires a separately accepted G7 extension.
- G9 v1 admits exactly one transport channel, `whatsapp_business@1`, and explicitly does not authorize additional channels or routing policy.
- G10 preserves `Alert != Incident`; an Alert does not automatically become or mutate an Incident.
- G11 Automation is not yet authorized.
- provider/native identity is never platform identity, and event payload fields never select tenant or authorization authority.

If any text below conflicts with those accepted contracts, the accepted contracts win until a later explicit authorization changes them.

## Proposed capability A — ApplicationErrorEvent

`ApplicationErrorEvent` is a candidate platform-owned event representing an application-side operational failure that may be invisible to infrastructure polling.

### Candidate admission shape

A future authorization may admit an authenticated machine principal to submit:

```text
application_error_event_id   platform-owned opaque identity
tenant_id                    derived from trusted admission context, not payload authority
application_id               platform resource/application reference
occurred_at                  source-reported event time
error_code                   bounded source code
error_message                bounded source text
operation                    optional bounded operation name
principal_ref                optional external/platform principal reference with explicit namespace
session_context              optional bounded correlation context
severity_hint                optional advisory source metadata
raw_evidence_ref             optional bounded evidence reference, not unrestricted payload authority
```

Requirements:

- tenant authority is derived from authenticated machine-principal admission and must match any body tenant field if one is present;
- `application_id` must resolve through current platform-owned inventory/registration authority;
- source-provided severity is advisory evidence only and cannot silently become Alert severity/policy authority;
- raw payload/evidence is bounded, privacy-minimized, and cannot select policy, tenant, destination, runbook, or ITSM provider;
- provider/source IDs are evidence references only and cannot become canonical event or Alert identity.

### Candidate idempotency

The accepted design must define a durable logical event identity. Time-bucket heuristics alone are insufficient as canonical replay identity.

Before authorization, the design must choose one of:

- caller-supplied idempotency key bound to authenticated source + tenant + application and content equivalence;
- platform-issued ingestion token bound to the same scope; or
- another reviewed deterministic equivalence key.

A replay with equivalent content must converge to one logical admitted event. A replay with the same idempotency identity but divergent material content must fail closed.

### Candidate G7 integration

ApplicationErrorEvent must enter Alerting only through a separately accepted G7 source-kind/policy extension.

That extension must prove:

- current G7 monitoring-derived semantics remain unchanged;
- Alert identity remains platform-owned;
- source evidence is immutable/auditable;
- policy evaluation re-reads current admitted authority before an effect;
- dedupe/correlation cannot merge across tenant/application/policy authority boundaries;
- unknown/incomplete source evidence cannot fabricate resolution.

This proposal does not itself authorize Alert create/resolve from ApplicationErrorEvent.

## Proposed capability B — IncidentResponsePolicy

`IncidentResponsePolicy` is a candidate tenant-scoped orchestration policy evaluated **after** an accepted Alert lifecycle effect. It does not own Alert lifecycle.

Candidate fields may include:

```text
tenant_id
policy_id / policy_version
severity_threshold
manual_response_only
open_incident
notification_intents[]
automation_triggers[]
created_at / superseded_at
content_hash
```

The exact schema, versioning and edit semantics require a separate accepted contract.

### Separation of authority

A future accepted orchestration implementation must preserve:

```text
ALERT_LIFECYCLE != HUMAN_ACK
ALERT != INCIDENT
ALERT_EFFECT != NOTIFICATION_DELIVERY
ALERT_EFFECT != AUTOMATION_EXECUTION
RESPONSE_POLICY != G7_ALERT_POLICY
DOWNSTREAM_FAILURE != ALERT_ROLLBACK
```

Rules:

1. `manual_response_only` may suppress **downstream automated response effects** only. It must not redefine G7 source-derived Alert resolution or turn G8 ACK into an Alert state transition.
2. `open_incident` describes a future automatic Alert-to-Incident capability that is **outside current G10 authority**. Before it can cause any runtime effect, a separately accepted G10 extension must explicitly authorize automatic Alert-to-Incident creation, preserve `Alert != Incident`, and define the exact admission/idempotency/recovery contract. After that extension exists, orchestration may request the action only through the extended G10 boundary; G10 must re-read current Alert authority and owns Incident identity/idempotency.
3. notification requests must create/use G9 notification intent authority. This policy cannot directly dispatch provider messages.
4. any channel beyond `whatsapp_business@1` remains blocked until separately authorized.
5. `automation_triggers` are descriptive future configuration only until G11 is authorized; they cannot enqueue or execute runbooks today.
6. failure of ITSM/Notification/future Automation must be recorded and reconciled independently; it must not roll back or rewrite an already accepted Alert transition.

## Proposed ordering

The dependency-safe order is:

1. accept a bounded ApplicationErrorEvent admission contract;
2. accept the G7 source-kind/policy extension, if ApplicationErrorEvent is to create/resolve Alerts;
3. accept a separate response-orchestration contract;
4. if `open_incident` automation is desired, accept a bounded G10 extension that explicitly authorizes automatic Alert-to-Incident creation; current G10 is insufficient;
5. reuse existing G9 and the separately extended G10 boundaries for downstream intents/effects;
6. add G11 integration only after G11 authorization;
7. add any extra notification transport only after a separate G9 channel-expansion authorization.

No single implementation PR should claim all six authorities.

## Closure conditions before implementation authorization

### ApplicationErrorEvent admission

Evidence must prove:

- cross-tenant submission fails closed;
- authenticated source identity cannot choose another tenant in payload;
- exact bounded parser/body limits exist;
- durable replay/equivalence identity is explicit;
- divergent replay is rejected;
- source time is retained as evidence without replacing ingestion/currentness timestamps;
- raw evidence cannot select authorization or downstream routing.

### G7 extension

Evidence must prove:

- existing `monitoring_problem` and `monitoring_health_projection` paths are unchanged;
- new source kind is explicitly enumerated and versioned;
- create/resolve decisions remain current-state/evidence driven;
- G8 acknowledgement remains orthogonal;
- tenant/policy/source identity collisions fail closed.

### G10 automatic incident extension

Before `open_incident` can trigger an Incident automatically, a separately accepted G10 extension must prove:

- current G10's explicit exclusion of automatic Alert-to-Incident creation is superseded only for the exact new bounded path;
- `Alert != Incident` remains mechanically true;
- G10 independently re-reads current Alert authority before Incident creation;
- retries/replays converge on one Incident under explicit logical-action equivalence;
- orchestration cannot write ITSM tables or fabricate Incident identity directly;
- failure/recovery semantics remain owned by G10 and cannot rewrite Alert lifecycle.

### Response orchestration

Evidence must prove:

- response-policy version is pinned to each downstream request;
- replay does not duplicate Incident or notification intent;
- downstream provider failure does not mutate Alert lifecycle;
- G10 and G9 enforce their own authority rather than trusting orchestration assertions;
- automation fields cause zero runtime effects until G11 is authorized.

## Consequences

### Positive

- application-originated failures can eventually become governed evidence rather than ad-hoc webhook side effects;
- tenant response preferences can be modeled without collapsing Alert, Incident, Notification, and Automation into one state machine;
- downstream failures remain independently recoverable.

### Cost / risk

- this is a cross-domain feature and therefore requires multiple bounded gates, not one broad implementation authorization;
- durable idempotency/equivalence and privacy controls are mandatory for application-supplied evidence;
- orchestration introduces additional recovery and audit state.

## Exit / revisit conditions

Revisit if the product chooses a streaming ingress instead of HTTP, if ApplicationErrorEvent becomes a separate bounded context, or if response orchestration is better modeled as an Automation capability after G11 rather than a dedicated policy domain.
