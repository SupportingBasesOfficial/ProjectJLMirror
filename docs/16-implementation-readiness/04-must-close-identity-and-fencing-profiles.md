# Implementation Readiness — C1 Identity and Fencing Profiles

**Status:** proposed closure record  
**C1 closure on acceptance:** `OPEN-API-001`; the protocol/trust-shape subdecision of `OPEN-PRT-008`; `OPEN-PRT-011`; `OPEN-PRT-039`  
**Residual C2 after acceptance:** the replaceable workload-identity issuer/attestation backend portion of `OPEN-PRT-008`

These decisions are concrete protocol/mechanism profiles required to implement protected paths correctly. They do not select an identity SaaS, workload-identity control-plane product, service mesh, cloud or orchestrator vendor.

# IR-D-001 — Human and external machine authentication/token profile

## Human first-party browser

Canonical profile:

```text
OIDC Authorization Code Flow
+ PKCE S256
+ BFF confidential client/token holder
+ server-side code/token exchange
+ opaque browser BFF session handle
```

Requirements:

- the browser never receives platform refresh tokens or long-lived platform access credentials;
- every browser authorization transaction uses an unpredictable `state`, PKCE S256 verifier/challenge and an unpredictable OIDC `nonce` bound to that exact initiating BFF session/transaction;
- authorization-code callback validates issuer, audience/client, exact redirect binding, `state`, PKCE verifier and exact returned ID-token `nonce` before the login result is accepted;
- authorization response/code is accepted only for the initiating BFF session/transaction and cannot be replayed across browser sessions;
- tokens received from the identity authority remain server-side at the BFF/security boundary;
- the browser receives only an opaque, high-entropy session handle in a `Secure`, `HttpOnly`, host-bound cookie profile;
- session identifiers rotate or are replaced at privilege/authentication boundary changes where session-fixation resistance requires it;
- session validity is not current authorization: every protected operation re-establishes current membership/permission/tenant authority as required by accepted contracts;
- logout/revocation/session retirement invalidates server-side session authority even if a browser cookie remains present;
- ambient cookie possession does not replace CSRF/Origin controls from Phase 09;
- token validation rejects wrong issuer, audience, authorized-party/client binding or expired/not-yet-valid token state according to the accepted token profile;
- raw authorization codes/tokens/session handles are excluded from ordinary logs/telemetry.

### MFA / authentication-strength currentness

`SEC-ID-002` remains mandatory. Privileged or policy-sensitive human operations declare a required authentication-assurance policy in addition to ordinary permission/scope.

The BFF/security boundary SHALL retain trusted authentication-context evidence from the identity authority, such as accepted `acr`/`amr` claims or a reviewed equivalent, and SHALL evaluate it against the current Security policy before admitting an operation that requires MFA, step-up or recent re-authentication.

Rules:

- successful OIDC authentication does not imply that the current session satisfies every privileged-operation assurance requirement;
- a required MFA/step-up/re-authentication level that is absent, stale, untrusted or cannot be proven causes the protected operation to fail closed or begin a fresh policy-authorized step-up flow;
- the exact allowed MFA factors and the mapping from privileged operations/risk policy to required assurance are Security policy/configuration, not caller/UI/IdP defaults;
- a client-provided flag, UI state, role name, `amr` string without accepted issuer/profile semantics or elapsed session existence cannot manufacture authentication strength;
- after step-up, current authorization/tenant/permission checks are still required independently.

The exact IdP product, BFF session-store product and Phase 09 CSRF implementation mechanism remain C2 choices under their existing fixed semantics.

## External machine/API principal

Canonical protocol profile:

```text
OAuth 2.0 Client Credentials
+ asymmetric client authentication (`private_key_jwt`)
+ short-lived audience-bound access token
```

Requirements:

- each machine principal has attributable client identity and independently revocable credential generation;
- client private keys remain in accepted secret/key authority, never application payload/config/logs;
- each `private_key_jwt` assertion carries a cryptographically strong unique `jti`, short validity interval, issuer/client binding and exact token-endpoint audience and is signed by the current registered key generation;
- the authorization server/token boundary rejects reuse of the same accepted assertion `jti` during its replay-safety interval and rejects wrong-audience, stale/retired-key, expired or not-yet-valid assertions;
- access tokens are short-lived, issuer/audience/client/permission constrained and rejected when the relevant principal/credential generation is retired;
- tenant/resource authority is derived by the platform authorization model, not from arbitrary client-supplied tenant claims;
- token validity alone never proves current authorization or placement;
- shared, non-attributable long-lived bearer secrets are not the canonical machine-principal profile.

