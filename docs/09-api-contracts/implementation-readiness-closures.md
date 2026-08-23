# Phase 09 — Implementation Readiness Closures

**Status:** proposed normative amendment  
**Owning gate:** Implementation Readiness

This file records explicit closure of Phase 09 OPEN decisions through a later accepted governance decision. The original OPEN IDs remain stable historical identifiers; this closure record is authoritative once merged.

## OPEN-API-001 — SATISFIED

**Closure decision:** `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-001--human-and-machine-authenticationtoken-profile`

Accepted concrete profile on gate acceptance:

- first-party human browser: OIDC Authorization Code Flow + PKCE S256 with the BFF as confidential client/token holder and an opaque host-bound browser session handle;
- external machine/API principal: OAuth 2.0 Client Credentials + asymmetric `private_key_jwt` client authentication + short-lived audience-bound access token;
- token/session validity never replaces current tenant/membership/permission/placement authority;
- IdP/session-store product remains replaceable C2 implementation choice.

**Compatibility:** any implementation that exposes long-lived platform credentials to browser JS, uses shared non-attributable machine credentials, or derives tenant authority from arbitrary token/client claims violates the closure.

No other `OPEN-API-*` item is closed by this file.
