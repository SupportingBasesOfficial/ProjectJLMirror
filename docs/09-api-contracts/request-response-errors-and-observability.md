# Request, Response, Errors and Observability

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## HTTP method semantics

Phase 09 uses standard HTTP method intent:

- `GET` — retrieve a resource/projection; no intended authoritative mutation;
- `POST` — create a resource or invoke a non-idempotent-by-method command/use case protected by the idempotency contract where retry matters;
- `PATCH` — partial mutation under an operation-specific schema;
- `PUT` — full idempotent replacement only when the resource contract genuinely supports it;
- `DELETE` — request contract-level deletion/removal, possibly resulting in asynchronous governed work;
- `HEAD` — MAY be supported where metadata/existence semantics are useful and safe.

A route SHALL NOT use `GET` to trigger a protected state change.

## Success status semantics

The baseline uses these meanings:

### `200 OK`

The requested synchronous operation completed and the response contains the current logical result/projection promised by the contract.

### `201 Created`

A new resource was durably created. The response SHOULD identify the canonical resource URI via `Location` when practical.

`201` is not returned if only a queued intent exists and the resource is not yet contractually created.

### `202 Accepted`

A durable operation/process has accepted responsibility for work that is not yet terminal, including long-running processing or an externally ambiguous effect being reconciled.

A `202` response SHALL expose or link a stable operation resource. It does not mean the requested business outcome succeeded.

### `204 No Content`

A synchronous operation completed successfully and the contract intentionally has no response body. It SHALL NOT be used when the caller needs an operation resource or resulting representation to determine outcome.

## Response shape

Single-resource successful responses return the resource/result representation directly unless a use case requires additional top-level metadata.

The API does not wrap every successful response in generic structures such as:

```json
{"success": true, "data": {}}
```

because HTTP status plus typed response schemas already communicate transport success, and generic wrappers create unnecessary coupling.

Collections use the collection contract defined in the pagination document.

## Safe error model

Errors use a consistent problem representation with a stable machine-readable `code` independent of human wording.

Conceptual shape:

```json
{
  "type": "urn:jlmirror:problem:authorization-denied",
  "title": "Operation not permitted",
  "status": 403,
  "code": "authorization.permission_denied",
  "detail": "The current principal is not permitted to perform this operation.",
  "instance": "/api/v1/tenants/.../incidents/...",
  "request_id": "req_opaque",
  "correlation_id": "corr_opaque"
}
```

Validation problems MAY add bounded structured field errors:

```json
{
  "errors": [
    {
      "path": "$.name",
      "code": "validation.required",
      "message": "name is required"
    }
  ]
}
```

Human messages MAY improve over time. Machine behavior SHALL depend on stable `code`, status and documented fields, not exact prose.

## Error code namespace

Stable codes use logical categories, for example:

```text
authentication.required
authentication.credential_expired
authorization.permission_denied
authorization.step_up_required
tenant.not_found
tenant.not_admitted
resource.not_found
validation.invalid_request
validation.semantic_conflict
concurrency.precondition_required
concurrency.revision_mismatch
idempotency.key_reused
idempotency.in_progress
operation.reconciliation_required
rate_limit.exceeded
dependency.temporarily_unavailable
```

Domain contracts define additional domain-specific codes without exposing internal exception/class names.

## Baseline status mapping

Preferred mapping:

```text
400  malformed request / invalid syntax or generic request contract violation
401  authentication missing/invalid/expired when reauthentication is required
403  authenticated but not authorized, when existence disclosure is safe
404  resource absent or existence intentionally concealed
409  domain conflict / idempotency-key conflict or currently non-executable state
412  conditional request / revision precondition failed
422  syntactically valid request that fails documented semantic validation
428  required optimistic-concurrency precondition was omitted
429  request rejected by accepted usage/rate policy
500  unexpected server failure without sensitive detail
502  upstream protocol/gateway failure where externally meaningful
503  required dependency/authority unavailable and operation did not complete under the promised contract
504  gateway/dependency deadline where outcome semantics are still safe to classify as timeout
```

A route MAY use a more specific status when its contract documents the semantics. The machine-readable code remains the primary stable discriminator.

## Ambiguous effect errors

The API SHALL NOT return a generic retryable timeout when an irreversible external effect may already have occurred and a blind retry could duplicate it.

If durable operation/reconciliation state exists, the preferred external outcome is:

```text
202 Accepted
Location: <stable operation resource>
```

with the operation indicating `reconciliation_required` or an equivalent non-terminal state.

If the platform cannot establish safe durable tracking, the route fails conservatively under its contract and SHALL NOT invite automatic blind retry.

## Validation ordering and information leakage

Cheap request-shape/size checks MAY run before expensive authorization/database work, but protected operations SHALL NOT reveal protected resource existence through semantic validation before required authentication/tenant-authorization gates.

Provider callbacks remain subject to their separate rule: hard raw transport bounds are enforced before complete buffering/signature work.

## Request limits

Every endpoint class declares applicable bounds such as:

- maximum request-body bytes;
- maximum collection/bulk item count;
- maximum string/list/object depth or complexity where relevant;
- timeout/deadline policy where externally configurable;
- upload limits;
- filter/sort/include complexity.

Global infrastructure limits MAY be stricter during incident protection, but normal client contracts must define stable maximums or discoverable plan/policy constraints before relying on unlimited input.

## Request ID

Every API/BFF request receives a server-generated opaque `request_id`.

The response exposes it using:

```text
X-Request-Id: <opaque value>
```

and error bodies include `request_id`.

A client-supplied `X-Request-Id` is not trusted as the server's unique request identity.

## Correlation ID

Clients MAY supply a bounded opaque:

```text
X-Correlation-Id: <value>
```

for business/workflow correlation when accepted by the endpoint. The server validates size/character policy and may replace unsafe/invalid values.

When absent, the platform establishes a correlation ID. Responses SHOULD expose the effective value:

```text
X-Correlation-Id: <effective value>
```

Correlation IDs are not authorization or idempotency keys.

## Distributed tracing

Implementation MAY additionally propagate accepted distributed tracing context. External tracing headers never grant tenant/resource authority and are filtered from logs/telemetry according to security policy.

## Deadlines

Clients SHOULD be allowed to enforce their own network timeout without changing operation correctness. Server-side deadline/cancellation behavior is endpoint-specific.

A client disconnect SHALL NOT be treated as proof that a committed mutation or accepted external operation did not occur.

## Retry guidance

Responses MAY include `Retry-After` for throttling, temporary unavailability or in-progress idempotency/operation states where a later retry/read is safe.

The presence of `Retry-After` does not override the operation's idempotency semantics.

## Error privacy

External error responses SHALL NOT expose:

- stack traces;
- SQL text or database identifiers;
- cell/schema/cluster addresses;
- secret/token values;
- raw provider credentials;
- internal filesystem paths;
- sensitive policy rules that enable bypass;
- protected data belonging to another tenant.

Internal logs/traces may capture richer diagnostics only under accepted redaction/classification policy.

## Observability contract

Every externally meaningful request SHALL be correlatable to its owning use case and, where applicable, subsequent operation/job/provider work.

At minimum internal telemetry can associate:

```text
request_id
correlation_id
tenant-safe identity
principal/credential identity where policy permits
operation/use-case name
outcome/status class
latency
downstream operation_id when created
```

Observability fields never become a backdoor for secret/PII leakage.

## Health endpoints

Liveness/readiness/dependency health endpoints are operational contracts and SHALL distinguish process liveness from safe traffic readiness.

Detailed dependency/internal topology health is not exposed publicly by default. External health views use deliberately safe projections.