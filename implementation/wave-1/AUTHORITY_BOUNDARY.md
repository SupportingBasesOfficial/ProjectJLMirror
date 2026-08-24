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
- runtime profile bindings required by the three Wave 1 slices.

Trusted C2 adapters provide evidence only. Malformed, unbound or non-canonical adapter output fails closed before it can create session, replay, tenant, workload or protected-effect authority.

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
WORKLOAD IDENTITY != TENANT AUTHORITY
NETWORK PRESENCE != TRUST
TENANT ID INPUT != TENANT CONTEXT
PLACEMENT CACHE HIT != GLOBAL AUTHORITY
ENVIRONMENT LABEL != AUTHORIZATION
UNCLASSIFIED/UNTYPED CONFIG != RUNTIME-ADMISSIBLE CONFIG
FENCE TOKEN != AMBIGUOUS EFFECT ABSENCE
SECRET REFERENCE != SECRET VALUE
WAVE 1 AUTHORIZED != WAVE 2 AUTHORIZED
```