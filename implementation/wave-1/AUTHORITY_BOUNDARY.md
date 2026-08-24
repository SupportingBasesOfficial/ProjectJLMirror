# Wave 1 — Authority Boundary

Wave 1 implements only the identity and authority skeleton authorized by the accepted Implementation Readiness sequencing.

## Included slices

- `impl.identity-bff@1`
- `impl.control-plane@1`
- minimal `impl.platform-runtime@1`

## Included authority primitives

- browser session/authentication transaction primitives;
- principal-bound authentication-strength evidence and privileged step-up predicates;
- machine principal assertion/replay authority ports;
- typed workload identity parsing and service-authentication boundary;
- trusted `TenantContext` construction inputs;
- current authorization and placement admission predicates;
- runtime/configuration/workload credential/network-policy generation separation;
- classified finite-scalar configuration plus typed secret-reference boundaries;
- monotonic PostgreSQL fence contract and stale-actor rejection;
- persisted fence-state revalidation before historical state can remain authority-eligible;
- exact-base Git delta scope guard that rejects Product/domain/Wave 2/normative-doc changes;
- runtime profile bindings required by the three Wave 1 slices.

Trusted C2 adapters provide evidence only. Malformed, unbound or non-canonical adapter output fails closed before it can create session, replay, tenant, workload or protected-effect authority. Caller/request-adjacent tenant, destination and authority-generation identifiers are canonicalized before C2 placement/configuration/machine verification ports are invoked.

Browser authorization transaction authority is time-bounded on both sides: a consumed transaction is usable only while `created_at <= now < expires_at`. Clock rollback/not-yet-current state cannot reach the IdP adapter as an authentication attempt.

Fence scope/epoch/generation equality is necessary but not sufficient for a protected effect. The ordinary Wave 1 effect path requires the current fence authority state to be exactly `active`. `quarantined`, `retired` or any other syntactically valid state cannot admit a protected effect and cannot use the ordinary successor compare-and-advance path to resurrect effect eligibility. Recovery/state-transition authority remains separately governed by the accepted Phase 13/15 lifecycle and recovery predicates.

An already-present `platform.authority_fences` object is not automatically conforming. The follow-on revalidation migration applies the canonical identifier/positive-epoch contract to persisted rows and validates historical state without rewriting or deleting authority data merely to make validation pass.

## Explicitly not selected here

The following remain C2 implementation choices and are not made canonical by code presence:

- identity provider product;
- BFF/session-store product;
- CSRF mechanism/product beyond fixed Phase 09 semantics;
- workload-identity issuer/attestation backend;
- service mesh;
- secret manager/KMS product;
- configuration-distribution product;
- orchestrator/scheduler;
- ingress/load-balancer product;
- physical environment/topology mapping.

## Explicitly absent

- Product/domain endpoints not already accepted;
- customer telemetry implementation;
- provider adapters;
- realtime implementation;
- artifact delivery activation;
- Wave 2 transactional business/domain implementation;
- production topology/numerics.

## Authority laws

```text
AUTHENTICATED != AUTHORIZED
SESSION VALID != CURRENT AUTHORITY
MFA PRESENT != REQUIRED ASSURANCE CURRENT
AUTHENTICATION STRENGTH EVIDENCE != TRANSFERABLE PRINCIPAL AUTHORITY
MALFORMED ADAPTER OUTPUT != TRUSTED AUTHORITY
NONCANONICAL LOOKUP/GENERATION INPUT != C2 ADAPTER AUTHORITY
NOT-YET-CURRENT AUTH TRANSACTION != AUTHENTICATION AUTHORITY
WORKLOAD IDENTITY != TENANT AUTHORITY
NETWORK PRESENCE != TRUST
TENANT ID INPUT != TENANT CONTEXT
PLACEMENT CACHE HIT != GLOBAL AUTHORITY
ENVIRONMENT LABEL != AUTHORIZATION
UNCLASSIFIED/UNTYPED CONFIG != RUNTIME-ADMISSIBLE CONFIG
FENCE SCOPE/EPOCH/GENERATION MATCH != EFFECT AUTHORITY WITHOUT ACTIVE STATE
NON-ACTIVE FENCE STATE != ORDINARY SUCCESSOR AUTHORITY
PREEXISTING FENCE TABLE != PERSISTED AUTHORITY CONFORMANCE
FENCE TOKEN != AMBIGUOUS EFFECT ABSENCE
SECRET REFERENCE != SECRET VALUE
IMPLEMENTATION MANIFEST != AUTHORIZED GIT DELTA BY ITSELF
WAVE 1 AUTHORIZED != WAVE 2 AUTHORIZED
```