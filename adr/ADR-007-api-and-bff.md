# ADR-007 — Web BFF and API Boundary

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible/costly depending on client adoption

## Context

The web UI benefits from server-side session handling and composition, while the platform also needs direct APIs for automation/integrations. Making the browser own refresh/API credentials expands attack surface; making the API trust the BFF would break defense in depth. Direct browser realtime connections add a cross-site WebSocket risk if ambient cookies alone authorize the socket. A BFF-minted realtime capability also cannot be treated as proof that authorization remains current if session, membership, permission or tenant access changes after issuance. In a horizontally scaled realtime gateway, replay protection is also unsafe if replicas merely read an "unused" capability state concurrently; a single-use capability needs a shared atomic consume/claim operation so exactly one handshake can win. Replay protection also fails if that shared authority can forget a previously consumed capability while its signed token is still cryptographically valid, because missing state could otherwise be misinterpreted as unused.

Drivers: `FR-ID-002`, `FR-ID-004`, `FR-INT-001`, `INV-AUTHZ-001`, `SEC-ID-*`, `SEC-AUTHZ-*`, `SEC-BROWSER-*`.

## Decision

The web architecture SHALL use:

```text
Browser -> Web/BFF -> Versioned API -> Application modules
```

The BFF owns browser-specific confidential session handling, CSRF/session defenses, web composition and API credential mediation. Business rules remain in the API/application layer.

The API SHALL be independently secure and callable by authorized non-web clients. It SHALL NOT treat traffic as trusted merely because it originated from the BFF/network.

### Direct browser realtime exception

A protected first-party browser WebSocket/realtime connection MAY connect directly to the realtime gateway only through an explicitly designed browser connection contract. The preferred baseline is:

```text
Browser -> BFF (authenticated same-site request)
        -> short-lived scoped connection capability
Browser -> Realtime Gateway (capability + expected Origin)
```

The capability SHALL be short-lived, narrowly scoped to the principal/tenant/realtime purpose, non-refreshable as a general API credential, and single-use or otherwise replay-bounded according to its contract.

For a **protected** browser WebSocket, the gateway SHALL validate all of the following **before accepting the HTTP upgrade and before returning `101 Switching Protocols`**:

- allowlisted expected `Origin`;
- capability authenticity, expiry and principal/tenant/realtime scope;
- current session/membership/permission/tenant-access authorization for that scope, using a fresh authoritative evaluation or a trusted current authorization/session generation/revocation marker;
- applicable pre-upgrade admission/abuse limits;
- and an atomic replay-admission claim/consume against shared capability state immediately before successful upgrade admission.

For single-use capabilities, replay protection SHALL be a single-winner state transition keyed by a stable capability identity/nonce/JTI or equivalent. Concurrent presentations to different gateway replicas MUST result in at most one successful consume and at most one protected upgrade; every losing presentation is rejected before `101`. A bounded-use capability, if explicitly selected later, requires an equivalently atomic bounded counter/claim contract.

A pre-upgrade read such as "capability appears unused" is insufficient. The shared consume authority must serialize competing replicas. If that authority is unavailable or cannot establish single-winner consumption, the protected upgrade fails closed.

### Replay-authority continuity

A cryptographically valid capability MUST NOT become redeemable merely because replay-state storage restarted, was restored from an older point, was reinitialized, or lost a nonce/receipt. **Missing replay state is never interpreted as unused.**

The accepted implementation SHALL provide one of these equivalent fail-safe contracts, or a stronger one:

1. **registered capability state:** before the BFF returns a capability to the browser, its stable capability identity and accepted use bound are durably/continuously registered in the shared replay authority; admission requires that registered record to exist, and consumed state is retained at least through capability expiry plus accepted clock/retry safety margin; or
2. **replay epoch/generation:** the signed capability is bound to a replay-authority epoch/generation whose current value is trustworthy across replicas; replay-authority loss/reinitialization advances the epoch before protected admission resumes, thereby invalidating every capability minted under the lost epoch.

If replay authority is restored from an older snapshot, its state/epoch MUST be reconciled so a previously consumed capability cannot become eligible again. If the platform cannot prove replay-state continuity or establish a safely advanced current epoch, protected admission remains fail closed and clients remint capabilities only after the authority is safe.

