# IR-D-002 Decision Record — Workload Identity Profile (Monolith Phase)

**Status:** proposed — initial bounded scope selected; closure condition below is binding before this record satisfies the C2 residual for workload identity
**Decision class:** C2 (`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md` — "the replaceable workload-identity issuer/attestation backend portion of `OPEN-PRT-008`")
**Drivers:** `OPEN-PRT-008`, `ADR-020`, `ADR-005`, `ADR-013`, `SEC-ID-001`

This document is **not** a new ADR. It selects a concrete instantiation of the already-accepted workload-identity protocol shape within the monolith boundary defined by ADR-020.

## Context and problem

`docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md` fixes the external machine/API principal protocol shape (OAuth 2.0 Client Credentials + `private_key_jwt` + short-lived audience-bound access token) but explicitly leaves the workload-identity issuer/attestation backend as a replaceable C2 choice. The monolith phase (ADR-020) calls for an internal trust-boundary model that must not create premature coupling to a service-mesh or cloud workload-identity product.

## Requirements and invariants this selection must satisfy

- ADR-020: while the codebase lives as a modular monolith, services share an OS process boundary; workload identity inside that boundary cannot require a full SPIFFE/SPIRE or cloud metadata service.
- OPEN-PRT-008: the identity mechanism must be replaceable by a bounded SPIFFE/SPIRE integration without changing business semantics when services are extracted.
- ADR-005: workload identity applies to platform-internal background workers and adapters only; it does not extend tenant membership/authorization authority.
- ADR-013: credential material remains inside accepted secret/key authority; never in application config text, logs or event payloads.
- SEC-ID-001: credentials must be independently revocable per worker role; shared long-lived bearer secrets are not the accepted profile.

## Decision

### Phase A — PostgreSQL role-per-worker (current monolith phase)

Within the monolith boundary:

- each background worker (metric workers, problem-state workers, alerting transport, notification, ITSM) is assigned a dedicated PostgreSQL application role with minimum required table/function privileges.
- Connection credentials are loaded at startup from the accepted secrets authority (environment variable injected at deploy time or a secrets manager integration) and never hard-coded or logged.
- No worker role carries superuser or cross-tenant privileges.
- The DB connection pool is per-worker; credential rotation retires old connections and re-establishes from the updated secret without hot patch.

This satisfies OPEN-PRT-008 at the monolith phase without coupling to an external workload-identity product.

### Phase B — SPIFFE/SPIRE when services are extracted (future, per ADR-020)

When ADR-020's modular monolith is decomposed into independent services:

- each extracted service is issued a SPIFFE SVID by a SPIRE agent co-located with the service instance.
- The private_key_jwt client-assertion profile from `04-must-close-identity-and-fencing-profiles.md` is satisfied by the X.509 SVID or the JWT-SVID SPIFFE credential format.
- The SPIRE server is the issuer/attestation backend that this record defers as a replaceable C2 choice for the future extraction phase.
- A separate Phase B IR-D record will authorize the SPIRE deployment topology, trust domain, attestation methods and rotation policy before any service is extracted.

Phase B does not begin until the Phase B record is accepted.

### Closure condition — per-worker role evidence (binding)

Before Phase A is treated as canonical, the implementation SHALL demonstrate:

- each worker establishes its DB connection under its own dedicated role, not the superuser / migration role;
- role-level privilege audit (e.g., `\dp` or information_schema) confirms no worker role holds privileges beyond its documented minimum;
- credential rotation completes without worker downtime and the old credential is not re-accepted after rotation.

## Consequences

### Positive
- zero external service-mesh dependency during the monolith phase;
- per-role PostgreSQL privileges enforce least-privilege at the DB level;
- the SPIFFE/SPIRE replacement path is explicit and bounded, not invented at extraction time.

### Negative / cost
- per-worker role provisioning adds DBA/migration overhead versus a single app role;
- secret rotation must be orchestrated per role; a shared rotation mechanism reduces operational complexity but requires explicit design.

## Validation

Before Phase A is treated as canonical:
- CI migration run creates role(s) distinct from the superuser/migration role;
- each worker integration test connects under the correct role and is rejected when connecting under another worker's role;
- no worker role can SELECT, INSERT, UPDATE or DELETE on tables it has no documented business need to access.

## Exit / revisit conditions

Revisit if ADR-020 is revised to extract services sooner than expected, if a cloud provider workload-identity metadata service is adopted as infrastructure, or if PostgreSQL's role model becomes incompatible with a chosen multi-region/multi-DB topology.
