# Implementation Readiness — C1 Identity and Fencing Profiles

**Status:** proposed closure record  
**Closes on acceptance:** `OPEN-API-001`, `OPEN-PRT-008`, `OPEN-PRT-011`, `OPEN-PRT-039`

These decisions are concrete protocol/mechanism profiles required to implement protected paths correctly. They do not select an identity SaaS, service mesh, cloud or orchestrator vendor.

# IR-D-001 — Human and machine authentication/token profile

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

- the browser never receives platform refresh tokens or long-lived access credentials;
- authorization-code callback validates issuer, audience/client, exact redirect binding, `state`, PKCE verifier and OIDC `nonce` where applicable;
- tokens received from the identity authority remain server-side at the BFF/security boundary;
- the browser receives only an opaque, high-entropy session handle in a `Secure`, `HttpOnly`, host-bound cookie profile;
- session validity is not current authorization: every protected operation re-establishes current membership/permission/tenant authority as required by accepted contracts;
- logout/revocation/session retirement invalidates server-side session authority even if a browser cookie remains present;
- ambient cookie possession does not replace CSRF/Origin controls from Phase 09.

The exact IdP product and session store product remain C2 choices.

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
- access tokens are short-lived, audience-bound and permission/scope constrained;
- tenant/resource authority is derived by the platform authorization model, not from arbitrary client-supplied tenant claims;
- token validity alone never proves current authorization or placement.

A future accepted sender-constrained extension may strengthen this profile without weakening these rules.

# IR-D-002 — Internal workload identity and service authentication

Canonical workload identity profile:

```text
SPIFFE-compatible workload URI identity
+ X.509-SVID-compatible short-lived certificate profile
+ mutual TLS for service-to-service peer authentication
```

This profile selects an interoperable identity/protocol shape, not a SPIRE/service-mesh vendor.

## Identity

A workload identity has canonical form equivalent to:

```text
spiffe://<accepted-trust-domain>/<environment>/<runtime-profile>/<workload-id>
```

Physical pod/node/IP/instance/cell identifiers are not authorization identity unless an accepted profile explicitly binds them as non-canonical evidence.

## Issuance and currentness

- workload certificates are short-lived and automatically rotated;
- issuer/trust-bundle currentness and revocation/retirement are Security authority;
- a restored or stale issuer/bundle cannot become current merely because TLS succeeds;
- private keys are non-exported where the selected runtime permits and never ordinary configuration;
- trust domains/environment bindings cannot let development/validation/recovery identities authenticate as production identities.

## Service authentication vs application authorization

Successful mTLS proves only the authenticated workload principal and transport peer binding.

It does not grant:

- tenant authorization;
- placement authority;
- domain/business permission;
- replay/retry eligibility;
- Product applicability.

Application authorization maps the authenticated workload identity to exact service permissions/contracts and re-establishes tenant/current authority separately.

## Broker/state-port adaptation

Where a broker/database/vendor cannot consume the certificate profile directly, a narrow adapter MAY exchange current workload identity for a short-lived vendor credential. The adapter cannot broaden scope and the vendor credential remains derived/non-canonical authority.

# IR-D-003 — Concrete runtime generation/fence mechanism

Canonical initial mechanism:

```text
scope-local monotonically increasing 64-bit fence epoch
stored in the owning authoritative PostgreSQL state
allocated/advanced transactionally
checked at every protected effect boundary
```

This mechanism implements Phase 11/13 fencing without using wall-clock time, process identity or lease expiry as authority.

## Fence record

For each fenced authority scope:

```text
fence_scope_id
current_fence_epoch
current_generation_id
state/currentness
updated_at   # evidence only, never ordering authority
```

`current_fence_epoch` increases monotonically. `current_generation_id` remains a stable opaque generation identity and does not replace other generations such as `placement_version`, `configuration_generation`, `workload_credential_generation` or `network_policy_generation`.

## Acquisition / replacement

A new effectful holder becomes eligible only after an owning transaction atomically:

1. verifies the expected predecessor/current state;
2. increments `current_fence_epoch`;
3. records the successor generation/current state;
4. persists required audit/outbox evidence where that authority requires it.

Lease timeout/process death alone never increments authority or proves the old holder produced no effect.

## Effect admission

Every protected effect carries or resolves `{fence_scope_id, fence_epoch}`. The effect owner rejects an epoch lower than current.

Where authoritative state and effect are co-resident in PostgreSQL, the current-epoch predicate is checked in the same transaction as the protected mutation.

For cross-authority/external effects, the stable operation/reconciliation contract remains authoritative; a fence does not convert ambiguous outcome into absence.

## Recovery

Restore/PITR SHALL NOT move an effective fence epoch backwards. If restored state may be behind surviving evidence/current authority, the scope remains quarantined and reconciliation advances/fences forward before effectful admission.

## Portability

PostgreSQL is the initial concrete implementation because accepted architecture already uses PostgreSQL for transactional business/authority truth. A future authority store may replace it only if it proves equivalent atomic compare/advance, monotonic fencing, recovery continuity and stale-actor rejection.

# Compatibility

The following are semantic/security breaking and require reviewed migration:

- changing browser auth flow so long-lived platform credentials become JS-readable;
- changing machine authentication to shared non-attributable bearer secrets;
- allowing workload network presence to substitute for mTLS identity;
- changing workload identity so environment/trust domain can broaden production authority;
- replacing monotonic fencing with wall-clock/process/lease-expiry authority;
- allowing a restored lower epoch to become current;
- collapsing runtime fence epoch into unrelated placement/config/security generations.

# Required implementation evidence

Before an implementation slice claims conformance, tests SHALL cover:

- OIDC state/nonce/PKCE mix-up and token audience/issuer rejection;
- browser inability to read long-lived platform credentials;
- machine credential revocation/rotation;
- cross-environment workload identity rejection;
- expired/stale workload certificate and trust-bundle rejection;
- tenant authorization not derivable from mTLS identity alone;
- stale writer/worker with old fence epoch after failover/replacement;
- concurrent acquisition race with one winning epoch;
- restore/PITR with a surviving higher epoch;
- cross-authority ambiguity remaining reconciliation-blocked despite fencing.