A future accepted sender-constrained extension may strengthen this profile without weakening these rules.

## Internal service credential portion of OPEN-API-001

Phase 09 `OPEN-API-001` also asked for internal service credential transport where not already fixed. That portion is closed jointly by IR-D-002 below: internal service peers use the accepted short-lived workload certificate identity plus mTLS service-authentication profile. Therefore `OPEN-API-001` is closed only by the combination of IR-D-001 and IR-D-002.

# IR-D-002 — Internal workload identity and service authentication

Canonical workload identity/protocol profile:

```text
SPIFFE-compatible workload URI identity
+ X.509-SVID-compatible short-lived certificate profile
+ mutual TLS for service-to-service peer authentication
```

This closes the C1 protocol/trust-shape decision needed by protected implementation. It does **not** choose the concrete workload-identity issuer/attestation/control-plane product. That backend remains a C2 subdecision of `OPEN-PRT-008` and must later be selected through bounded conformance evidence.

## Identity

A workload identity has canonical form equivalent to:

```text
spiffe://<accepted-trust-domain>/<environment-class>/<runtime-profile>/<workload-id>
```

Rules:

- `environment-class` and `runtime-profile` are logical security/runtime classes, not physical topology identifiers;
- physical pod/node/IP/instance/cell/cluster/region identifiers are not canonical workload authorization identity unless an accepted profile explicitly binds one as subordinate non-canonical evidence;
- a workload identity authenticates a service/runtime principal, never a tenant/business principal;
- identity syntax cannot be used to bypass accepted placement/current-authorization lookup.

## Issuance and currentness

- workload certificates are short-lived and automatically rotated;
- workload attestation/issuance backend must prove the requested logical workload identity from accepted runtime evidence rather than caller-selected strings;
- issuer/trust-bundle currentness and revocation/retirement are Security authority;
- a restored or stale issuer/bundle cannot become current merely because TLS succeeds;
- private keys are non-exported where the selected runtime permits and never ordinary configuration;
- trust domains/environment bindings cannot let development/validation/recovery identities authenticate as production identities;
- certificate SAN/identity parsing is canonical and exact; alternate textual encodings cannot map one certificate to multiple workload principals;
- expired, not-yet-valid, untrusted-chain or retired-trust-bundle credentials fail service authentication.

## Service authentication vs application authorization

Successful mTLS proves only the authenticated workload principal and transport peer binding.

It does not grant:

- tenant authorization;
- placement authority;
- domain/business permission;
- replay/retry eligibility;
- Product applicability;
- database/broker superuser authority.

Application authorization maps the authenticated workload identity to exact service permissions/contracts and re-establishes tenant/current authority separately.

## Broker/state-port adaptation

Where a broker/database/vendor cannot consume the certificate profile directly, a narrow adapter MAY exchange current workload identity for a short-lived vendor credential. The adapter:

- authenticates the current workload identity first;
- maps only to the least-privilege state-port/contract scope;
- cannot broaden tenant/domain permissions;
- emits an independently revocable short-lived credential;
- records credential generation/currentness without making the vendor identity canonical platform identity.

# IR-D-003 — Concrete runtime generation/fence mechanism

Canonical initial mechanism:

```text
scope-local monotonically increasing positive PostgreSQL BIGINT fence epoch
stored in the owning authoritative PostgreSQL state
allocated/advanced transactionally
checked at every protected effect boundary
```

This mechanism implements Phase 11/13 fencing without using wall-clock time, process identity or lease expiry as authority.

## Fence record

For each fenced authority scope:

```text
fence_scope_id
current_fence_epoch       # positive signed BIGINT, no wraparound semantics
current_generation_id
state/currentness
updated_at                # evidence only, never ordering authority
```

