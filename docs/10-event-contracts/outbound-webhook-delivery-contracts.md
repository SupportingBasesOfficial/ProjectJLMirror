# Outbound Webhook Delivery Contracts

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines the future-safe contract for delivering accepted JLMIRROR events to external HTTP destinations when Product later enables outbound webhooks. It does not create a Product requirement to expose every internal event externally.

Outbound webhooks are delivery projections of platform-owned contracts. They are not the platform's internal event bus, not provider callbacks, and not a mechanism for external destinations to become authoritative over JLMIRROR business state.

## Product gate

A webhook contract exists only when:

- the owning Product/domain use case is accepted;
- the event/data is approved for external disclosure;
- subscriber authorization/tenant scope is defined;
- retention/retry/SLO expectations are accepted.

The fact that an internal event exists does not automatically make it externally subscribable.

## Delivery architecture

Representative flow:

```text
authoritative mutation
  -> outbox/integration event commit
  -> webhook projection/delivery obligation
  -> outbound connector
  -> subscriber endpoint
  -> durable delivery outcome / retry / quarantine
```

The webhook dispatcher consumes a stable platform integration event or approved projection. It does not read arbitrary current domain tables/provider payloads to reconstruct ad-hoc external meaning on each retry.

## Webhook contract identity

Every webhook payload has:

```text
webhook_contract_name
webhook_contract_version
source event/message identity
delivery identity
tenant/subscription scope
payload schema
signing/authentication profile
retry/delivery semantics
```

Webhook versioning is independent from:

- internal broker topic;
- external destination URL;
- API major version unless intentionally aligned;
- provider callback versions;
- deployment version.

## Delivery identity versus event identity

The platform distinguishes:

```text
source_message_id   -> the logical event/fact being projected
webhook_delivery_id -> one stable subscriber-specific delivery obligation
attempt_id          -> optional individual network attempt metadata
```

`webhook_delivery_id` is a platform-generated opaque identity whose namespace is globally unique across outbound webhook delivery obligations for the full supported retry/recovery/deduplication horizon. An implementation SHALL NOT rely on a subscription-local counter or another namespace that could collide when one receiver endpoint processes deliveries for multiple subscriptions or tenants.

A single source event delivered to two subscribers has two independent globally unique `webhook_delivery_id` values.

Retrying one subscriber delivery preserves the same `webhook_delivery_id` and source event identity. It does not invent a new business event or a new delivery obligation.

If a future external profile intentionally uses scoped rather than globally unique delivery IDs, that profile must expose an equally stable non-secret scope in the external contract and require deduplication by the complete `(scope, webhook_delivery_id)` identity. The default platform contract is global uniqueness.

## Immutable delivery obligation

A `webhook_delivery_id` identifies one immutable semantic delivery obligation, not merely a mutable retry row.

At obligation creation, the platform durably binds at least:

```text
webhook_delivery_id
source_message_id
webhook_contract_name
webhook_contract_version
tenant/subscription scope
subscription_id or equivalent stable subscription reference
destination_configuration_generation
canonical projected semantic payload or deterministic immutable projection inputs
payload/data-classification profile
created_at / causation identity
```

Every retry of the same `webhook_delivery_id` SHALL preserve the same externally meaningful contract and semantic body:

- same webhook contract name/version;
- same source event identity and occurrence meaning;
- same tenant/subscription disclosure scope;
- same canonical projected payload meaning;
- same bound destination configuration generation.

A rolling deployment, changed projection mapper, current mutable domain state, schema-default change or retry-worker version SHALL NOT cause the same `webhook_delivery_id` to represent a different external event.

The platform satisfies this by persisting the canonical semantic snapshot/bytes or by persisting immutable source + projection-version + inputs sufficient to deterministically reproduce the same canonical semantic payload. Exact storage mechanics remain implementation-specific.

Only explicitly attempt-scoped metadata may change across network attempts, for example:

- `attempt_id`;
- authenticator-bound attempt timestamp/freshness value;
- signature/MAC/certificate material produced under the accepted rotation profile;
- transport tracing/request metadata;
- safe retry bookkeeping.

Attempt-scoped authentication metadata SHALL NOT mutate the webhook's semantic contract/version, tenant scope, source identity, payload meaning or destination configuration generation.

## Subscription/tenant binding

A webhook subscription is bound to trusted platform state:

