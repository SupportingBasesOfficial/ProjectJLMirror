# G1 Identity + Tenant + Protected Shell — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@7c20c9301711e9a4bf355517d7aa23faad7a05b7`  
**Authorization ID:** `g1.identity-tenant-protected-shell@1`

## Purpose

This is the separate implementation-authorization gate required before canonical Product code may begin for the first full-stack JLMirror slice.

It does not implement G1. It authorizes only the bounded product path needed to expose already accepted Identity/BFF/current-authorization semantics through a real backend/BFF/frontend shell, together with the minimum G0 bootstrap required to run and prove that slice.

## Authorization on acceptance

If this exact package is reviewed, accepted and separately merged, canonical implementation may begin for exactly one vertical slice:

- `g1.identity-tenant-protected-shell@1`.

The observable outcome is:

> an authenticated user can enter a tenant-scoped JLMirror application shell, the BFF establishes current platform authorization independently of token validity, and forbidden/cross-tenant context fails closed.

## Allowed G0 bootstrap inside the G1 slice

G0 is not authorized as a speculative platform program. Only bootstrap required by the G1 slice may be introduced:

- one reproducible local dependency stack for G1;
- one database migration/bootstrap entrypoint needed by G1;
- one backend/BFF start entrypoint;
- one frontend start entrypoint;
- one fixture/test tenant and identity bootstrap;
- exact-head local/CI parity commands;
- container/runtime proof for components introduced by G1.

No shared foundation may be invented unless G1 consumes it immediately or an accepted architecture contract requires it.

## Accepted authority consumed

G1 SHALL reuse rather than redefine:

- accepted Wave 1 identity/BFF/current-authorization substrate;
- accepted D3 Identity/Security mechanism dispositions;
- canonical API/BFF and security contracts;
- canonical tenant isolation, current membership/permission, placement and authentication-strength authority rules;
- the AI E2E Delivery Constitution, Product Execution Roadmap and Vertical Slice Delivery Model.

The following remain mechanically true:

```text
JWT_VALIDITY != CURRENT_AUTHORIZATION
IDP_IDENTITY != PLATFORM_MEMBERSHIP_AUTHORITY
WORKLOAD_IDENTITY != TENANT_BUSINESS_AUTHORITY
NETWORK_PRESENCE != TRUST
BROWSER_SESSION_HANDLE != BUSINESS_AUTHORITY
CLIENT_TENANT_ID != TENANT_AUTHORITY
```

## Product surface authorized

The later implementation slice may add only what is needed for:

- OIDC Authorization Code + PKCE S256 through the confidential BFF boundary;
- opaque server-side BFF session capability;
- current tenant selection/admission based on platform truth;
- current membership/permission read required by the protected shell;
- authenticated BFF route(s) required by the shell;
- protected application shell and minimal tenant context display;
- loading, success, forbidden, unauthenticated, unavailable and revoked/stale-authority states;
- browser E2E proving allowed and forbidden/cross-tenant paths;
- adversarial/recovery proof for stale session/current-authority changes.

## Explicit non-authority

This gate does **not** authorize:

- G2 Monitoring Source onboarding or any Monitoring product UI;
- Resource, Metric, Problem or Health product surfaces;
- Alert creation, Alert policy/evaluation, ACK, notification or escalation;
- ITSM, Automation, AIOps, FinOps or Commercial behavior;
- production deployment;
- production C3 capacity, retention, timeout, rotation, topology, SLO, RPO or RTO numerics;
- provider-native roles/groups/organizations as JLMirror authorization truth;
- direct browser possession of refresh tokens or long-lived platform access credentials;
- client-supplied tenant identity as authorization proof;
- a generic design system, navigation framework or speculative frontend information architecture beyond the protected shell needed by G1.

## Historical authority rule

Earlier D3/D4 records that state canonical Product implementation authority was not granted remain immutable source-time truth. This successor authorization, if accepted, authorizes only this exact G1 slice and does not rewrite those historical snapshots.

```text
HISTORICAL_NOT_GRANTED != CURRENT_AUTHORIZATION_REGRESSION
SUCCESSOR_G1_AUTHORIZATION != GLOBAL_PRODUCT_AUTHORITY
G1_AUTHORIZED != G2_AUTHORIZED
G1_AUTHORIZED != PRODUCTION_AUTHORIZED
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```

## Merge boundary

This document remains a proposal until the exact PR HEAD passes dedicated authorization validation, deterministic assurance, panoramic/adversarial review and zero unresolved material findings, followed by separate explicit owner authorization for squash merge.
