# Realtime Subscription and Message Protocol

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

Phase 09 owns protected realtime admission and subscription authority lifecycle. This document defines the **Phase 10 message protocol representation after admission** without weakening those authority invariants.

The protocol is designed so browser clients can miss messages, reconnect, relocate between cells and coexist with rolling deployments without treating the socket as authoritative state.

## Phase boundary

Phase 09 remains authoritative for:

- BFF-minted bounded connection capability;
- expected `Origin`;
- current session/credential/membership/permission/tenant authority before `101`;
- replay-authority continuity;
- atomic single-winner capability consumption before `101`;
- current authorization for every protected subscription;
- bounded authorization freshness/active invalidation during subscription lifetime;
- current placement/admission generation;
- retirement of subscriptions/connections after revocation or relocation.

Phase 10 defines:

- client subscription request representation;
- subscription acknowledgement/error representation;
- server event/projection message representation;
- optional resume/cursor representation;
- protocol compatibility/version negotiation if/when required;
- resynchronization control messages.

A Phase 10 message cannot override a Phase 09 denial or restore authority to a retired subscription.

## Realtime transport

The initial protected first-party realtime transport is WebSocket under the Phase 09 `/realtime/v1/...` admission surface.

This does not make WebSocket the domain contract. A future compatible transport may map the same logical protocol semantics if explicitly accepted.

## Message serialization

For the first-party browser protocol, messages use a bounded structured JSON profile unless a future accepted protocol revision selects another encoding.

JSON parsing inherits the same fail-closed principles used elsewhere:

- bounded frame/message bytes;
- bounded nesting/collection/string sizes;
- duplicate object member names rejected;
- aliasing member names after accepted normalization rejected;
- unknown message type rejected or handled by the negotiated compatibility profile;
- no first/last/merge semantics for duplicate protected fields.

Compression, binary frames and exact numeric bounds remain OPEN.

## Protocol envelope

Every realtime protocol message contains:

```json
{
  "message_type": "...",
  "protocol_version": "1",
  "request_id": "...",
  "subscription_id": "...",
  "payload": {}
}
```

Field applicability depends on message type.

`protocol_version` here is explicitly the **Phase 10 realtime message protocol version**. It is not the Phase 09 ticket/admission contract version, API major version, deployment version or event contract version.

## Client-generated `request_id`

A client sends an opaque bounded `request_id` for request/ack correlation.

It is not:

- authentication;
- idempotency for business effects;
- tenant scope;
- subscription authority;
- trace authority.

The server echoes it only under the accepted bounded safe-value profile.

## `subscription_id`

A subscription receives a server-authoritative opaque `subscription_id` after successful subscription admission.

Rules:

- scoped to the current realtime connection/session context;
- not a globally reusable bearer credential;
- not authorization outside that connection;
- may change on reconnect/resubscribe;
- never encodes physical cell/database/provider identity;
- retirement/Phase 09 invalidation makes the subscription non-authoritative regardless of the ID still being known by the client.

A client may suggest a correlation label, but only the server-issued `subscription_id` identifies the active server subscription.

## Subscribe request

Logical client request:

```json
{
  "message_type": "subscribe",
  "protocol_version": "1",
  "request_id": "req_client_opaque",
  "payload": {
    "contract_name": "...",
    "contract_version": "...",
    "tenant_id": "tenant_opaque",
    "scope": {},
    "resume": null
  }
}
```

`contract_name` identifies the realtime projection/subscription contract, not a broker topic.

`scope` is contract-specific bounded logical resource/query scope. It SHALL NOT contain physical placement selectors or provider-native routing authority.

The gateway applies current Phase 09 subscription authorization to the requested tenant/resource scope before accepting it.

## Subscription acknowledgement

Success:

```json
{
  "message_type": "subscription_ack",
  "protocol_version": "1",
  "request_id": "req_client_opaque",
  "subscription_id": "sub_opaque",
  "payload": {
    "status": "active",
    "resync_required": false,
    "resume": null
  }
}
```

The acknowledgement means only that the protected subscription is currently admitted under the current authorization/placement authority.

It does not promise that:

- the stream contains complete historical state;
- future authority cannot be revoked;
- every business event will be retained indefinitely;
- the connection cannot be retired during relocation.

## Subscription rejection

