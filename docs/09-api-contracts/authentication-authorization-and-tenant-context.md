# Authentication, Authorization and Tenant Context

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Authentication, tenant membership, authorization and physical placement are separate concerns and remain separate in the API contract.

A valid credential does not imply tenant access. A tenant ID in the URI does not prove membership. A routed request does not prove authorization. A BFF does not become an authorization oracle for the downstream API.

For externally reachable HTTP surfaces, authentication itself consumes only a request that has already passed `http-message-framing-and-canonicalization.md`. Framing/header/authority/request-target ambiguity is rejected before any credential, tenant or authorization interpretation is accepted.

## Principal classes

Phase 09 recognizes these logical principal classes:

```text
human_browser_session
human_api_session (only if separately accepted)
machine_api_principal
internal_service_principal
platform_admin_principal
provider_callback_identity
scheduled/system_process
```

Exact authentication/token technology remains OPEN unless already constrained by an accepted decision. Contract behavior SHALL depend on principal semantics, scope, revocability and current authorization rather than a vendor-specific token shape.

## First-party browser

The first-party browser SHALL use the BFF as the confidential session boundary.

Browser JavaScript SHALL NOT intentionally receive or persist long-lived platform access credentials or refresh credentials.

The BFF owns browser-specific session/cookie handling, CSRF protections and safe request composition. The downstream API still independently resolves tenant context and evaluates authorization.

Security-relevant cookie/header parsing uses one accepted canonical meaning across the trusted edge and BFF. Duplicate/conflicting session/authentication/CSRF material cannot be resolved differently by different hops.

## Machine/API principals

Machine credentials SHALL be independently revocable and attributable. Their effective authority includes:

- principal/credential identity;
- allowed tenant/global scope;
- permission/action scope;
- credential status/revocation;
- expiration/lifecycle constraints;
- applicable network/client policy when accepted.

A credential MAY be restricted to one tenant or permitted to name multiple tenants. The request's `tenant_id` must still be authorized against the credential's current scope at the authoritative owning boundary.

Exact credential transport/format remains an authentication-profile decision until separately accepted. Phase 09 contracts SHALL NOT require business consumers to understand identity-provider internals.

`Authorization` or equivalent machine-credential transport follows explicit security-sensitive header cardinality semantics. Competing credential values cannot reach authentication logic and be selected by first/last/framework behavior.

## Tenant-scoped authorization

A protected tenant route conceptually evaluates:

```text
canonical HTTP ingress
  -> Identity
  -> current credential/session validity
  -> intended tenant_id
  -> trusted placement resolution
  -> route to authoritative cell
  -> current placement admission/version
  -> trusted TenantContext construction
  -> request-contract validation
  -> current membership / machine tenant scope
  -> permission/action
  -> resource scope/policy
  -> owning use case
```

Membership, permission and resource-policy evaluation SHALL occur at the owning server-side authority after the request has been routed to the authoritative cell, a trusted current TenantContext exists, and caller-controlled fields consumed by the owning policy have passed the request contract.

Canonical HTTP ingress and request-contract validation are different gates. The former proves every participating HTTP hop agrees on the request/framing/security-header/request-target meaning. The latter validates the agreed caller-controlled fields under the trusted TenantContext before owning authorization consumes them.

Request-contract validation before owning authorization SHALL NOT become a protected-information oracle. Cheap transport bounds/syntax checks may fail early where safe, but semantic checks that would reveal protected resource existence remain behind the required authentication/tenant authority gates.

Ingress/global checks MAY reject a credential or tenant target earlier when global authoritative evidence is sufficient, but such checks are only fail-fast/narrowing gates. They SHALL NOT be treated as proof of cell-owned membership or resource authorization and SHALL NOT bypass the owning authorization decision.

The server SHALL deny when any mandatory authority cannot be established safely.

## Canonical authorization declaration

Every protected operation declares at minimum:

```text
action              canonical permission/policy action
scope               platform | tenant | resource/group refinement
tenant_requirement  none | required | explicit cross-tenant privileged
step_up             none | policy-driven | required
audit_class         none | normal | privileged | security-critical
```

Suggested canonical action naming follows:

```text
<domain>.<resource>.<verb>
```

Examples:

```text
monitoring.resources.read
monitoring.sources.manage
itsm.incidents.create
itsm.incidents.resolve
automation.executions.start
reporting.artifacts.download
organization.memberships.manage
platform.tenants.suspend
```

Permission names describe platform semantics, not controller/class names.

## Resource-level scope

Phase 09 SHALL NOT assume tenant-wide RBAC is the permanent ceiling. Contracts and permission naming must permit future refinement to groups, resources, services, environments, projects or other accepted scopes without renaming the domain/resource itself.

An initial implementation MAY evaluate a tenant-wide permission when finer scope does not yet exist, provided the contract does not falsely promise that tenant-wide scope is permanent.

## Cross-tenant privileged operations