`current_fence_epoch` increases monotonically and SHALL NOT wrap, reset or be reused. Approaching implementation/storage exhaustion is a governed migration blocker long before the signed `BIGINT` maximum; overflow fails closed rather than wrapping.

`current_generation_id` remains a stable opaque generation identity and does not replace other generations such as `placement_version`, `configuration_generation`, `workload_credential_generation` or `network_policy_generation`.

## Acquisition / replacement

A new effectful holder becomes eligible only after an owning transaction atomically:

1. verifies the expected predecessor/current state;
2. increments `current_fence_epoch` using a compare/lock/update primitive that admits one winning successor for that predecessor;
3. records the successor generation/current state;
4. persists required audit/outbox evidence where that authority requires it.

Lease timeout/process death alone never increments authority or proves the old holder produced no effect.

## Effect admission

Every protected effect carries or resolves `{fence_scope_id, fence_epoch}` through an authenticated/trusted internal context. Caller-controlled public input cannot choose a higher epoch as authority.

The effect owner rejects an epoch lower than the current epoch and rejects an epoch whose scope/generation binding is invalid for the requested operation.

Where authoritative fence state and protected effect are co-resident in PostgreSQL, the current-epoch predicate is checked in the same transaction as the protected mutation.

Where the effect authority is separate, one of the following is required:

- the target maintains/consults an authoritative monotonic accepted epoch for the same fence scope before the effect; or
- the operation uses the accepted stable operation/create-or-observe/reconciliation protocol so that a stale source cannot gain a new effect attempt merely from an epoch claim.

A fence token never converts an ambiguous cross-authority outcome into absence.

## Recovery

Restore/PITR SHALL NOT move an effective fence epoch backwards. Recovery inventory compares restored epoch/generation with surviving current authority, audit/effect/release/placement evidence. If a higher surviving epoch may exist or equality cannot be proven, the scope remains quarantined and reconciliation advances/fences forward before effectful admission.

A recovered lower epoch is never made current by resetting external actors to match the backup.

## Portability

PostgreSQL is the initial concrete implementation because accepted architecture already uses PostgreSQL for transactional business/authority truth. A future authority store may replace it only if it proves equivalent:

- atomic predecessor check + monotonic advance;
- one-current-successor behavior;
- authenticated scope binding;
- stale-actor rejection at effect boundaries;
- restore/PITR forward continuity;
- interoperability with stable-operation reconciliation.

# Compatibility

The following are semantic/security breaking and require reviewed migration:

- changing browser auth flow so long-lived platform credentials become JS-readable;
- weakening MFA/step-up/re-authentication assurance checks or treating ordinary login as sufficient for every privileged operation;
- changing machine authentication to shared non-attributable bearer secrets;
- dropping `private_key_jwt` assertion replay rejection/current-key checks;
- allowing workload network presence to substitute for mTLS identity;
- changing workload identity so environment/trust domain can broaden production authority;
- allowing caller-selected workload URI strings to become issuance authority;
- replacing monotonic fencing with wall-clock/process/lease-expiry authority;
- allowing fence reuse/wrap/reset;
- allowing a restored lower epoch to become current;
- collapsing runtime fence epoch into unrelated placement/config/security generations.

# Required implementation evidence

Before an implementation slice claims conformance, tests SHALL cover:

- OIDC state/nonce/PKCE mix-up and token audience/issuer/client rejection;
- authorization-code/session replay across browser sessions;
- privileged operation with missing/stale/insufficient MFA/step-up assurance;
- post-step-up operation with revoked permission or tenant access;
- browser inability to read long-lived platform credentials;
- `private_key_jwt` duplicate-`jti` replay, wrong-audience, expired/not-yet-valid and retired-key rejection;
- machine credential revocation/rotation;
- cross-environment workload identity rejection;
- caller-requested workload identity different from attested runtime identity;
- expired/stale workload certificate and trust-bundle rejection;
- tenant authorization not derivable from mTLS identity alone;
- stale writer/worker with old fence epoch after failover/replacement;
- concurrent acquisition race with one winning epoch;
- wrong-scope/forged higher epoch rejection;
- restore/PITR with a surviving higher epoch;
- no epoch wrap/reset/reuse behavior;
- cross-authority ambiguity remaining reconciliation-blocked despite fencing.
