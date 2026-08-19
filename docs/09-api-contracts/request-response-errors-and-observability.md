# Request, Response, Errors and Observability

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Canonical HTTP request prerequisite

Every externally reachable HTTP request described by this document first passes `http-message-framing-and-canonicalization.md`.

Authentication, tenant routing, idempotency admission, cache selection, request-contract validation and protected use cases consume the resulting canonical request rather than independently interpreting raw framing, duplicate security-sensitive headers, trusted-proxy metadata or an ambiguous request target.

A transport/framing/canonicalization rejection occurs before the request is treated as a valid protected operation and SHALL NOT create an idempotency claim, durable operation or protected domain effect.

## HTTP method semantics

Phase 09 uses standard HTTP method intent:

- `GET` — retrieve a resource/projection; no intended authoritative mutation;
- `POST` — create a resource or invoke a non-idempotent-by-method command/use case protected by the idempotency contract where retry matters;
- `PATCH` — partial mutation under an operation-specific schema;
- `PUT` — full idempotent replacement only when the resource contract genuinely supports it;
- `DELETE` — request contract-level deletion/removal, possibly resulting in asynchronous governed work;
- `HEAD` — MAY be supported where metadata/existence semantics are useful and safe.

A route SHALL NOT use `GET` to trigger a protected state change.

There is one canonical HTTP method. Generic method-override mechanisms such as `X-HTTP-Method-Override`, `X-Method-Override`, query/form `_method` or framework equivalents are not accepted by default. A future compatibility profile that requires method override must be explicitly reviewed under the canonical HTTP ingress contract so routing, CSRF, authorization, idempotency and caching all observe the same effective method.

## Success status semantics

The baseline uses these meanings:

### `200 OK`

The requested synchronous operation completed and the response contains the current logical result/projection promised by the contract.

### `201 Created`

A new resource was durably created. The response SHOULD identify the canonical resource URI via `Location` when practical.

`201` is not returned if only a queued intent exists and the resource is not yet contractually created.

`Location` and other server-generated links SHALL NOT copy protected cursor/query/credential material into a new URL unless the target contract explicitly requires a bounded non-reusable capability and applies its dedicated leakage controls.

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

## Response cache contract

Every endpoint SHALL declare an explicit response-cache class. Browser, reverse-proxy, gateway, CDN or framework defaults SHALL NOT silently decide whether a representation may be stored or shared.

The baseline semantic classes are:

```text
no_store
private_revalidate
public_shared
artifact_delivery_guarded
```

The cache contract applies to **all response variants**, including success, redirect where allowed, conditional responses and errors. An endpoint SHALL NOT define a safe success cache policy while leaving authentication/authorization/not-found/error responses to intermediary defaults.

A cache/reverse proxy is eligible to process/cache a request only after applying the same canonical method/authority/path/query/header meaning accepted by the owning service. Ambiguous requests are not valid cache candidates.

### `no_store`

Use when a response contains or is materially derived from secrets, credential/session material, one-time secret presentation, security-sensitive mutation results, authorization-sensitive data whose storage is not explicitly accepted, or any response where retention by an intermediary would create unacceptable disclosure/replay risk.

`no_store` SHALL emit behavior equivalent to `Cache-Control: no-store`. A more permissive infrastructure default cannot override it.

Secret-bearing responses are always `no_store`.

Authentication, authorization, step-up and existence-concealing protected error responses default to `no_store` unless a stricter reviewed endpoint contract proves an equally safe behavior. A shared cache SHALL NOT reuse a protected `401`, `403` or concealed `404` across principals/tenants.

### `private_revalidate`

A response may be stored only in a caller-private cache and must be revalidated according to the endpoint contract before reuse when freshness/authorization matters. Shared intermediaries SHALL NOT reuse it across principals or tenants.

The endpoint SHALL declare:

- the logical variance relevant to the representation;
- validator/revalidation behavior where used (`ETag`/conditional request or equivalent);
- whether authorization/membership freshness requires server re-evaluation before reuse;
- any maximum freshness duration when accepted.

A private cache key MUST NOT collapse different tenant/principal representations merely because the URI is identical in an intermediary implementation.

### `public_shared`