Failure uses a bounded stable code:

```json
{
  "message_type": "subscription_error",
  "protocol_version": "1",
  "request_id": "req_client_opaque",
  "payload": {
    "code": "realtime.subscription_not_authorized"
  }
}
```

External error detail remains sparse and does not reveal:

- hidden resource existence;
- physical cell/placement;
- authorization internals;
- provider topology;
- replay-state detail.

Representative stable classes may include:

```text
realtime.invalid_request
realtime.unsupported_contract
realtime.subscription_not_authorized
realtime.subscription_not_admitted
realtime.resync_required
realtime.rate_limited
realtime.temporarily_unavailable
```

Exact codes are governed contract metadata.

## Server projection message

Logical message:

```json
{
  "message_type": "event",
  "protocol_version": "1",
  "subscription_id": "sub_opaque",
  "payload": {
    "message_id": "msg_opaque",
    "contract_name": "monitoring.example.changed",
    "contract_version": "1",
    "tenant_id": "tenant_opaque",
    "subject": {
      "subject_type": "resource",
      "subject_id": "resource_opaque"
    },
    "occurred_at": "...",
    "correlation_id": "corr_opaque",
    "sequence": null,
    "data": {}
  }
}
```

Example names/data are illustrative only.

The projection contract controls `data`. Clients do not infer domain truth from transport fields not documented by that contract.

## Realtime message identity

`message_id` identifies the logical realtime projection message and remains stable for exact redelivery/replay within the channel contract.

It may be the underlying integration-event identity when the projection is a direct projection of that event, or a distinct projection identity when the realtime message aggregates/transforms state. The contract declares the relationship.

A realtime `message_id` is not authorization or business idempotency authority.

## Sequence and resume

A subscription MAY support resume/replay using a bounded opaque `resume` token or sequence/cursor.

The contract declares:

- whether resume exists;
- retention/replay window;
- sequence scope;
- whether gaps are detectable;
- token data classification;
- behavior after expiration/relocation/version change.

A resume token:

- is not authorization;
- does not freeze placement or membership;
- cannot bypass Phase 09 current subscription authority;
- may be invalidated on recovery/retention/generation changes;
- is kept out of logs when sensitive.

## Resync required

When the gateway cannot provide a trustworthy continuous stream — for example due to:

- missed retention window;
- detected sequence gap;
- relocation/source-generation retirement;
- replay continuity uncertainty;
- incompatible protocol/contract transition;
- server restart/state loss under a non-durable channel;

the server sends/returns a `resync_required` outcome or retires the subscription/connection so the client performs authoritative API/read-model resynchronization.

Representative control message:

```json
{
  "message_type": "resync_required",
  "protocol_version": "1",
  "subscription_id": "sub_opaque",
  "payload": {
    "code": "realtime.resync_required"
  }
}
```

The client then:

1. retrieves authoritative state through the current API/read model;
2. obtains current placement/authorization through normal routing;
3. creates a fresh subscription;
4. treats the new snapshot as truth.

## Realtime is not authority

A client SHALL NOT make an irreversible business decision solely because a realtime projection says state changed if the owning workflow requires authoritative confirmation.

UI components may optimistically update from realtime but must recover from missed/duplicate/out-of-order messages through accepted snapshot/read behavior.

## Duplicate messages

Clients should tolerate duplicate realtime events.

Where application state needs deduplication, clients may use `message_id` within the documented channel window. Duplicate suppression is an optimization; server/business correctness does not depend on browser dedup state.

## Out-of-order messages

If the contract is unordered, clients treat later authoritative snapshot/API reads as resolution.

If an ordered realtime contract exposes sequence, clients follow its gap/stale rules. They do not assume WebSocket frame order equals business order across reconnects, sources or subscriptions.

## Subscription authority lifecycle

The protocol SHALL expose no message that says "keep this subscription authorized" independently of Phase 09 authority.

When Phase 09 detects:

- session/logout revocation;
- membership/permission/scope removal;
- tenant suspension/access denial;
- placement/admission generation retirement;

protected delivery stops within the accepted security bound.

The server may send a safe control/error before closing/removing the subscription when possible, but notification is best-effort. Security does not depend on the client receiving the explanation.

## Multi-tenant connection

