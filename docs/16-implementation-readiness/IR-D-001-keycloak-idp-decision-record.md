# IR-D-001 Decision Record — Keycloak as the Human Identity Provider

**Status:** proposed — mechanism selected; two closure conditions below are binding before this record satisfies the IdP-product C2 residual
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` — "the exact IdP product... remain[s] a C2 choice under [its] existing fixed semantics")
**Drivers:** `SEC-ID-001`, `SEC-ID-002`, `TM-013`, `ADR-005`, `ADR-017`, `AP-03`, `IR-D-001` (OIDC Authorization Code Flow + PKCE + BFF confidential session)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: Keycloak is a concrete instantiation of the already-accepted protocol shape (IR-D-001's canonical OIDC/PKCE/BFF-session profile, ADR-005's identity/membership/authorization separation) and does not redefine architecture. It was produced from an adversarial multi-round red/blue-team review of the candidate decision against the accepted repository baseline; the review's own confirmed findings are what this record closes.

## Context and problem

`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` fixes the protocol shape (OIDC Authorization Code Flow + PKCE S256 + BFF confidential session) but explicitly leaves "the exact IdP product... [as] a C2 choice under its existing fixed semantics." This record selects Keycloak as that product and, per the closure-evidence rule in `docs/16-implementation-readiness/03-consolidated-open-decision-register.md`, records the conditions required before the selection is canonical.

## Requirements and invariants this selection must satisfy

- Identity/membership/authorization separation (`adr/ADR-005-identity-and-authorization.md:15-27`): Keycloak authenticates human principals only; it does not redefine tenant membership semantics.
- `AP-03` (`docs/00-foundation/architecture-principles.md:11-13`): external identity providers are adapters behind a stable port; their native model must not become the platform's ubiquitous language.
- `SEC-ID-001`/`SEC-ID-002` (`docs/05-security/security-requirements.md:7,9`): credentials are independently revocable; privileged access supports MFA/step-up.
- `ADR-017`'s baseline dependency-failure categories (`adr/ADR-017-availability-and-degradation.md:19-24`): every runtime dependency declares a failure mode; "security authority unavailable" fails closed unless a separately documented durable/local verification path remains valid.
- IR-D-001's revocation rule (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:33`): logout/revocation/session retirement invalidates server-side session authority even if a browser cookie remains present — the BFF session, not the raw Keycloak token, is the enforcement point.

## Decision

Keycloak is selected as the human identity provider, integrated exclusively behind the BFF per IR-D-001's canonical profile. Browser JavaScript never receives a Keycloak token; the BFF exchanges the authorization code server-side and issues only its own opaque session handle.

Selection is conditioned on the two closure requirements below, both confirmed by adversarial review as real gaps in the candidate decision as originally stated (not hypothetical implementation risk):

### Closure condition 1 — IdP-side revocation back-channel (binding, high severity)

Every other revocation class in this repository — session, membership, permission, tenant suspension — gets an explicit, tested propagation bound (`adr/ADR-011-realtime-delivery.md:116-118`; `SEC-AUTHZ-004`; `docs/09-api-contracts/browser-bff-and-realtime-admission.md:230-244`). An administrator disabling a Keycloak account or forcing logout at the IdP had no defined channel into the BFF's authoritative session fence — the BFF's silently-renewed opaque session could keep serving requests indefinitely with no wired back-channel.

**Requirement:** the BFF SHALL implement OIDC Back-Channel Logout 1.0 (`logout_token` receipt at a dedicated BFF endpoint) as a required, not optional, wired integration. This is an authenticated inbound provider callback and SHALL be implemented under ADR-013's existing inbound-callback framework (`adr/ADR-013-external-provider-architecture.md:31-50`) unchanged for its generic parts — bounded raw-body size, provider authentication before effects, issuer/audience binding, freshness and replay handling — but this concrete profile makes the cryptographic JWT checks explicit so an implementer cannot mistake claim validation for authenticity.

Before trusting **any** `logout_token` claim or resolving a BFF session, the BFF SHALL:

1. parse only within the accepted bounded callback/JWT size limits;
2. cryptographically verify the JWS signature against the currently trusted Keycloak signing-key set for the configured issuer/client;
3. enforce an explicit allowed-signature-algorithm policy chosen by trusted configuration, not by attacker-controlled token header alone; `alg=none`, an unexpected algorithm, an unknown/retired key, or signature failure is rejection;
4. resolve `kid` only against trusted Keycloak/JWKS configuration and bounded key-rotation logic; token-supplied `jku`, `x5u` or equivalent remote-key indirection SHALL NOT select an arbitrary verification endpoint;
5. only after signature/key/algorithm verification, verify `iss`/`aud` against the registered Keycloak issuer/client and process the protocol-specific claims below.

ADR-013 already mandates provider signature/authentication verification before domain mutation; the bullets above are the Keycloak/OIDC concrete instantiation of that accepted rule, not a competing trust model.

ADR-013's freshness/replay rule is protocol-conditional ("enforce timestamp/nonce/event-ID freshness semantics **provided by the protocol**"), and the Back-Channel Logout protocol's freshness/replay semantics are not the generic OIDC authentication `nonce`. Per the Back-Channel Logout specification, a `logout_token` is REQUIRED to carry `iat` and a unique `jti`, is REQUIRED to carry an `events` claim containing the `http://schemas.openid.net/event/backchannel-logout` member, carries `sid` and/or `sub` identifying the logged-out session/principal, and is REQUIRED to **not** contain a `nonce` claim. Applying a blanket "require nonce" rule (a mistake in an earlier draft of this record) would cause the BFF to reject every standards-compliant logout token Keycloak actually sends, silently defeating this entire closure condition.

