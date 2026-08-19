# Browser BFF and Realtime Admission

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

This document translates the accepted browser/BFF and realtime security invariants into concrete Phase 09 HTTP/admission contracts without defining the Phase 10 realtime message/event envelope.

## Canonical HTTP ingress

BFF and realtime upgrade requests inherit `http-message-framing-and-canonicalization.md` before session/Origin/CSRF/ticket/replay logic consumes the request.

Therefore:

- ambiguous request framing is rejected before BFF authentication or state-changing handling;
- security-sensitive headers/cookies used by the BFF have one accepted cardinality/parse meaning;
- trusted proxy scheme/host/client metadata is accepted only from the configured proxy boundary;
- request-target normalization is identical at edge and BFF/owning service;
- a protected realtime request cannot receive `101` unless canonical HTTP ingress has already succeeded;
- gateway/proxy translation cannot cause the edge to validate one credential/Origin/ticket request while the application consumes another interpretation.

Exact gateway/runtime products remain implementation choices; the one-request/one-canonical-interpretation property does not.

## Browser boundary

The first-party Web application communicates with the BFF under:

```text
/bff/v1/...
```

The BFF is the confidential browser-session boundary. Browser JavaScript SHALL NOT intentionally receive or persist long-lived platform access credentials or refresh credentials.

The BFF may perform presentation-oriented aggregation/composition but SHALL NOT:

- own domain business rules;
- bypass downstream authorization;
- expose internal service topology;
- turn browser cookies into direct arbitrary API authority;
- persist provider/application secrets into client-readable state.

## Browser session

The exact identity-provider/token implementation remains separately selectable. The browser-facing session profile SHALL nevertheless provide:

- HttpOnly credential/session handling where cookies are used;
- Secure transport requirements;
- accepted same-site/cross-site policy;
- CSRF protection for state-changing BFF requests;
- logout/revocation behavior;
- session renewal without exposing platform refresh credentials to JavaScript;
- current authorization re-evaluation where required by the use case.

Cookie names and identity-provider-specific token shape are not Phase 09 business contracts.

Security-relevant session/CSRF cookie names SHALL NOT be interpreted differently by edge and BFF parsers. Duplicate/conflicting values for a security-relevant cookie or header fail closed unless the accepted browser profile defines one canonical parse rule that every hop shares.

## Browser origin/CORS boundary

Credentialed BFF access is deny-by-default across untrusted origins.

If deployment topology requires cross-origin browser access, the accepted browser profile SHALL use an explicit allowlist and credential policy. A wildcard origin with credentialed protected responses is prohibited.

CORS response headers are transport enforcement, not authorization. A request that passes CORS/Origin policy still requires the normal session, CSRF where applicable, tenant context and downstream owning authorization.

The exact allowed origins/hostnames remain deployment/profile configuration, but an arbitrary-origin credentialed BFF is not an accepted default.

Origin/scheme/host evaluation uses the canonical request plus trusted proxy metadata. Untrusted client-supplied forwarding headers cannot rewrite the effective protected origin or secure-scheme decision.

## BFF tenant scope

When a human can belong to multiple tenants, tenant-scoped BFF routes use explicit logical scope:

```text
/bff/v1/tenants/{tenant_id}/...
```

The BFF validates the human session and downstream APIs independently verify the resulting protected request context.

A browser-selected tenant ID is not placement authority.

## CSRF

State-changing browser BFF requests SHALL require the accepted anti-CSRF mechanism in addition to ambient session state.

A route that is safe only because a cookie has `SameSite` set is insufficient if the deployment/browser flow requires cross-site behavior or the accepted threat model requires stronger proof.

The exact CSRF token/header name may be implementation-specific until a browser session profile is accepted, but the requirement itself is mandatory.

A duplicate/conflicting anti-CSRF header/cookie presentation cannot be first-value-selected by one hop and last-value-selected by another. The browser profile declares its accepted cardinality and parser semantics.

