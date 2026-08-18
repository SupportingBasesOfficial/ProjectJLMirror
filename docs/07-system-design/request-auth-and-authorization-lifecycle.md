# Request, Authentication and Authorization Lifecycle

**Status:** proposed baseline  
**Primary ADRs:** ADR-005, ADR-007, ADR-011, ADR-014, ADR-017

## Tenant-scoped HTTP lifecycle

```text
First-party browser -> Web/BFF
Machine/API principal -> API ingress
                    |
                    v
Authentication verification
                    |
                    v
Logical tenant selection/claim validation
                    |
                    v
Trusted placement resolution
                    |
                    v
Route to authoritative cell
                    |
                    v
Cell validates placement admission/version
                    |
                    v
Resolve TenantContext
                    |
                    v
Validate request contract
                    |
                    v
Evaluate server-side authorization
                    |
                    v
Execute application use case
                    |
                    +--> authoritative transaction if mutating
                    |
                    +--> audit/outbox as required
                    |
                    v
Return versioned response contract
```

No step is allowed to convert client-supplied physical routing data into trusted placement.

## Authentication versus membership versus authorization

- **Authentication** proves/establishes a principal.
- **Membership** establishes that a principal belongs to a tenant and its membership state.
- **Authorization** determines whether that principal/membership may perform a specific action in a specific scope.

These are separate checks. A valid login is not tenant authorization; tenant membership is not permission to every tenant resource.

## Browser/BFF boundary

The first-party browser application **MUST** use the BFF as its confidential-client and session boundary. Browser JavaScript MUST NOT receive, persist, or intentionally operate with long-lived platform access credentials or refresh credentials.

The BFF owns browser-facing session establishment/refresh orchestration, HttpOnly credential handling where applicable, CSRF/browser protections and request composition. The API independently validates authentication, tenant context and authorization and does not trust the BFF as an authorization oracle.

### Protected direct realtime

A protected first-party browser realtime connection may bypass the normal BFF request hop only after an authenticated same-site BFF request mints a short-lived, narrowly scoped connection capability.

Before accepting the protected WebSocket upgrade, the realtime gateway MUST validate:

- the expected allowlisted browser `Origin`;
- the connection capability authenticity, expiry and intended principal/tenant/realtime scope;
- **current authorization for that principal/tenant/realtime scope**, including current session, membership, permission/scope and tenant-access state, using either a fresh authoritative evaluation or a trusted authorization/session generation/revocation marker proven current at handshake time;
- applicable pre-upgrade abuse/connection-admission limits;
- and, as the final replay-admission gate, atomically claim/consume the capability's unique replay identity in a shared authority so concurrent gateway replicas cannot both treat the same capability as unused.

Capability replay protection is an admission mutation, not a read-only "is unused?" check. For a single-use capability, exactly one concurrent handshake may successfully transition the capability identity from unused/available to consumed; every losing handshake MUST be rejected before `101 Switching Protocols`. If the accepted contract permits a bounded use count greater than one, the shared authority MUST enforce that bound atomically.

The atomic consume occurs only after the other required pre-upgrade validations pass and immediately before successful upgrade admission. If the gateway consumes the capability and then fails before returning `101`, the capability remains consumed and the client must obtain a new capability; fail-safe credential burning is preferred to replay ambiguity. If the shared replay/consume authority is unavailable or cannot prove single-winner consumption, protected upgrade admission fails closed.

A capability proves that authority existed when it was minted; it does **not** freeze that authority until expiry. If the gateway cannot safely establish authorization freshness at handshake time, the protected upgrade fails closed.

Failure of any required pre-upgrade check or atomic capability consumption rejects the HTTP handshake before `101 Switching Protocols`; the gateway does not retain an unauthorized or replay-losing protected socket and then merely suppress subscriptions afterward.

The capability is bound to the intended principal/tenant/realtime purpose, expires quickly and is single-use or otherwise replay-bounded. It is not a refresh token or a general API bearer credential. An authorization/session generation carried by the capability is only a freshness reference and MUST be compared with trusted current state; it is not self-authorizing after revocation.

An ambient HttpOnly session cookie by itself **MUST NOT** authorize a protected direct browser WebSocket. A future cookie-authenticated direct-socket design requires a separate security decision proving pre-upgrade Origin validation, current authorization and an anti-CSRF/connection proof with equivalent protection.

Public unauthenticated endpoints/transports are separate exposure contracts.

Machine/API principals may use the API directly under independently revocable machine credentials and explicit tenant/permission scope.

## Validation ordering

Implementations MAY perform cheap syntax/size validation before expensive placement/database work, but protected use cases MUST NOT reveal protected resource existence before authentication/tenant authorization semantics are established.

For untrusted callbacks/webhooks, transport-level raw byte bounds are allowed and required before expensive authentication/signature processing; this does not authorize or semantically validate the payload.

The owning use case receives validated typed input, not raw transport payloads.

## Authorization contract

Every protected operation declares:

```text
action              canonical permission/policy action
scope               platform | tenant | resource/group or accepted refinement
tenant_requirement  none | required | explicit cross-tenant privileged
step_up             whether stronger/recent authentication is required
audit_class         none | normal | privileged | security-critical
```

Deny is the default when required policy cannot be evaluated safely.

## Cross-tenant platform operation

Global/support operations are modeled as distinct operations. They do not gain authority by substituting `tenant_id=*` or bypassing tenant policy implicitly.

A cross-tenant operation records:

- platform principal;
- purpose/action;
- target tenant(s);
- authorization policy used;
- optional approval/step-up where policy requires;
- correlation/request identifiers;
- outcome and audit record.

## Error behavior

External error contracts use stable codes/classes and safe messages. They do not expose stack traces, secret values, raw SQL, physical placement, internal network details or unauthorized resource existence.

Internal telemetry contains enough correlation to diagnose the failure while remaining tenant-safe.