After cryptographic authenticity is established, the BFF SHALL therefore: verify `iat` is within an accepted bounded clock-skew freshness window; persist `jti` for the replay-safety interval and reject reuse; reject any `logout_token` that carries a `nonce` claim; require the `events` claim to contain the back-channel-logout member; and resolve the affected BFF session(s) from `sid` where present, falling back to `sub` (all active sessions for that subject) otherwise. On accepted receipt, the BFF SHALL invalidate the corresponding session(s) within an explicit numeric propagation SLA (evidence-driven, `OPEN` until measured, tracked alongside `OPEN-REL-002`'s freshness-horizon discipline). The BFF's own session re-validation interval against Keycloak SHALL be capped as a self-healing backstop for a missed/delayed back-channel event. `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md`'s required-implementation-evidence list includes this scenario explicitly.

### Closure condition 2 — outage classification under ADR-017 (binding, medium severity)

ADR-017 already gives "security authority unavailable" a deliberate, general default (fail closed unless a documented durable/local verification path remains valid) — a different, intentionally stricter category than the Control Plane's own cached-continuity carve-out (`adr/ADR-017-availability-and-degradation.md:22,28`). This is a chosen split, not an oversight the candidate decision needs to invent a new mechanism for. What the decision must still do is exercise or decline that existing escape hatch explicitly for Keycloak.

**Requirement:** this record classifies Keycloak under ADR-017's "security authority unavailable" category and selects the escape-hatch branch: during a Keycloak outage, already-issued, still-valid BFF sessions continue to be honored using the BFF's own current membership/permission re-checks (which do not require contacting Keycloak per request); new session creation and step-up/MFA admission fail closed until Keycloak recovers. This bound is added to ADR-017's mandated chaos/fault-injection matrix (`adr/ADR-017-availability-and-degradation.md:43`) as a named scenario rather than left implicit.

### Non-binding reinforcement (documented for implementer clarity, not a new invariant)

`ADR-005:27` ("External identity providers integrate through standards/provider adapters and do not redefine tenant membership semantics") and `AP-03` already prohibit Keycloak's native realm/group/Organizations model from becoming a second, unsynced source of tenant membership — this is not a gap this record closes, it is an already-binding rule automatically inherited the moment Keycloak is selected. For implementer clarity at the point of concrete adoption, this record states explicitly: **Keycloak stores and authenticates only human identity, credential and MFA state; tenant, organization, group or membership data SHALL NOT be created, synced, or read from Keycloak's realm/group/Organizations model for authorization or membership purposes — JLMirror's own membership store remains the sole authority per ADR-005.** A CI/config-review conformance check SHOULD fail the build if Keycloak realm roles, groups, or the Organizations feature appear in any authorization-relevant code path or IaC/config.

Identity/session residency (a minor, non-blocking consistency note): `threat-model.md` classifies identity/session state at the same protected-asset tier as tenant operational data, but neither business data nor identity data has an *enforced* residency guarantee today (`region_intent` is an optional, not-yet-enforced field, and a region hierarchy above cells is explicitly future work per `docs/07-system-design/cross-cell-and-global-operations.md:49`). No ADR text change is required now; if/when a future region hierarchy is defined, identity/session state should be included in that same design rather than assumed out of scope.

## Consequences

### Positive
- reuses a mature, widely-deployed OIDC provider rather than building custom human-identity infrastructure;
- back-channel logout closes the one revocation class this platform's own bar had left unaddressed;
- explicit JWS signature/algorithm/key verification prevents forged claim sets from reaching session revocation authority and makes ADR-013's generic callback-authentication rule concrete at the Keycloak boundary;
- the ADR-017 classification makes Keycloak's outage behavior an explicit, tested, accepted-risk decision rather than an implicit assumption.

### Negative / cost
- back-channel logout is a new wired integration requiring its own conformance tests under ADR-013's framework;
- signing-key rotation/JWKS currentness becomes part of the identity-provider adapter's security-operability surface and requires bounded refresh/failure semantics;
- the fail-closed-for-new-sessions branch means a Keycloak outage genuinely blocks new logins/step-up platform-wide — an accepted cost of the stricter security-authority category, not mitigated by this record.

### Risks
- an operator error that bypasses the CI conformance check and reaches for Keycloak Organizations under delivery pressure remains a residual risk mitigated by, not eliminated by, the restated rule and check.

## Validation

Before this selection is treated as production-eligible, conformance evidence SHALL prove:
- a Keycloak-side admin account disable/forced logout propagates to BFF session revocation within the accepted bound;
- a standards-compliant, **correctly signed** `logout_token` (no `nonce` claim, per spec) is accepted and processed, not rejected;
- a forged/bad-signature token, `alg=none`, an algorithm outside the configured allow-list, an unknown/retired signing key, or a token attempting untrusted remote-key indirection is rejected before any `sid`/`sub` lookup or session mutation;
- valid signing-key rotation is accepted only after the new key is established through trusted Keycloak/JWKS configuration/currentness rules, while a retired key cannot regain authority merely because its `kid` appears again in an untrusted token;
- a `logout_token` carrying a `nonce` claim, a stale/out-of-window `iat`, a reused `jti`, or a missing/incorrect `events` member is rejected;
- a Keycloak outage leaves already-issued sessions honored via BFF-local checks while new session/step-up admission fails closed;
- no authorization-relevant code path or IaC/config references Keycloak realm roles, groups, or Organizations.

## Exit / revisit conditions

Revisit if a future client architecture change (per ADR-005's own exit clause), a change in Keycloak/OIDC signing-key operational requirements, or a measured back-channel-logout propagation cost disproportionate to actual revocation frequency argues for a different mechanism.