The consume operation is the final replay-admission gate after the other required validation succeeds. If a gateway consumes the capability but fails before completing the HTTP upgrade, the capability remains consumed and the browser must request a new one; sacrificing that one capability is preferable to ambiguous reuse.

The connection capability proves an authorization decision at mint time but does not freeze authorization until capability expiry. A capability-carried authorization/session generation is a reference that must be compared with trusted current state. If current authorization cannot be established safely, the protected upgrade fails closed.

An invalid, absent, expired, replayed, replay-losing, wrong-scope, wrong-tenant, stale-authorization, revoked-authority, untrusted-origin or null-origin request is rejected at the HTTP handshake and is not retained as an upgraded protected socket.

An ambient HttpOnly session cookie by itself SHALL NOT authorize a protected direct WebSocket connection. Any future cookie-authenticated socket design requires an explicit security decision proving Origin validation, current authorization plus an anti-CSRF/connection proof with equivalent protection before upgrade.

Public unauthenticated endpoints are outside this protected exception and have their own exposure policy.

Public/integration API contracts SHALL be versioned and schema-defined. Transport DTOs SHALL NOT expose internal persistence representations by default.

The web delivery layer MAY use CDN/edge/serverless capabilities, but the core API contract must not rely on edge-only constraints.

## Consequences

### Positive
- reduced browser credential exposure;
- web and external clients share one authoritative business API;
- BFF can optimize web-specific aggregation without duplicating domain rules;
- cross-site pages cannot gain or retain protected WebSocket connections merely by causing ambient cookies to be attached;
- a capability minted before revocation cannot establish a protected socket solely because it remains cryptographically valid;
- concurrent replicas cannot both redeem the same single-use capability;
- replay-authority restart/loss cannot turn a previously consumed capability into an apparently unused one;
- invalid protected socket attempts are rejected before consuming long-lived gateway connection resources.

### Negative / cost
- one additional request hop for typical browser calls;
- session/BFF availability and CSRF policy require engineering;
- direct realtime needs a connection-ticket mint/validation lifecycle, current-authorization check and shared atomic replay-consumption authority on the pre-upgrade path;
- replay authority needs continuity across the capability validity window or an epoch/generation mechanism that safely invalidates outstanding capabilities after state loss;
- fail-safe consume-before-upgrade semantics can burn a capability if the gateway fails after claim and before `101`, requiring the browser to mint another;
- replay-authority recovery may invalidate all outstanding capabilities in an affected epoch, which is an accepted availability cost;
- API version/contract discipline is mandatory.

## Validation

- browser JavaScript has no long-lived platform API secret;
- API rejects unauthorized direct calls regardless of BFF;
- CSRF/session fixation/logout/revocation scenarios tested;
- hostile/untrusted/null Origin direct WebSocket handshakes are rejected before `101` for protected browser realtime;
- stolen/replayed/expired/wrong-tenant/wrong-scope connection capability is rejected before upgrade;
- concurrent presentation of one single-use capability to multiple gateway replicas yields exactly one atomic consume winner and at most one `101`; every loser is rejected;
- failure after successful capability consume but before `101` leaves that capability unusable and requires minting a new one rather than permitting replay;
- replay-authority restart/loss is tested while a consumed capability remains cryptographically valid; the old capability remains rejected, either because its registered consumed state survives or because a new replay epoch invalidates all capabilities from the lost epoch;
- missing capability state after authority recovery is rejected and is never treated as an unused capability;
- a valid capability minted before session/membership/permission/tenant revocation is rejected if the underlying authority is no longer current when presented;
- ambient cookie alone cannot establish a protected direct browser socket;
- invalid protected socket attempts are not retained as upgraded idle connections;
- contract tests cover BFF/API compatibility.

## Exit / revisit conditions

Revisit only if web delivery model changes; API independence remains required by machine/integration actors and protected browser realtime must preserve equivalent cross-site, current-authorization, single-winner replay-consumption, replay-authority continuity and pre-upgrade admission defenses.