## Protected realtime flow

The canonical browser flow is:

```text
Browser
  -> authenticated same-site BFF request
  -> BFF authorizes bounded realtime intent
  -> BFF mints short-lived single-use connection ticket
  -> Browser opens direct protected WebSocket using ticket + expected Origin
  -> Gateway accepts one canonical HTTP upgrade request
  -> Gateway validates current underlying authority + replay continuity
  -> Gateway atomically consumes ticket as final protected admission gate
  -> HTTP 101 only for the winner that passes every gate
  -> protected subscriptions separately authorize tenant/resource scope
```

## Ticket mint endpoint

Proposed browser contract:

```text
POST /bff/v1/tenants/{tenant_id}/realtime-tickets
```

The request MAY specify a bounded intended realtime scope/profile such as application area or allowed channel family. It SHALL NOT request arbitrary permission names beyond the human's current authority.

Successful response conceptually:

```json
{
  "ticket": "opaque-short-lived-single-use-value",
  "expires_at": "2026-08-18T22:30:00Z",
  "websocket_url": "wss://<logical-realtime-host>/realtime/v1/connect",
  "protocol_version": "1"
}
```

The ticket is a connection capability, not a platform access token.

The ticket-mint response is a secret-bearing `no_store` response. Browser/proxy/CDN caches SHALL NOT retain or replay the ticket, and the BFF endpoint SHALL NOT rely on infrastructure defaults for this behavior.

## Ticket secrecy

The ticket SHALL be:

- short-lived;
- random/unguessable or cryptographically protected as appropriate;
- bound to intended principal/tenant/realtime scope;
- single-use under the accepted baseline;
- redacted from normal logs/traces/error telemetry;
- unusable as a general HTTP API credential.

The BFF SHALL NOT store the ticket in long-lived browser storage. Client code SHOULD hold it only for the immediate connection attempt and discard it after use/failure.

## Ticket presentation

The exact browser-compatible presentation encoding is a transport detail, but the baseline requires that ticket evidence be available **before `101`** and be excluded/redacted from ordinary access logs.

An implementation may use a narrowly reviewed query parameter or another browser-compatible pre-upgrade representation. It SHALL NOT defer authentication to the first WebSocket message because the accepted architecture requires current authorization/replay admission before upgrade.

If a URL-carried representation is selected, ticket-bearing URLs are transient capability transport, not canonical/persistable URLs, and MUST be excluded from normal analytics, logs, histories and referrer-like propagation to the extent controllable by the platform profile.

Ambient cookies alone are not sufficient authority for the direct protected socket.

Ticket presentation has one canonical value at the accepted HTTP ingress. Duplicate/conflicting ticket/capability representations cannot be resolved differently across gateway replicas or proxy/application hops.

## Realtime endpoint

The logical protected endpoint is:

```text
/realtime/v1/connect
```

Before returning `101 Switching Protocols`, the gateway SHALL first accept the HTTP request under `http-message-framing-and-canonicalization.md`, then validate in order sufficient to preserve the accepted security contract:

- expected allowlisted browser `Origin` from the canonical request;
- ticket authenticity/integrity;
- ticket expiry;
- intended principal/tenant/realtime scope;
- current underlying session/credential state;
- current membership/permission/scope and tenant access;
- current trusted tenant placement/admission generation where applicable;
- pre-upgrade abuse/connection limits;
- replay-authority continuity/current epoch;
- atomic shared single-winner ticket consumption as the final admission mutation.

Any required failure rejects the HTTP handshake before `101`.

Ambiguous framing, conflicting authority/Origin/ticket input, invalid request-target interpretation or other canonical-ingress failure is itself sufficient to reject the upgrade before replay-ticket consumption.

## Single winner

Concurrent presentation of one single-use ticket to multiple gateway replicas yields at most one successful protected upgrade.

The winner is the request that atomically consumes the replay identity. Every loser is rejected before `101`.