Shared caching is allowed only for a deliberately public projection whose representation does not depend on protected caller authority.

The endpoint SHALL explicitly define:

- public cacheability;
- cache key/variance dimensions that are externally safe;
- freshness/revalidation/staleness policy;
- invalidation behavior where required;
- numeric lifetime values or an explicit `OPEN` item before implementation.

A protected tenant resource does not become `public_shared` merely because a CDN is available.

### `artifact_delivery_guarded`

Protected artifact bytes are governed by the accepted artifact delivery-generation, active-lease/stream and erasure-fencing invariants.

A cache/CDN may participate only if its behavior preserves equivalent current authorization/releasability and revocation/fencing semantics. A cache hit SHALL NOT bypass current delivery admission when the artifact class requires it. If equivalent fencing cannot be proven, protected artifact delivery falls back to non-shared/no-store behavior.

Public immutable artifacts, if Product later defines them, use a separate explicit public contract rather than inheriting protected artifact semantics.

### Variance and authorization

`Vary` or equivalent cache-key metadata is not an authorization mechanism. A shared cache SHALL NOT be made safe merely by adding a caller-controlled tenant/principal header to its key.

Protected cacheability is accepted only when the endpoint contract proves that no representation can cross a tenant/principal/security boundary and that authorization/revocation semantics remain correct.

Exact public/private freshness durations and optional optimization headers remain policy/evidence-driven under `OPEN-API-017`; `no_store` security semantics are not OPEN.

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

`instance` identifies the request/resource context at a safe level. It SHALL NOT echo raw query strings, cursors, secrets, one-time capabilities or confidential filter/search values. If the exact URL contained protected transport metadata, the problem representation uses the safe path/reference rather than reflecting that metadata.

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
secret.delivery_not_replayable
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
409  domain conflict / idempotency-key conflict / one-time-secret replay conflict or currently non-executable state
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

Malformed transport/framing requests may be rejected by the edge/HTTP stack before the normal problem representation is available. Exact safe status mapping remains deployment/profile OPEN; such errors never reveal which parser/hop would have accepted an alternate interpretation.

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

For tenant-scoped HTTP requests whose membership/resource authority is cell-owned, the accepted order is:

```text
canonical HTTP ingress
 -> authenticate
 -> logical tenant intent
 -> trusted placement resolution
 -> authoritative route
 -> cell admission/current placement version
 -> trusted TenantContext
 -> request-contract validation
 -> owning membership/permission/resource authorization
 -> use case
```

Canonical HTTP ingress proves one accepted framing/header/authority/request-target/body interpretation. Request-contract validation later proves that the already agreed caller-controlled fields are valid and bounded under the trusted TenantContext before owning authorization consumes them. Neither gate substitutes for the other.

Request-contract validation before owning authorization is specifically the validation needed to ensure caller-controlled path/query/header/body fields are well-formed, bounded and safe to consume as policy/resource inputs. It SHALL NOT perform protected semantic existence checks that would leak information before the owning authority gate.

Provider callbacks remain subject to their specialized ordering: canonical HTTP framing first, then hard raw transport bounds before complete buffering/signature work, followed by provider authentication/freshness/replay rules.

## Request limits and content interpretation

Every endpoint class declares applicable bounds such as:

- maximum request-body raw bytes;
- maximum decoded/decompressed bytes where content coding is accepted;
- maximum HTTP header count/bytes/per-field size under the platform profile;
- maximum collection/bulk item count;
- maximum string/list/object depth or complexity where relevant;
- timeout/deadline policy where externally configurable;
- upload limits;
- filter/sort/include complexity.

`Content-Encoding`/content-coding is explicitly interpreted by the accepted surface/endpoint profile. Unsupported, malformed or ambiguously ordered codings are rejected rather than decoded differently by edge and application. Raw and decoded size bounds are independent.

Request trailers cannot introduce/override authentication, idempotency, tenant/routing, CSRF/Origin, conditional-precondition, callback-security or other protected authority after initial header admission unless an explicitly reviewed profile defines a safe non-security trailer field.

Global infrastructure limits MAY be stricter during incident protection, but normal client contracts must define stable maximums or discoverable plan/policy constraints before relying on unlimited input.

