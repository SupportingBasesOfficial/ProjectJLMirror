# ADR-007 — Web BFF and API Boundary

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible/costly depending on client adoption

## Context

The web UI benefits from server-side session handling and composition, while the platform also needs direct APIs for automation/integrations. Making the browser own refresh/API credentials expands attack surface; making the API trust the BFF would break defense in depth.

Drivers: `FR-ID-002`, `FR-ID-004`, `FR-INT-001`, `INV-AUTHZ-001`, `SEC-ID-*`, `SEC-AUTHZ-*`.

## Decision

The web architecture SHALL use:

```text
Browser -> Web/BFF -> Versioned API -> Application modules
```

The BFF owns browser-specific confidential session handling, CSRF/session defenses, web composition and API credential mediation. Business rules remain in the API/application layer.

The API SHALL be independently secure and callable by authorized non-web clients. It SHALL NOT treat traffic as trusted merely because it originated from the BFF/network.

Public/integration API contracts SHALL be versioned and schema-defined. Transport DTOs SHALL NOT expose internal persistence representations by default.

The web delivery layer MAY use CDN/edge/serverless capabilities, but the core API contract must not rely on edge-only constraints.

## Consequences

### Positive
- reduced browser credential exposure;
- web and external clients share one authoritative business API;
- BFF can optimize web-specific aggregation without duplicating domain rules.

### Negative / cost
- one additional request hop for typical browser calls;
- session/BFF availability and CSRF policy require engineering;
- API version/contract discipline is mandatory.

## Validation

- browser JavaScript has no long-lived platform API secret;
- API rejects unauthorized direct calls regardless of BFF;
- CSRF/session fixation/logout/revocation scenarios tested;
- contract tests cover BFF/API compatibility.

## Exit / revisit conditions

Revisit only if web delivery model changes; API independence remains required by machine/integration actors.
