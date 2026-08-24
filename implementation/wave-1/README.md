# Wave 1 — Identity and Authority Skeleton

**Implementation scope:** explicitly authorized Wave 1 only  
**Authority base:** `main@5b56ad94566b48b72a993ee8f5cf7e983127ab21`

This package implements the portable authority core required by:

- `impl.identity-bff@1`;
- `impl.control-plane@1`;
- minimal `impl.platform-runtime@1`.

It does not create Product/domain endpoints.

## Implemented boundaries

- one-shot browser OIDC transaction binding with state, nonce and PKCE S256;
- trusted OIDC adapter boundary and current auth-strength evidence hook;
- machine assertion current-key/current-replay-generation checks plus atomic replay-authority port;
- canonical SPIFFE-compatible workload identity parsing and current mTLS evidence admission;
- service identity remains separate from tenant/business authorization;
- Control-Plane placement evidence -> cell-local trusted `TenantContext` construction;
- owning current authorization re-check after TenantContext construction;
- exact runtime environment/profile bindings for Web BFF, API auth boundary and Control Plane;
- config generation separated from secret-reference classes/values;
- IR-D-003 positive PostgreSQL `BIGINT` fence record and atomic predecessor compare/advance;
- exact scope+epoch+generation effect admission; forged-higher epochs do not authorize effects.

## Explicitly NOT selected in this wave

The following remain C2 unless separately accepted through evidence:

- IdP product;
- BFF web framework / HTTP server;
- BFF session-store product;
- concrete CSRF mechanism;
- workload-identity issuer/attestation backend (`OPEN-PRT-008.B`);
- service mesh or no-mesh deployment decision;
- secret-manager/KMS product;
- configuration-distribution product;
- orchestrator/container/serverless mechanism;
- physical environment/cell topology.

Python standard-library code in `src/jlmirror_authority/` is an implementation of the portable authority core and does not make Python, a hosting model or any vendor a normative architecture authority. Future implementations may replace it only while passing the same accepted semantic/adversarial contracts.

## Authority laws

```text
VALID CREDENTIAL != CURRENT AUTHORIZATION
LOGIN SUCCESS != PRIVILEGED ASSURANCE
SERVICE IDENTITY != TENANT AUTHORIZATION
ROUTED REQUEST != TRUSTED TENANT CONTEXT
ENVIRONMENT LABEL != AUTHORITY
NETWORK PRESENCE != TRUST
FENCE CLAIM > CURRENT != AUTHORITY
FENCE TOKEN != AMBIGUOUS EFFECT ABSENCE
SECRET REFERENCE != SECRET VALUE
WAVE 1 AUTHORIZED != WAVE 2 AUTHORIZED
```