A read-only "unused?" check or replica-local memory is prohibited.

## Burn-on-ambiguity

If a gateway consumes the ticket and crashes before completing `101`, the ticket remains consumed.

The browser obtains a fresh ticket through the BFF. Availability cost is preferred over reopening replay eligibility.

Canonical HTTP ingress failures occur before ticket consumption; they do not create a misleading partial admission state.

## Replay-authority loss

A consumed still-valid ticket SHALL NOT become usable after replay-store restart/loss/restore.

Missing replay state means rejection unless accepted continuity is re-established or a trusted replay epoch/generation advance invalidates outstanding old tickets.

## Rejection representation

A protected realtime admission failure MUST NOT receive `101`.

Pre-upgrade rejection uses safe HTTP status/problem representation appropriate to the failure class, for example authentication/authorization/throttling/unavailability. The response does not expose sensitive replay or authorization internals.

Transport/framing ambiguity rejection also avoids revealing which intermediary/parser would have accepted an alternate interpretation.

Browser UI may treat many security denials as "obtain a fresh ticket / reauthenticate / resync" rather than relying on exact hidden policy reason.

## Connection does not grant subscriptions

A successful `101` establishes only the bounded connection authority represented by the ticket.

Each protected subscription request later evaluates:

- current tenant/resource authorization;
- current placement/admission generation;
- subscription-specific scope.

The Phase 10 realtime message/subscription protocol SHALL preserve this separation.

## Revocation during connection lifetime

Long-lived connections do not freeze authority.

The gateway/runtime supports active invalidation and bounded revalidation for:

- session revocation;
- membership disable/revocation;
- permission/scope removal;
- tenant suspension/access denial;
- tenant relocation/placement-generation retirement.

A source socket remaining TCP-open after relocation does not make the retired tenant subscription authoritative.

## Relocation

The default relocation behavior is retire and resubscribe:

```text
source subscription generation N
 -> N retired
 -> affected subscription removed / connection closed
 -> browser obtains/uses current route
 -> fresh current authorization + target generation N+1
 -> subscribe
 -> API snapshot/resync
```

Transparent socket transfer is not assumed.

## Reconnect and resync

Realtime is advisory. After reconnect, gap, relocation or suspected missed events, the client uses authoritative API/read-model endpoints to resynchronize current state.

A realtime message stream SHALL NOT be the only durable source from which the UI can reconstruct critical business state.

## Public realtime

Any future unauthenticated/public realtime surface is a separate contract with deliberate public projections. It SHALL NOT inherit protected tenant topics or schemas merely by omitting authentication.

## Required ingress tests

The deployed BFF/realtime path SHALL test, where applicable:

- conflicting `Content-Length`/`Transfer-Encoding` or body length rejected before BFF session/state handling;
- duplicate/conflicting authentication/session/CSRF headers or security-relevant cookie names fail closed under the accepted profile;
- untrusted forwarding headers cannot spoof protected Origin/scheme/host;
- edge and BFF resolve one canonical tenant-scoped route/request target;
- duplicate/conflicting realtime ticket presentation cannot produce multiple interpretations;
- an ambiguously framed/targeted realtime handshake never receives `101`;
- HTTP-version translation does not make invalid upgrade/framing metadata acceptable;
- ordinary realtime replay/single-winner/current-auth tests still pass after gateway/proxy/runtime changes.

## Phase boundary

Phase 09 accepts:

- canonical HTTP ingress before BFF/realtime security logic;
- BFF browser-session boundary;
- logical ticket minting endpoint/profile;
- protected pre-`101` admission semantics;
- current authorization/replay/placement checks;
- single-winner ticket consumption;
- reconnect/resync responsibility.

Phase 10 defines:

- realtime message envelope;
- subscription request/ack format;
- sequence/cursor/replay fields;
- event naming/versioning;
- transport-level message delivery semantics.

Phase 10 may not weaken the Phase 09 canonical HTTP ingress or pre-upgrade security contract.