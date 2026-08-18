# ADR-007 — Web BFF and API Boundary

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible/costly depending on client adoption

## Context

The web UI benefits from server-side session handling and composition, while the platform also needs direct APIs for automation/integrations. Making the browser own refresh/API credentials expands attack surface; making the API trust the BFF would break defense in depth. Direct browser realtime connections add a cross-site WebSocket risk if ambient cookies alone authorize the socket.

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

The capability SHALL be short-lived, narrowly scoped to the principal/tenant/realtime purpose, non-refreshable as a general API credential, and single-use or otherwise replay-bounded according to its contract. The gateway SHALL validate an allowlisted expected `Origin` and the capability before protected subscription delivery.

An ambient HttpOnly session cookie by itself SHALL NOT authorize a protected direct WebSocket connection. Any future cookie-authenticated socket design requires an explicit security decision proving Origin validation plus an anti-CSRF/connection proof with equivalent protection.

Public unauthenticated endpoints are outside this protected exception and have their own exposure policy.

Public/integration API contracts SHALL be versioned and schema-defined. Transport DTOs SHALL NOT expose internal persistence representations by default.

The web delivery layer MAY use CDN/edge/serverless capabilities, but the core API contract must not rely on edge-only constraints.

## Consequences

### Positive
- reduced browser credential exposure;
- web and external clients share one authoritative business API;
- BFF can optimize web-specific aggregation without duplicating domain rules;
- cross-site pages cannot gain protected WebSocket access merely by causing ambient cookies to be attached.

### Negative / cost
- one additional request hop for typical browser calls;
- session/BFF availability and CSRF policy require engineering;
- direct realtime needs a connection-ticket mint/validation lifecycle;
- API version/contract discipline is mandatory.

## Validation

- browser JavaScript has no long-lived platform API secret;
- API rejects unauthorized direct calls regardless of BFF;
- CSRF/session fixation/logout/revocation scenarios tested;
- hostile/untrusted/null Origin direct WebSocket handshakes are rejected for protected browser realtime;
- stolen/replayed/expired/wrong-tenant connection capability is rejected;
- ambient cookie alone cannot establish a protected direct browser socket;
- contract tests cover BFF/API compatibility.

## Exit / revisit conditions

Revisit only if web delivery model changes; API independence remains required by machine/integration actors and protected browser realtime must preserve equivalent cross-site defenses.