## Request ID

Every API/BFF request receives a server-generated opaque `request_id` after or as part of accepted ingress handling.

The response exposes it using:

```text
X-Request-Id: <opaque value>
```

and error bodies include `request_id` where a normal application response exists.

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

Correlation IDs are not authorization or idempotency keys. Their header cardinality follows the accepted HTTP message profile and cannot be interpreted differently across hops.

## URL/query confidentiality and logging

URLs are operationally high-propagation data: browsers, reverse proxies, access logs, analytics, traces, referrers, support tooling and redirect targets may observe them even when the network connection uses HTTPS.

Therefore:

- endpoints classify path/query parameters for URL suitability;
- credentials, one-time capabilities, confidential/restricted search/filter values and protected cursor payloads SHALL NOT be placed in URL text unless a separately accepted profile explicitly requires a bounded capability and defines leakage controls;
- normal access logs/analytics/traces SHALL NOT record raw protected cursor/query values; use parameter-name-only logging, redaction, hashing/reference or another accepted safe representation;
- error `instance`, tracing attributes and metrics labels SHALL NOT duplicate raw protected query strings;
- server redirects/links SHALL NOT propagate protected query/cursor material to unrelated origins or third-party destinations;
- referrer policy for any browser surface carrying bounded sensitive URL material SHALL prevent unintended propagation according to that surface's accepted profile.

A cursor being opaque to clients does not make its URL representation non-sensitive. Encoding/signing alone is not confidentiality.

## Distributed tracing

Implementation MAY additionally propagate accepted distributed tracing context. External tracing headers never grant tenant/resource authority and are filtered from logs/telemetry according to security policy.

Trace/span attributes use safe normalized route templates and redacted query metadata rather than unbounded/raw protected URLs.

Tracing/proxy middleware consumes the canonical request meaning and must not reconstruct a competing route/authority/request target from raw untrusted forwarding metadata.

## Deadlines

Clients SHOULD be allowed to enforce their own network timeout without changing operation correctness. Server-side deadline/cancellation behavior is endpoint-specific.

A client disconnect SHALL NOT be treated as proof that a committed mutation or accepted external operation did not occur.

## Retry guidance

Responses MAY include `Retry-After` for throttling, temporary unavailability or in-progress idempotency/operation states where a later retry/read is safe.

The presence of `Retry-After` does not override the operation's idempotency semantics.

A request rejected at canonical HTTP ingress before protected admission may be retried only after the client constructs a valid unambiguous request; such a rejection is not evidence that an idempotency claim/effect existed.

## Error privacy

External error responses SHALL NOT expose:

- stack traces;
- SQL text or database identifiers;
- cell/schema/cluster addresses;
- secret/token values;
- raw provider credentials;
- internal filesystem paths;
- sensitive policy rules that enable bypass;
- protected data belonging to another tenant;
- raw protected cursor/query values;
- competing values from rejected security-sensitive headers/trailers;
- raw malicious framing/body material beyond a safe diagnostic class.

Internal logs/traces may capture richer diagnostics only under accepted redaction/classification policy; URL/query confidentiality and rejected-ambiguity rules still apply.

## Observability contract

Every externally meaningful accepted request SHALL be correlatable to its owning use case and, where applicable, subsequent operation/job/provider work.

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

Transport-security telemetry may additionally record safe canonical-ingress rejection classes such as framing conflict, duplicate security header, authority conflict, invalid request target, method override rejection, security trailer rejection or content-coding conflict.

Observability fields never become a backdoor for secret/PII/confidential-query leakage. Route templates/operation IDs are preferred to raw URLs; protected cursor/search/filter text is represented only through accepted redacted/hash/reference forms. Rejected credentials/header values and malicious raw request bodies are not logged as convenience diagnostics.

## Health endpoints

Liveness/readiness/dependency health endpoints are operational contracts and SHALL distinguish process liveness from safe traffic readiness.

Detailed dependency/internal topology health is not exposed publicly by default. External health views use deliberately safe projections.

Health endpoints remain subject to canonical HTTP ingress; unauthenticated operational routes are not exempt from request-smuggling/framing defenses.