- tenant/global scope;
- authorized event/contract families;
- destination/configuration;
- monotonic or otherwise non-reusable destination configuration generation;
- signing credential reference/profile;
- status/disable/revocation state;
- optional filters defined by accepted contract.

Payload fields cannot redirect a delivery to another tenant/subscriber.

A subscriber-controlled filter cannot weaken tenant isolation or expand into events the subscription is not authorized to receive.

## Destination configuration generation

Destination/configuration state is security authority and is versioned independently from the delivery ID.

Every delivery obligation binds to the exact authorized subscription/destination configuration generation current when the obligation is admitted. That generation identifies the destination authorization/configuration under which disclosure was approved; it is not inferred later from whichever URL happens to be current.

A configuration generation change — including destination URL replacement, tenant/subscription scope change, security disablement or another change that affects disclosure authority — SHALL NOT silently retarget an existing delivery obligation.

For a pending or ambiguous delivery bound to an old generation, the accepted contract does exactly one of:

```text
cancel/fence   -> no further network attempts under the old obligation;
quarantine     -> hold for explicit governed resolution;
reissue        -> create a NEW delivery obligation/ID under the new authorized generation,
                  with causation/reference to the prior obligation.
```

The selected behavior is explicit by Product/security profile. Reissue is not an ordinary retry and cannot reuse the old `webhook_delivery_id`.

A security revocation may fence all future attempts for a generation immediately even though bytes already transmitted by an in-flight attempt cannot be recalled. An ambiguous outcome from an in-flight old-generation attempt remains historical evidence; it does not authorize retrying to either the old or new destination automatically.

Signing-key rotation that does not change destination/disclosure authority may be handled as attempt-scoped authentication metadata only when the accepted signing profile explicitly permits it. A signing profile change that changes what is authenticated or who is authorized is a configuration-generation/security change.

## Destination security

Outbound destinations are untrusted network targets and inherit the accepted outbound connector/SSRF boundary.

The delivery profile requires as applicable:

- allowed URL scheme/protocol;
- destination validation;
- DNS/IP/private-network policy;
- redirect policy;
- connect/request/overall timeouts;
- bounded response body/header size;
- rate/concurrency budget;
- TLS/certificate policy;
- secret retrieval by reference;
- safe proxy/egress configuration.

A customer-supplied URL SHALL NOT provide access to metadata services, localhost, internal control planes or otherwise prohibited network ranges according to the accepted SSRF policy.

Redirects do not silently escape the validated destination policy or the delivery's bound destination configuration generation.

## Payload envelope

External webhook payloads use a versioned bounded envelope conceptually equivalent to:

```json
{
  "delivery_id": "whd_opaque",
  "event_id": "msg_opaque",
  "event_type": "platform.contract.name",
  "event_version": "1",
  "tenant_id": "tenant_opaque",
  "occurred_at": "...",
  "correlation_id": "corr_opaque",
  "data": {}
}
```

Exact field naming/wire profile may be refined before a Product webhook surface ships, but the semantic separation among delivery identity, event identity, contract/version, tenant scope and payload is fixed.

Physical cell/provider/broker identifiers and internal destination-generation identifiers are not exposed unless a future external profile proves that exposure is necessary and safe. The receiver can deduplicate the default profile by globally unique `delivery_id` without learning physical topology.

## Data minimization

A webhook payload contains only fields deliberately approved for that external contract.

It SHALL NOT expose by default:

- internal database rows/keys;
- provider-native secrets/tokens;
- internal cell/region topology;
- authorization/session state;
- raw confidential artifacts;
- internal audit-only data;
- unrestricted error/stack detail.

Large/binary content uses a separately authorized resource/capability contract rather than embedding unbounded bytes.

## Authentication/signing

Webhook deliveries require an accepted destination-verification/authentication profile where the destination needs to verify platform authenticity.

The profile declares:

- signing/MAC/certificate mechanism;
- exact bytes/canonical representation covered;
- key/credential rotation behavior;
- timestamp/freshness evidence;
- delivery/event identity coverage;
- header cardinality/serialization;
- verification examples/test vectors.

Exact cryptographic algorithm/provider remains OPEN until the external webhook Product contract is accepted. The property that authenticity covers the intended payload plus freshness/replay-relevant metadata is not OPEN.