A single connection may host multiple authorized subscriptions when accepted by the deployment profile.

Each subscription independently carries:

- tenant scope;
- resource scope;
- current authorization lifecycle;
- current placement generation.

Retiring one tenant subscription does not require terminating unrelated valid subscriptions if the gateway can prove isolation. If it cannot, closing the connection is acceptable fail-closed behavior.

## Subscribe/Unsubscribe races

An `unsubscribe` request references the server `subscription_id`:

```json
{
  "message_type": "unsubscribe",
  "protocol_version": "1",
  "request_id": "req_client_opaque",
  "subscription_id": "sub_opaque",
  "payload": {}
}
```

Unsubscribe is idempotent at the protocol level. Repeating it cannot recreate authority.

Messages already in transport buffers may race with unsubscribe. Client/server contracts therefore do not promise a perfect "last frame" unless a future stronger drain/fence profile is accepted.

Security-sensitive revocation/placement retirement uses server-side delivery fencing and is not equivalent to best-effort client unsubscribe.

## Backpressure

Realtime fanout is bounded per connection/subscription/tenant/workload.

If a slow client cannot keep up, the server may:

- drop non-authoritative projection messages and require resync;
- coalesce safe state-change hints where the contract permits;
- retire the subscription;
- close the connection.

It SHALL NOT buffer unbounded confidential messages in memory.

The contract declares whether messages are individually significant or safely coalescible.

## Heartbeat/liveness

Transport ping/pong/heartbeat may be used for liveness. It carries no authorization or business semantics.

Exact interval/frame behavior remains deployment/protocol OPEN unless client interoperability requires it.

## Protocol versioning

`protocol_version = "1"` identifies this first accepted Phase 10 realtime message protocol family.

Within protocol major 1:

- additive optional fields may be introduced under compatibility rules;
- clients ignore documented compatible unknown fields;
- existing message types do not silently change semantic meaning;
- new required semantics that old clients cannot safely understand require a new protocol major or explicit negotiation mechanism.

Event/projection `contract_version` evolves independently from `protocol_version`.

A new domain event version does not automatically require realtime protocol version 2.

## Contract negotiation

Initial protocol uses the version associated with the accepted endpoint/client profile. Explicit multi-version negotiation remains OPEN until needed.

The platform SHALL NOT overload event `contract_version` as transport protocol negotiation.

## Security/data classification

Realtime messages follow payload data classification.

Rules:

- no long-lived platform credentials/secrets in messages;
- no physical topology/provider secrets;
- protected payload delivered only on currently authorized subscriptions;
- message contents are not copied into ordinary gateway logs;
- browser devtools visibility is treated as user-accessible data, so only data the authorized user may receive is sent;
- URLs/cursors/capabilities are not emitted casually into payloads.

## Reconnect

Reconnect always re-enters Phase 09 admission:

```text
fresh BFF connection capability
-> current Origin/auth/tenant/placement/replay admission
-> 101
-> fresh subscription requests
-> current subscription authorization
-> snapshot/resync when needed
```

An old socket/session/subscription ID is not migrated as authority to a new connection.

## Required tests

Protocol implementations test:

- duplicate JSON protected members rejected;
- malformed/oversized message fails boundedly;
- subscribe cannot select physical cell/provider routing;
- unauthorized tenant/resource scope rejected without existence leakage;
- logout/session revocation after active subscription stops delivery;
- membership/permission removal stops delivery;
- tenant relocation retires old-generation delivery and forces resubscribe/resync;
- resume token cannot bypass current authority;
- detected gap/retention loss produces resync rather than silent state divergence;
- duplicate/out-of-order events do not corrupt client recovery path;
- slow consumer causes bounded coalesce/drop/resync/close rather than unbounded buffer;
- protocol version and event contract version evolve independently;
- unsubscribe does not restore/recreate authority;
- reconnect requires fresh Phase 09 admission.

## Intentionally OPEN

- exact WebSocket hostname/topology;
- compression/binary frame support;
- numeric message/frame/backpressure limits;
- heartbeat interval;
- resume retention window/token encoding;
- explicit protocol negotiation mechanism;
- fanout/pubsub product;
- exact close codes where not required for interoperability.

The Phase 09 authority lifecycle, bounded message model, resync safety and protocol/event-version separation are fixed.