Cross-tenant operations are distinct platform operations. They do not use `tenant_id=*`, a wildcard membership or a bypass flag on ordinary tenant endpoints.

A cross-tenant operation records/audits:

- platform principal;
- operation/action;
- explicit target tenant(s) or target selection criteria;
- purpose/reason where policy requires;
- step-up/approval where applicable;
- request/correlation identifiers;
- outcome.

## TenantContext propagation

The external API exposes logical tenant identity, never a trusted physical TenantContext object.

After canonical HTTP ingress, authentication, trusted placement resolution, routing to the authoritative cell and current placement admission/version validation, the cell constructs the accepted canonical `TenantContext`. Request-contract validation and the owning membership/permission/resource authorization then execute against that trusted context before the protected use case runs.

Caller-controlled headers/body fields SHALL NOT be allowed to override trusted internal `cell_id`, `placement_version`, database target or authorization context.

## No physical routing headers

The public/BFF API SHALL NOT accept caller-authoritative headers such as:

```text
X-Cell-Id
X-Database
X-Schema
X-Shard
X-Cluster
X-Secret-Ref
```

An internal trusted transport may carry signed/authenticated routing metadata between platform components, but that is not a public client contract.

Trusted proxy metadata is likewise not ordinary caller authority. `Forwarded`, `X-Forwarded-*` or equivalent deployment metadata is accepted only from the configured trusted proxy boundary after canonicalization; untrusted copies cannot select tenant placement, credential interpretation or protected routing.

## Existence concealment

When revealing whether a protected resource exists would leak unauthorized tenant/resource information, the operation MAY return the same externally safe not-found response used for absence.

The contract SHALL define when `403` versus existence-concealing `404` is used. Internal audit/telemetry retains the true denial reason where policy permits.

## Step-up authorization

High-risk operations MAY require stronger/recent authentication or approval. The contract declares this explicitly.

A missing step-up requirement is not represented as a generic validation error. It uses a stable authorization/problem code that a first-party client can use to invoke the appropriate re-authentication/approval flow without exposing sensitive policy details.

## Delayed/asynchronous user authority

Request-time human authorization is not durable execution authority.

For user-requested delayed import/export/report/other protected work:

- authorization is checked at request creation;
- the worker/process re-establishes current tenant context and current applicable authority immediately before protected execution;
- release/download is reauthorized where the accepted baseline requires it;
- resumed multi-stage protected mutation rechecks when prior authorization may no longer be fresh.

A queued job containing `requested_by` or request-time permission metadata does not allow execution after the human's authority is revoked.

## Authorization freshness and recovery

A restored older positive grant SHALL NOT override a later revoke/deny that must survive recovery under the accepted `(R,F]` continuity model.

Contracts exposing current session/membership/credential status SHOULD make freshness/revision semantics explicit enough for clients to reason about revocation outcomes without exposing internal recovery topology.

## Realtime distinction

Realtime connection admission and realtime subscription authorization are separate gates.

A BFF-minted connection capability proves bounded connection intent. It does not grant arbitrary subscriptions and does not freeze authority until expiry.

Protected subscription details/message envelopes belong to the later async/realtime contract layer, but Phase 09 fixes canonical HTTP ingress plus the pre-`101` admission behavior in the dedicated BFF/realtime document.

## Provider callbacks

Provider callback identity is derived from configured integration/provider authentication, not tenant IDs supplied in the callback payload.

A callback route may include an opaque integration/callback identifier for lookup, but the adapter SHALL bind the resulting tenant/integration context from trusted configuration and authenticated callback evidence.

Callback authentication also consumes the canonical framed/header interpretation defined by the callback ingress contract; duplicate/conflicting provider-auth headers or body-framing ambiguity cannot create alternate identities.

## Authorization contract tests

Every protected endpoint SHALL have contract/integration tests that prove at minimum:

- ambiguous HTTP framing/security-sensitive credential headers cannot reach authentication/authorization with competing interpretations;
- gateway/BFF/proxy and owning service agree on canonical authority/request target used for credential and tenant/resource selection;
- unauthenticated denial;
- wrong-tenant denial;
- authoritative placement/cell admission occurs before cell-owned membership/resource authorization;
- trusted request-contract validation occurs after TenantContext construction and before owning authorization consumes caller-controlled resource/scope fields;
- malformed/invalid caller resource/scope input cannot alter or widen authorization authority;
- validation ordering does not leak protected resource existence before required auth/tenant authority gates;
- ingress/global prechecks cannot substitute for owning authorization;
- insufficient permission denial;
- stale/revoked session or credential denial where applicable;
- resource-scope denial where applicable;
- no physical routing override;
- expected cross-tenant privileged behavior when such a route exists;
- error response does not leak protected resource existence or internal topology beyond the accepted contract.

Tests that cross a gateway/proxy/runtime boundary SHOULD exercise the actual deployed parser/translation path; controller-only tests are insufficient proof against request ambiguity.