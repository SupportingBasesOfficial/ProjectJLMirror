# Phase 09 — Implementation Readiness Closures

**Status:** proposed normative amendment  
**Owning gate:** Implementation Readiness

This file records explicit closure of Phase 09 OPEN decisions through a later accepted governance decision. The original OPEN IDs remain stable historical identifiers; this closure record is authoritative once merged.

## OPEN-API-001 — SATISFIED on gate acceptance

**Closure decisions:**

- human/external-machine profile: `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-001--human-and-external-machine-authenticationtoken-profile`;
- internal-service credential/authentication portion: `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md#ir-d-002--internal-workload-identity-and-service-authentication`.

Accepted concrete profile on gate acceptance:

- first-party human browser: OIDC Authorization Code Flow + PKCE S256 with per-transaction `state`/`nonce`, the BFF as confidential client/token holder and an opaque host-bound browser session handle;
- privileged human operations consume current Security MFA/step-up/re-authentication assurance in addition to current authorization;
- external machine/API principal: OAuth 2.0 Client Credentials + asymmetric `private_key_jwt` client authentication + short-lived audience-bound access token;
- machine assertion replay protection uses unique `jti`, one logical atomic single-winner replay authority across token-boundary replicas, fail-closed behavior when unused-state/continuity cannot be proven, and recovery semantics that do not make missing replay state mean unused;
- internal service principal: SPIFFE-compatible short-lived workload identity, X.509-SVID-compatible certificate profile and mTLS peer authentication, with application authorization remaining separate;
- token/session/certificate validity never replaces current tenant/membership/permission/placement authority;
- raw auth codes/tokens/session handles/private keys remain outside ordinary telemetry/configuration;
- IdP/session-store/workload-identity issuer/replay-store products remain replaceable C2 implementation choices so long as they conform to the accepted protocol/trust/replay profiles.

**Compatibility:** any implementation that exposes long-lived platform credentials to browser JS, weakens required MFA/step-up assurance, uses shared non-attributable machine credentials, accepts replay assertions through replica-local/fail-open state, treats service mTLS identity as tenant authorization, or derives tenant authority from arbitrary token/client/workload claims violates the closure.

No other `OPEN-API-*` item is closed by this file.
