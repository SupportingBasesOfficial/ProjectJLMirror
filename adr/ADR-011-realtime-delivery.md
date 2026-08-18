# ADR-011 — Realtime Delivery Semantics

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible at transport layer

## Context

Operators need near-real-time alerts, health/state updates and execution progress. Realtime transport is lossy across reconnects and multi-replica fanout; treating it as authoritative creates missed-state and duplicate-delivery bugs. Tenant/topic collisions are a security risk. Long-lived connections also outlive individual authorization decisions, so authorization checked only at connect/join time can become stale after membership, permission, session or tenant-state changes. Browser WebSockets additionally require explicit cross-site handshake protection because ambient cookies can be attached by a hostile origin and unauthenticated upgrades can consume persistent gateway resources. A short-lived connection capability is not sufficient by itself if authorization is revoked after issuance but before presentation, and single-use/replay-bounded semantics are not sufficient if multiple gateway replicas can concurrently observe the same capability as unused.

Drivers: `FR-ALT-002`, `FR-ALT-004`, `INV-REALTIME-001`, `SEC-AUTHZ-*`, `SEC-BROWSER-*`, `SEC-ABUSE-*`, `TM-003`, `TM-004`, `QA-OBS-001`.

## Decision

JLMIRROR SHALL use **WebSocket** as the initial authenticated browser realtime transport for operational subscriptions. The transport is a notification/update channel, not durable business truth.

### Browser connection establishment

A protected first-party browser socket SHALL use a BFF-mediated short-lived connection capability as defined by ADR-007.

The realtime gateway MUST complete all required protected-connection admission checks **before accepting the WebSocket upgrade**, including:

- allowlisted expected browser `Origin`;
- capability authenticity, expiry and principal/tenant/realtime scope;
- current session/membership/permission/tenant-access authorization for the capability scope, established through a fresh authoritative decision or a trusted current authorization/session generation/revocation marker;
- applicable pre-upgrade connection/rate/abuse limits;
- final atomic claim/consume of the capability's replay identity in shared state before returning `101`.

For a single-use capability, the consume is a shared single-winner transition. Concurrent presentations of the same capability to multiple replicas MUST permit at most one winner to complete protected admission; every loser is rejected before upgrade. A simple read of replay state followed by later best-effort marking is prohibited because it admits a check-then-act race across replicas.

If replay state is unavailable or cannot provide atomic single-winner semantics, new protected upgrade admission fails closed. If the winning gateway consumes the capability and then fails before the socket upgrade completes, the capability stays consumed and the client mints a new one; a consumed-but-unused capability is an accepted availability cost, not permission to replay.

The capability records/proves an authorization decision at issuance time; it MUST NOT be treated as an immutable authorization lease through its full expiration window. If current authorization cannot be safely established, a new protected upgrade fails closed.

Invalid, missing, null/untrusted-origin, expired, replayed, replay-losing, wrong-scope, stale-authorization or revoked-authority handshakes are rejected at HTTP handshake time and MUST NOT receive a successful `101 Switching Protocols` response or become retained protected connections.

Ambient session cookies alone SHALL NOT authorize a protected direct browser socket.

The capability is narrowly scoped to the principal/tenant/realtime purpose, expires quickly, is non-refreshable as a general API credential and is single-use or otherwise replay-bounded according to the accepted contract. A capability MAY carry an authorization/session generation/version, but the gateway must compare that marker with trusted current state rather than accepting it as self-authorizing after revocation. Public unauthenticated realtime/status paths, if any, are separate contracts with their own admission/rate-limit policy.

Every protected connection/subscription SHALL be authenticated and authorized before joining a tenant/resource scope. Fanout keys/channels use canonical tenant-aware namespaces. Realtime messages carry stable event/update ID, schema version, tenant scope, resource/topic and correlation metadata where applicable.

### Authorization freshness and revocation

Authorization is not a one-time handshake property. A realtime gateway MUST stop protected delivery when the principal/session/membership/permission/tenant state no longer authorizes a subscription.