A retry may generate fresh attempt authentication metadata only under the accepted profile; the verified semantic payload associated with a stable delivery ID remains unchanged.

## Secret handling

Webhook signing secrets/private keys are stored/retrieved through the accepted secret boundary.

Rules:

- no plaintext secret in async payloads/logs;
- delivery workers receive only narrowly scoped secret access;
- secret rotation does not require changing webhook event identity;
- configuration UI/API never returns reusable secret material except under an explicit one-time-secret contract;
- compromise/revocation can disable/rotate independently per subscription where required.

## Timestamp/freshness

When a signing profile uses a timestamp, the timestamp is authenticator-bound to the same delivery/payload identity.

Subscriber guidance may define an accepted verification window. A timestamp header not covered by the accepted authenticator is insufficient freshness evidence.

An attempt timestamp may change on retry when it is explicitly attempt-scoped and authenticated; that does not permit the semantic webhook body or delivery obligation to change.

## Delivery acknowledgement semantics

An HTTP response from the subscriber has contract-specific meaning.

The platform distinguishes:

```text
success_terminal
retryable_transient
retryable_throttled
permanent_rejection
ambiguous_network_outcome
```

Exact status mapping is profile-specific.

A `2xx` normally means the subscriber endpoint accepted the webhook according to the external contract, not that the subscriber completed any downstream business work.

## Network ambiguity

If the destination may have received/processed a webhook but the response is lost, the platform preserves the same immutable delivery obligation.

A network retry is eligible only while the exact bound destination configuration generation remains authorized for retry under the contract. If the generation has been retired/revoked/changed, the platform fences or quarantines the old obligation; it does not retarget the same delivery ID to the new destination.

When retry is eligible, the platform retries the same `webhook_delivery_id`, same source identity, same contract version, same semantic payload and same destination generation under at-least-once semantics.

External consumers are therefore instructed to deduplicate by stable delivery identity under the documented namespace.

The platform SHALL NOT invent a new event ID or mutate event meaning on timeout.

## Retry policy

Retry is bounded and uses backoff/jitter.

The profile declares:

- retryable status/error classes;
- maximum retry window/attempts;
- trusted `Retry-After` handling;
- concurrency/rate limits;
- terminal/quarantine behavior;
- configuration-generation eligibility/fencing behavior.

Exact numbers remain evidence-driven OPEN.

## Permanent rejection

Permanent configuration/contract failures move the delivery/subscription into a governed state rather than retrying forever.

Examples may include:

- invalid/retired destination configuration;
- subscriber contract/version rejected permanently;
- repeated authentication failure indicating stale credentials;
- destination disabled/revoked.

The platform records safe operator-visible reason classes without storing unrestricted response bodies.

## Subscription disablement

A tenant/admin may disable a webhook subscription under current authorization.

Disablement retires/fences the relevant configuration generation and prevents new delivery attempts according to the accepted fence semantics.

The contract defines behavior for already in-flight network attempts. Security-sensitive secret revocation may require immediate credential retirement even if transport cancellation cannot recall bytes already sent.

Disablement does not make an old ambiguous attempt disappear and does not authorize retargeting the same delivery obligation elsewhere.

## Deletion/erasure interaction

Webhook delivery history may contain confidential tenant data/evidence and follows retention/governance rules.

Governed erasure does not falsely claim an external subscriber forgot data already delivered. The platform can delete its retained payload/evidence according to policy while audit records truthfully represent that an external disclosure occurred where required.

## Replay/redrive

Operators may redrive a failed webhook delivery only through a governed action.

A true retry/redrive of the same delivery obligation:

- preserves source event identity;
- preserves the same globally unique logical webhook delivery identity;
- preserves webhook contract/version and semantic payload meaning;
- preserves the bound destination configuration generation;
- revalidates that the bound generation remains eligible for another attempt;
- respects current data-retention/authorization policy;
- is audited;
- does not bypass terminal security disablement.

If the bound destination generation is no longer eligible, the old obligation is canceled/fenced/quarantined according to policy. A manual resend to the current/new destination is a deliberately **new external delivery obligation**, receives a new `webhook_delivery_id`, binds to the new configuration generation and records causation back to the original event/delivery.

## Ordering

Webhook consumers SHALL NOT assume global delivery order.

If a specific webhook contract requires per-subject/process ordering, it declares:

