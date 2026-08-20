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
  -> webhook projection/delivery record
  -> outbound connector
  -> subscriber endpoint
  -> durable delivery outcome / retry / quarantine
```

The webhook dispatcher consumes a stable platform integration event or approved projection. It does not read arbitrary domain tables/provider payloads to construct ad-hoc external messages.

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
source_message_id  -> the logical event/fact being projected
webhook_delivery_id -> this subscriber-specific delivery operation
attempt_id          -> optional individual network attempt metadata
```

A single source event delivered to two subscribers has two independent `webhook_delivery_id` values.

Retrying one subscriber delivery preserves the same `webhook_delivery_id` and source event identity. It does not invent a new business event.

## Subscription/tenant binding

A webhook subscription is bound to trusted platform state:

- tenant/global scope;
- authorized event/contract families;
- destination/configuration;
- signing credential reference;
- status/disable/revocation state;
- optional filters defined by accepted contract.

Payload fields cannot redirect a delivery to another tenant/subscriber.

A subscriber-controlled filter cannot weaken tenant isolation or expand into events the subscription is not authorized to receive.

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

Redirects do not silently escape the validated destination policy.

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

Physical cell/provider/broker identifiers are not exposed.

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

If the destination may have received/processed a webhook but the response is lost, the platform retries the same `webhook_delivery_id` under at-least-once semantics.

External consumers are therefore instructed to deduplicate by stable delivery/event identity as appropriate.

The platform SHALL NOT invent a new event ID on timeout.

## Retry policy

Retry is bounded and uses backoff/jitter.

The profile declares:

- retryable status/error classes;
- maximum retry window/attempts;
- trusted `Retry-After` handling;
- concurrency/rate limits;
- terminal/quarantine behavior.

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

Disablement prevents **new delivery attempts** according to the accepted fence semantics.

The contract defines behavior for already in-flight network attempts. Security-sensitive secret revocation may require immediate credential retirement even if transport cancellation cannot recall bytes already sent.

## Deletion/erasure interaction

Webhook delivery history may contain confidential tenant data/evidence and follows retention/governance rules.

Governed erasure does not falsely claim an external subscriber forgot data already delivered. The platform can delete its retained payload/evidence according to policy while audit records truthfully represent that an external disclosure occurred where required.

## Replay/redrive

Operators may redrive a failed webhook delivery only through a governed action.

Redrive:

- preserves source event identity;
- normally preserves the logical webhook delivery identity when retrying the same delivery obligation;
- revalidates current subscription/destination status;
- respects current data-retention/authorization policy;
- is audited;
- does not bypass terminal security disablement.

A newly requested manual resend that is intentionally a new external delivery obligation may receive a new delivery identity with causation back to the original event/delivery.

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
subscription reference
tenant hash/reference where policy permits
delivery ID
event ID
attempt count
latency
response class
retry/quarantine state
oldest pending age
```

Normal logs exclude signing secrets and unrestricted payload/response bodies.

## Audit

Privileged subscription creation/update/delete, secret rotation, manual redrive and security disablement are auditable.

The platform may additionally retain governed delivery evidence required for support/compliance.

Audit evidence is separate from mutable retry bookkeeping.

## Recovery continuity

Restore/PITR can roll local delivery state backward while a subscriber already received a webhook.

Recovery therefore preserves:

- stable source event identity;
- stable webhook delivery identity;
- surviving attempt/ack evidence where available;
- audit/accountability;
- duplicate-safe at-least-once semantics.

A missing restored "success" record does not prove the subscriber never received the delivery. Retrying the same delivery identity is allowed by the at-least-once external contract, but the platform SHALL NOT create a new semantic event or claim exactly-once subscriber effect.

Where a webhook itself triggers an irreversible partner effect and stronger guarantees are required, the specific integration contract must provide partner idempotency/reconciliation rather than relying on HTTP acknowledgement alone.

## Required tests

Before an outbound webhook profile ships:

- SSRF/private-network/redirect escape attempts fail closed;
- destination response size/time is bounded;
- signing verification vectors prove exact covered representation;
- timestamp/freshness metadata is authenticator-bound;
- timeout after subscriber receives request retries same delivery identity;
- duplicate delivery can be safely identified by documented external identity;
- tenant A cannot subscribe to tenant B events;
- payload filters cannot expand scope;
- secret rotation/revocation does not leak old/new secret;
- permanent failure reaches governed terminal/quarantine state;
- one failing subscriber does not exhaust global delivery capacity;
- restore to older local delivery state does not invent a new event identity;
- logs/errors do not leak payload/signature secrets.

## Intentionally OPEN

- whether/which Product webhook surfaces are enabled;
- exact external envelope field names beyond fixed semantics;
- signature algorithm/profile;
- key management backend;
- retry numeric policy;
- subscriber ordering profiles;
- delivery storage implementation;
- external hostname/egress implementation.

The tenant isolation, stable identity, SSRF boundary, bounded at-least-once delivery and authenticated payload properties are fixed.
