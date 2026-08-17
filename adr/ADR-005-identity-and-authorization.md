# ADR-005 — Identity, Membership and Authorization Boundaries

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

Identity and tenant authorization are different concerns. A human identity may belong to multiple tenants, machine principals require independent credentials, and global support/admin operations must not be hidden wildcard roles. Browser token exposure should be minimized while APIs must remain usable by non-browser clients.

Drivers: `FR-ID-*`, `FR-ORG-*`, `INV-AUTHZ-*`, `SEC-ID-*`, `SEC-AUTHZ-*`, `TM-003`, `TM-013`.

## Decision

JLMIRROR SHALL separate:

1. **Identity** — principal, authentication bindings, MFA, credential/session lifecycle;
2. **Membership** — relationship between identity and tenant;
3. **Authorization policy** — roles/permissions/resource scopes within tenant or explicit platform scope.

Protected operations are deny-by-default and declare required permission/policy at the owning server-side boundary. Cross-tenant/platform operations are distinct privileged capabilities, not implicit `*:*` behavior.

For the web application, the browser SHALL use a BFF-managed confidential session with Secure/HttpOnly cookie semantics; raw long-lived API credentials/refresh credentials are not intentionally exposed to browser JavaScript. The BFF authenticates to the API using a server-side credential/session representation.

Direct API/machine clients SHALL use explicit machine/API credentials or standards-based token mechanisms with independent revocation and scope.

External identity providers integrate through standards/provider adapters and do not redefine tenant membership semantics.

## Consequences

### Positive
- global identity can participate in multiple tenants cleanly;
- browser attack surface for bearer tokens is reduced;
- authorization is explainable/auditable;
- machine access and human sessions have separate lifecycle policy.

### Negative / cost
- BFF session infrastructure is required;
- membership/authorization evaluation must be efficient and consistently cached if cached at all;
- token/session protocol selection remains a separate implementation ADR.

## Validation

- UI hiding cannot bypass server authorization;
- role/feature-flag confusion tests deny unauthorized actions;
- cross-tenant support requires explicit privileged operation and audit;
- credential revocation behavior survives multiple API replicas.

## Exit / revisit conditions

Revisit browser session transport only if client architecture changes materially (for example native-only application). Identity/membership separation remains architectural.