- scope;
- sequence/revision;
- gap/retry behavior;
- whether later deliveries block behind a failed earlier delivery.

The default is independent at-least-once delivery.

## Subscriber isolation

One slow/broken subscriber SHALL NOT block unrelated tenants/subscriptions globally.

Worker/rate/concurrency isolation is maintained by tenant/subscription/destination/workload dimensions as needed.

## Observability

Safe webhook telemetry includes:

```text
webhook contract/version
subscription reference / configuration generation reference where policy permits
tenant hash/reference where policy permits
delivery ID
event ID
attempt count
latency
response class
retry/quarantine/fence state
oldest pending age
```

Normal logs exclude signing secrets and unrestricted payload/response bodies.

## Audit

Privileged subscription creation/update/delete, destination-generation changes, secret rotation, manual redrive/reissue and security disablement are auditable.

The platform may additionally retain governed delivery evidence required for support/compliance.

Audit evidence is separate from mutable retry bookkeeping.

## Recovery continuity

Restore/PITR can roll local delivery state or subscription configuration backward while a subscriber already received a webhook or while a newer configuration generation was already established.

Recovery therefore preserves/reconciles:

- stable source event identity;
- stable globally unique webhook delivery identity;
- immutable webhook contract/version and semantic payload snapshot/reproduction authority;
- bound subscription/destination configuration generation;
- surviving attempt/ack evidence where available;
- retired/revoked destination-generation fences;
- audit/accountability;
- duplicate-safe at-least-once semantics.

A missing restored `success` record does not prove the subscriber never received the delivery. A missing/older configuration record does not prove an old generation is current or retry-eligible.

Until generation continuity and delivery evidence are reconciled, protected outbound attempts that could disclose to the wrong destination remain fail closed/quarantined. Recovery SHALL NOT reconstruct the same `webhook_delivery_id` from current mutable state into a different payload, contract version or destination.

Retrying the same delivery identity is allowed only when the original bound generation and immutable delivery obligation remain eligible under the at-least-once external contract. Otherwise any deliberate resend is a new delivery obligation/ID with explicit causation.

Where a webhook itself triggers an irreversible partner effect and stronger guarantees are required, the specific integration contract must provide partner idempotency/reconciliation rather than relying on HTTP acknowledgement alone.

## Required tests

Before an outbound webhook profile ships:

- SSRF/private-network/redirect escape attempts fail closed;
- destination response size/time is bounded;
- signing verification vectors prove exact covered representation;
- timestamp/freshness metadata is authenticator-bound;
- globally unique delivery IDs do not collide when one endpoint receives multiple tenants/subscriptions;
- timeout after subscriber receives request retries the same delivery identity only when its bound destination generation remains eligible;
- retry across rolling deployment/projection-mapper change preserves identical contract version and semantic payload for the same delivery ID;
- current mutable domain state changing after obligation creation does not mutate retry payload meaning;
- destination/configuration change while delivery is pending never silently retargets the same delivery ID;
- destination revocation during ambiguous in-flight outcome prevents further old-generation attempts and never redirects the old delivery to the new generation;
- explicit reissue to a new generation receives a new delivery ID with causation to the original;
- duplicate delivery can be safely identified by the documented external identity namespace;
- tenant A cannot subscribe to tenant B events;
- payload filters cannot expand scope;
- secret rotation/revocation does not leak old/new secret and cannot change delivery semantics silently;
- permanent failure reaches governed terminal/quarantine state;
- one failing subscriber does not exhaust global delivery capacity;
- restore to older local delivery/configuration state does not invent a new event identity, resurrect a retired destination generation or mutate the semantic payload of an existing delivery ID;
- logs/errors do not leak payload/signature secrets.

## Intentionally OPEN

- whether/which Product webhook surfaces are enabled;
- exact external envelope field names beyond fixed semantics;
- signature algorithm/profile;
- key management backend;
- retry numeric policy;
- subscriber ordering profiles;
- delivery storage implementation;
- exact representation/storage of destination configuration generation;
- exact cancel/quarantine/reissue policy by Product webhook profile;
- external hostname/egress implementation.

The Product gate, tenant isolation, globally unique delivery identity namespace, immutable per-delivery semantic obligation, destination-generation fencing, SSRF boundary, bounded at-least-once delivery and authenticated payload properties are fixed.