The implementation SHALL support all of the following semantics:

- protected connection establishment evaluates authorization that is current at handshake time, not merely at capability issuance;
- capability replay/redemption uses shared atomic single-winner semantics before `101`;
- every new protected subscription evaluates current authorization;
- authorization/session/membership changes that can remove access produce an invalidation/revocation signal or equivalent mechanism capable of reaching active realtime gateways;
- affected subscriptions are re-evaluated and removed, or the connection is terminated, when access is revoked;
- periodic bounded revalidation provides defense in depth when an invalidation signal is missed or delayed;
- reconnect always performs fresh authentication/authorization rather than inheriting prior subscription authority;
- a gateway that cannot safely establish current authorization or capability-consumption uniqueness fails closed for new protected admission/delivery;
- any accepted propagation/revalidation delay is explicitly bounded by a later security/SLO policy rather than being unlimited.

An authorization generation/version or equivalent freshness marker MAY be used so gateways can detect stale authorization state without embedding mutable permission sets as permanent socket authority.

Clients SHALL tolerate duplicate delivery, reconnect and missed transient messages. On reconnect/gap detection, clients re-query authoritative API/read models or use a bounded replay mechanism where a feature explicitly provides one.

Durable events/jobs and database state remain authoritative. Ephemeral pub/sub may be used behind the gateway but loss of ephemeral fanout must not corrupt business state.

## Consequences

### Positive
- strong fit for interactive NOC/operator experience;
- horizontally scalable gateways are possible without allowing duplicate redemption of a single-use capability;
- no false exactly-once promise;
- reconnect semantics are explicit;
- revocation/permission changes do not leave indefinitely authorized stale sockets;
- revocation between capability mint and presentation cannot obtain protected socket admission merely because the capability has not expired;
- protected browser upgrades fail before persistent socket admission when cross-site/capability/current-authorization/replay-consumption checks fail.

### Negative / cost
- connection lifecycle/heartbeats/backpressure need operations;
- authorization invalidation and periodic revalidation add coordination/load;
- BFF connection-capability minting and shared atomic replay-consumption add a browser realtime control path;
- pre-upgrade Origin/capability/current-authorization/admission/consume validation must be available on the handshake path;
- fail-safe consume-before-upgrade can burn a capability on gateway failure and require remint;
- some edge/serverless platforms may be unsuitable for long-lived connections;
- replay/current-state query paths must exist.

## Validation

Test cross-tenant subscription attempts, reconnect storms, duplicate delivery, gateway restart, fanout dependency failure and stale authorization.

A release test MUST establish a protected subscription, then revoke membership/permission/session or suspend tenant access and verify that protected delivery stops according to the accepted bounded revocation policy without waiting for a manual reconnect. Failure to terminate/restrict a known unauthorized live subscription is release-blocking.

Handshake security tests MUST mint a valid connection capability, then revoke/suspend the underlying session, membership, permission/scope or tenant access **before the capability is presented** and verify the protected handshake is rejected before upgrade despite a still-valid capability signature/expiry.

Replay-concurrency tests MUST present one single-use capability concurrently to multiple gateway replicas and prove exactly one atomic consume winner and at most one successful `101`; every losing handshake must be rejected before upgrade. A fault test MUST also crash the winner after successful consume but before `101` and prove subsequent presentation remains rejected and requires a newly minted capability.

Security tests MUST also verify protected first-party browser handshakes from untrusted/null origins, with expired/replayed/wrong-scope/wrong-tenant capabilities, or with ambient cookie alone are rejected **before upgrade** and never receive `101`/persistent protected socket admission.

A missed realtime frame must be recoverable through authoritative state.

## Exit / revisit conditions

SSE or another transport may replace/supplement WebSocket for unidirectional/public workloads if it materially reduces cost/complexity while preserving these authorization, atomic replay-consumption, pre-admission cross-site and recovery semantics.
