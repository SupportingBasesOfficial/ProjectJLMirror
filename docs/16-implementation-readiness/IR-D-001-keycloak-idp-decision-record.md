# IR-D-001 Decision Record — Keycloak as the Human Identity Provider

**Status:** proposed — mechanism selected; two closure conditions below are binding before this record satisfies the IdP-product C2 residual
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` — "the exact IdP product... remain[s] a C2 choice under [its] existing fixed semantics")
**Drivers:** `SEC-ID-001`, `SEC-ID-002`, `TM-013`, `ADR-005`, `ADR-013`, `ADR-017`, `AP-03`, `IR-D-001` (OIDC Authorization Code Flow + PKCE + BFF confidential session)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: Keycloak is a concrete instantiation of the already-accepted protocol shape and does not redefine Identity, Membership or Authorization ownership. Provider-native `sid`/`sub` values remain external provider references; they never become JLMirror principal/session IDs merely because a cryptographically valid Logout Token carries them.

## Context and problem

`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:52` fixes the protocol shape (OIDC Authorization Code Flow + PKCE S256 + BFF confidential session) but explicitly leaves the exact IdP product as a C2 choice. This record selects Keycloak as that candidate and records the conditions required before the selection is canonical.

## Requirements and invariants this selection must satisfy

- ADR-005: Keycloak authenticates human principals only; it does not redefine tenant membership/authorization semantics.
- AP-03 / ADR-013: external provider identities and payloads stay behind a stable adapter/trust boundary; provider-native IDs remain external references.
- `SEC-ID-001`/`SEC-ID-002`: credentials are independently revocable; privileged access supports MFA/step-up.
- ADR-017: security-authority unavailability fails closed unless a separately documented durable/local verification path remains valid.
- IR-D-001: logout/revocation/session retirement invalidates server-side BFF session authority even if a browser cookie remains present.
- Back-channel identity resolution SHALL NOT trust raw `sid` or `sub` as a platform-owned identity or tenant selector.
- Uncertainty about provider-session/external-identity mapping SHALL NOT be treated as confirmed absence.

## Decision

Keycloak is selected as the candidate human identity provider, integrated exclusively behind the BFF per IR-D-001. Browser JavaScript never receives a Keycloak refresh/access credential; the BFF exchanges the authorization code server-side and issues only its own opaque session handle.

Selection is conditioned on the two closure requirements below.

### Closure condition 1 — IdP-side revocation back-channel (binding, high severity)

Administrator disable/forced logout at Keycloak needs a bounded path into the BFF's authoritative session fencing. The BFF SHALL therefore implement OIDC Back-Channel Logout 1.0 (`logout_token` receipt at a dedicated BFF endpoint) as a required wired integration under ADR-013's inbound-callback framework.

#### Cryptographic authenticity before identity resolution

Before trusting **any** `logout_token` claim or attempting `sid`/`sub` mapping, the BFF SHALL:

1. enforce the accepted bounded callback/JWT byte/parser limits;
2. if Logout Token encryption is ever negotiated, decrypt only under trusted registered algorithms/keys; encryption never substitutes for signing;
3. cryptographically verify the Logout Token JWS signature using the trusted Keycloak/ID-token signing-key profile for the configured issuer/client;
4. enforce an allowed-signature-algorithm policy selected from trusted discovery/registration/configuration, never from the attacker-controlled JOSE header alone; reject `alg=none`, unexpected algorithms, unknown/retired keys and signature failures;
5. resolve `kid` only against trusted Keycloak/JWKS configuration and bounded rotation/currentness logic; token-supplied `jku`, `x5u` or equivalent remote-key indirection SHALL NOT choose an arbitrary verification endpoint;
6. only after cryptographic authenticity succeeds, validate protocol claims and provider-to-platform identity mappings.

ADR-013 already mandates provider signature/authentication before effects; this section is the exact Keycloak/OIDC instantiation so claim validation cannot be mistaken for authentication.

OIDC Back-Channel Logout requires `iss`, `aud`, `iat`, `exp`, `jti` and `events`; the Logout Token carries `sid`, `sub`, or both; `nonce` is prohibited. JLMirror intentionally strengthens the specification's optional recent-`jti` duplicate check into mandatory durable replay recognition because replay reaches security-sensitive mutation authority.

After cryptographic authenticity, the BFF SHALL:

- bind `iss` and `aud` to the exact registered Keycloak issuer/client;
- validate `iat` freshness and `exp` under the accepted bounded clock-skew policy;
- durably recognize replay identity under at least `(issuer, client, jti)` for the supported replay-safety horizon and reject reuse; the same `jti` under a different trusted issuer/client does not collide merely because its string is equal;
- require the back-channel-logout `events` member;
- reject any `nonce` claim;
- require `sid`, `sub`, or both.

#### Provider identity is not platform identity

`sid` and `sub` are Keycloak-native external references. They SHALL be resolved only through trusted mappings created/maintained by the Identity adapter under the authenticated issuer/client context:

- `(issuer, client, sid)` may resolve to the corresponding provider-session binding/session-lineage authority; raw `sid` is never interpreted as a JLMirror `session_id`;
- `(issuer, sub)` resolves through the platform-owned external-identity link to the JLMirror principal; raw `sub` is never a JLMirror principal ID and never selects tenant membership/authorization by itself;
- provider-session/external-identity mapping lifecycle must preserve enough historical/current linkage to revoke any still-active BFF session created under that provider identity; account unlink/relink cannot silently make an active provider-originated session unresolvable to a valid logout;
- if a trusted lookup **confirms** that the provider session/identity has no active mapped JLMirror session authority (including an already-retired session), the valid logout is an idempotent no-op/success rather than an invitation to guess another principal;
- if mapping/currentness lookup is unavailable, contradictory or otherwise uncertain, that uncertainty is not absence and is handled through the callback's fail/retry/reconciliation path; it SHALL NOT acknowledge success on the assumption that nothing exists;
- the token cannot carry or infer tenant authority. Revoking Identity/session authority may subsequently cause protected requests to fail current Membership/Authorization checks, but Keycloak does not mutate those business authorities.

#### Bounded revocation effect — no O(N) session rewrite

Where `sid` identifies a provider-session lineage, the BFF retires/fences the mapped JLMirror session/session-lineage authority. Where only `sub` is present, the logical effect is "all BFF sessions for the mapped principal", but implementation SHALL use a principal/session-authority generation/fence or equivalent bounded mechanism; it SHALL NOT synchronously enumerate and rewrite every active session as the correctness mechanism. Existing session records bound to the retired principal/session generation become non-authorizing through the security-cache/session-authority generation contract.

The actual security-cache propagation/fencing must conform to `OPEN-REL-031-session-store-decision-record.md` and the canonical `OPEN-REL-015` cache invalidation/epoch ownership; provider callback handling does not invent a separate cache-consistency model.

On accepted receipt, the BFF invalidates the mapped session/principal-session authority within an explicit measured propagation bound. Numeric propagation/revalidation horizons remain production objectives under `OPEN-REL-023` and applicable C3 gates, not `OPEN-REL-002` (which belongs to Control Plane freshness). The BFF's own bounded session revalidation against Keycloak remains a self-healing backstop for a missed/delayed callback, not a substitute for Back-Channel Logout.

### Closure condition 2 — outage classification under ADR-017 (binding, medium severity)

This record classifies Keycloak under ADR-017's "security authority unavailable" category and selects its documented durable/local-verification branch: during a Keycloak outage, already-issued BFF sessions MAY continue only while the BFF can establish current JLMirror session, Membership, permission and tenant-access authority through their own accepted local/durable mechanisms; new session creation and step-up/MFA admission fail closed until Keycloak recovers. Keycloak outage never freezes previously cached authorization as current.

### Non-binding reinforcement (implementer clarity)

ADR-005/AP-03 already prohibit Keycloak realm/group/Organizations state from becoming a second tenant-membership authority. Keycloak stores/authenticates human identity, credential and MFA state only. Tenant organization/group/membership data SHALL NOT be created, synchronized or read from Keycloak's realm/group/Organizations model for JLMirror authorization. A CI/config-review conformance check SHOULD reject authorization-relevant use of Keycloak realm roles/groups/Organizations.

Identity/session residency remains subject to the platform's future region/residency decisions; this C2 product selection does not silently fix a global forever-topology.

## Consequences

### Positive
- uses a mature OIDC provider behind the already-accepted identity adapter boundary;
- explicit signature/algorithm/key validation prevents forged claim sets from reaching revocation authority;
- exact `exp`/`iat`/`jti`/`events`/`nonce` handling makes the Logout Token profile unambiguous;
- issuer-bound `sid`/`sub` mappings preserve provider-identity != platform-identity;
- confirmed mapping absence is idempotent while lookup uncertainty remains fail/reconcile rather than false absence;
- principal-wide logout can fence a generation in bounded work instead of enumerating active sessions;
- outage behavior remains tied to current JLMirror authority, not Keycloak reachability alone.

### Negative / cost
- Back-Channel Logout is a wired security integration requiring conformance tests and durable replay state;
- signing/JWKS rotation currentness becomes a security-operability surface;
- provider-session/external-principal mapping lifecycle must remain current across logout, recovery, unlink and relink;
- durable replay recognition consumes bounded security-state capacity;
- Keycloak outage blocks new login/step-up even when existing locally-verifiable sessions remain usable.

## Validation

Before this selection is treated as canonical/production-eligible as applicable, evidence SHALL prove:
- a Keycloak-side admin disable/forced logout propagates to the mapped BFF session/principal-session generation within the accepted bound;
- a correctly signed, unexpired standards-compliant Logout Token is accepted with required `iss`, `aud`, `iat`, `exp`, `jti`, `events`, `sid`/`sub` and no `nonce`;
- forged/bad signature, `alg=none`, unapproved algorithm, unknown/retired key or untrusted remote-key indirection rejects before any platform identity lookup/mutation;
- expired `exp`, future/stale `iat` outside policy, replayed `(issuer, client, jti)`, malformed/missing `events`, missing both `sid` and `sub`, or present `nonce` rejects;
- equal raw `jti` strings from distinct trusted issuer/client scopes do not collide incorrectly, while reuse inside one replay scope is rejected;
- a valid `sid` is resolved only through `(issuer, client, sid)` provider-session mapping and cannot collide into an unrelated BFF session;
- a valid `sub` is resolved only through the current/trusted issuer-bound external-identity linkage and cannot be treated as a tenant/principal/platform ID directly;
- unlink/relink while a provider-originated BFF session remains active does not make a valid subsequent logout unresolvable to that session authority;
- confirmed already-retired/no-active-session mapping is idempotent success, but injected mapping-store outage/contradiction is not acknowledged as absence;
- `sub`-wide logout remains O(1) or bounded-constant relative to active-session count by generation/fence rather than synchronous session enumeration;
- cache propagation follows the accepted security-cache fencing/recovery protocol and a crash after source revocation cannot leave stale positive session authority admitted;
- valid signing-key rotation is accepted only after trusted currentness is established, while retired key authority cannot be revived by an untrusted `kid`;
- if encrypted Logout Tokens are later negotiated, wrong encryption algorithm/key or decrypt failure rejects before effects and successful decryption is still followed by required signature validation;
- Keycloak outage honors only existing sessions whose JLMirror session/membership/permission/tenant-access authority can still be established current; new login/step-up fails closed;
- no authorization-relevant code/config uses Keycloak realm roles, groups or Organizations as JLMirror membership/permission truth.

## Exit / revisit conditions

Revisit if client architecture changes, Keycloak/OIDC signing/encryption requirements change materially, provider-session mapping cannot meet the accepted recovery/revocation semantics, or measured logout propagation cost argues for another IdP mechanism while preserving IR-D-001/ADR-005 semantics.
