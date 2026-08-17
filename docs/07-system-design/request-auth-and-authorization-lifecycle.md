# Request, Authentication and Authorization Lifecycle

**Status:** proposed baseline  
**Primary ADRs:** ADR-005, ADR-007, ADR-014, ADR-017

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

A browser MAY connect directly only to an explicitly designed public endpoint or realtime transport whose browser credential semantics preserve this boundary—for example an HttpOnly session or a short-lived, narrowly scoped connection capability minted through the BFF. Such a path MUST NOT become a direct long-lived bearer/refresh-token flow in browser JavaScript.

Machine/API principals may use the API directly under independently revocable machine credentials and explicit tenant/permission scope.

## Validation ordering

Implementations MAY perform cheap syntax/size validation before expensive placement/database work, but protected use cases MUST NOT reveal protected resource existence before authentication/tenant authorization semantics are established.

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
