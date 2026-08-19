# Canonical Endpoint Contract Template

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

Every externally consumed endpoint/use case SHALL be designed from this template or an equivalent machine-validated representation before implementation is considered contract-ready.

The template exists to prevent hidden assumptions from becoming permanent compatibility debt.

---

# `<operation_id>` — `<human title>`

## Contract metadata

```text
Status: proposed | accepted | deprecated | superseded
API surface: machine-api | bff | public | callback | realtime-admission
Major version: v1
Owner domain: <accepted bounded context>
Use case: <stable application use case>
Traceability: <FR-* / INV-* / SEC-* / QA-* / ADR-* / design sections>
```

## HTTP contract

```text
Method: GET | POST | PATCH | PUT | DELETE | HEAD
Path: /api/v1/...
Operation ID: <domain.actionResource>
Content-Type: application/json (or explicit alternative)
```

## Purpose

State the externally meaningful business/system behavior. Do not describe controller/service classes or SQL implementation.

## Actors

Allowed logical principal classes:

```text
human_browser_session
machine_api_principal
platform_admin_principal
internal_service_principal
scheduled/system_process
provider_callback_identity
```

State which are accepted and which are rejected.

For BFF/browser endpoints additionally declare:

```text
Credentialed cross-origin allowed: no | explicit allowlist only
Origin/CORS profile: <accepted profile or OPEN profile reference>
CSRF required for state change: yes | no/not applicable
```

Wildcard credentialed browser origins are prohibited. Origin/CORS enforcement is never authorization.

## Tenant/global scope

```text
Tenant requirement: none | required | explicit cross-tenant privileged
Tenant source: path | trusted integration mapping | platform operation target
Physical placement input from caller: prohibited
```

For tenant-scoped routes, document where trusted placement is resolved and where authoritative membership/resource authorization occurs. If membership/resource policy is cell-owned, placement resolution -> authoritative routing -> cell admission -> trusted TenantContext -> request-contract validation MUST precede the owning authorization decision. Earlier ingress/global checks are narrowing/fail-fast only.

Explain any legitimate global scope.

## Authorization

```text
Action: <domain.resource.verb>
Scope: platform | tenant | resource/group refinement
Step-up: none | policy-driven | required
Audit class: none | normal | privileged | security-critical
Existence concealment: yes | no | conditional
Owning authorization authority: <cell/domain/control-plane authority>
Authorization input fields: <validated path/query/body/resource identifiers consumed by policy>
```

Define any resource-level scope rules and distinguish ingress/global prechecks from the final owning authorization decision. Caller-controlled authorization/resource-scope inputs MUST be validated under the trusted route/TenantContext before the owning policy consumes them.

## Request

### Path parameters

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `tenant_id` | opaque string | yes/no | Logical tenant scope, never placement authority |

### Query parameters

Document allowlisted fields/operators, defaults and maximum complexity.

### Headers

Declare applicable headers:

```text
Idempotency-Key
If-Match
X-Correlation-Id
accepted authentication profile
content negotiation / range where applicable
```

### Body schema

Define typed request fields and semantics.

For each field specify:

- type/format;
- required/optional;
- nullable or not;
- bounds;
- enum open/closed classification;
- data classification;
- whether mutable/immutable;
- semantic validation.

Unknown request fields: rejected unless an explicit extension namespace is defined.

## Request limits

```text
Maximum body bytes: <value/policy>
Maximum item count: <value/policy>
Maximum string/list depth/size: <value/policy>
Timeout/deadline class: <policy>
Query complexity class: <policy>
```

If a numeric limit is not yet accepted, mark it `OPEN` rather than implying unlimited.

## Consistency

Choose/document:

```text
committed_authoritative
accepted_async
stale_tolerant_projection
historical_window
reconciliation_required_possible
```

Explain read-after-write expectations where material.

## Transaction/effect boundary

State:

- authoritative owner;
- local transaction scope;
- external effects, if any;
- outbox/audit obligations;
- whether a durable operation is created.

No external network call is assumed to be part of an ordinary local database transaction.

## Idempotency

```text
Class: none | optional | required | intrinsic
Effective server-derived scope: <description>
Fingerprint fields: <semantic request fields>
Completed replay behavior: <status/result>
In-progress duplicate behavior: <409 or same 202 operation>
Different-fingerprint behavior: 409 idempotency.key_reused
Retention/recovery window: <accepted policy or OPEN>
One-time-secret response: none | initial-presentation-only
Secret response-loss recovery: <not applicable | safe metadata + explicit rotate/reissue/create/revoke flow>
Surviving recovery authority: <not applicable | concrete still-valid authority/staged overlap/privileged recovery>
Credential cutover semantics: <not applicable | non-disruptive create | staged overlap | immediate with proven alternate authority>
```

For external effects, describe stable `operation_id` / reconciliation behavior.

If the endpoint creates/rotates/reissues non-retrievable secret material, document that the secret is excluded from idempotent replay state, a same-key response-loss retry cannot recreate the effect or re-present the secret, and the explicit authorized recovery action does not require possession of the lost secret. If the operation can invalidate an existing credential, prove which still-valid authority survives to recover or use a staged/overlap cutover; a nominal recovery endpoint without usable authority is insufficient.

## Optimistic concurrency

```text
Required: yes | no
Validator: ETag / opaque revision
If-Match required: yes | no
Missing precondition: 428 concurrency.precondition_required
Mismatch: 412 concurrency.revision_mismatch
```

Explain why concurrency is or is not required.

## Success responses

List every normal success status and schema.

Example:

```text
201 Created -> <Resource>
202 Accepted -> <Operation>
204 No Content -> no body
```

Define `Location` behavior when applicable.

For a secret-bearing success, explicitly identify the one-time secret field(s), response cache class `no_store`, logging/redaction restrictions and response-loss behavior.

For any endpoint that uploads, returns, previews, streams or delegates artifact/binary bytes, additionally declare:

```text
Browser delivery applicable: yes | no
Browser delivery profile: opaque_download | safe_inline | active_inline_isolated | not_applicable
Authoritative media-type source: <server-controlled validation/classification policy>
Caller filename/extension/Content-Type trusted for browser execution: no
Content-Disposition: attachment | inline only under accepted profile
MIME sniffing: prohibited / nosniff-equivalent
Active-content origin isolation: required | not applicable
Ambient application/BFF credentials on active-content origin: prohibited | not applicable
Delegated delivery capability scope: <artifact/delivery-generation bound or not applicable>
Untrusted server-side content processing: none | isolated_bounded
Processing boundary: <isolated parser/renderer/worker profile or not applicable>
Processing secret access: none | narrowly scoped explicit capability
Processing egress: denied/restricted under accepted outbound policy
Expansion/resource limits: <bytes/nesting/members/CPU/memory/time/output policy or OPEN with implementation blocked>
Embedded macro/script execution: prohibited unless separately accepted
Embedded URL retrieval: prohibited except through accepted outbound/SSRF policy
Derived artifact classification: independent required | not applicable
```

Unknown/untrusted/browser-active content defaults to `opaque_download`. A caller-controlled upload media type, filename or extension never authorizes inline execution. `active_inline_isolated` requires a dedicated untrusted-content browser boundary with no application/BFF ambient credential or DOM/service-worker trust and must preserve current authorization/releasability/delivery-generation/active-stream fencing.

Complex document/archive/media parsing, preview, conversion, extraction or rendering of untrusted bytes uses an isolated least-privilege bounded processing profile. It SHALL NOT run with ordinary API/BFF application secrets or unrestricted egress merely because the uploader is authorized. Archive/decompression expansion, recursion, CPU/memory/time and generated-output volume are bounded. A derived preview/conversion receives independent artifact identity/classification and does not inherit `safe_inline` automatically.

## Response cache contract

Every endpoint MUST choose a cache class:

```text
Class: no_store | private_revalidate | public_shared | artifact_delivery_guarded
Shared cache allowed: yes | no | only with proven guarded delivery
Variance dimensions: <public-safe dimensions or none>
Validator/revalidation: <ETag/conditional/none/policy>
Freshness/TTL: <accepted value/policy or OPEN>
Authorization re-evaluation before reuse: <required/not applicable>
Sensitive response fields: <none/list>
Protected error variants: <no_store/private policy>
```

Rules:

- the cache contract applies to success and error/conditional response variants;
- secret-bearing responses are always `no_store`;
- protected authentication/authorization/existence-concealing errors cannot become shared-cacheable by default;
- protected API/BFF responses cannot become shared-cacheable from framework/CDN defaults;
- `Vary` or equivalent keying is not authorization;
- `public_shared` requires a deliberately public projection independent of protected caller authority;
- protected artifact caching must preserve current authorization/releasability/delivery-generation/active-stream fencing and browser-delivery profile or fall back to non-shared behavior.

Exact public/private lifetime tuning may remain `OPEN-API-017`; absence of an accepted cache contract blocks implementation.

## Error contract

List stable problem codes that callers may branch on.

Minimum classes considered:

```text
authentication.*
authorization.*
resource.not_found
validation.*
concurrency.*
idempotency.*
secret.delivery_not_replayable
rate_limit.*
dependency.*
domain-specific conflicts
```

Do not expose raw database/provider exception text.

## Retry contract

State:

```text
Automatic retry safe: yes | no | only with valid idempotency key
Safe statuses/classes: <documented>
Ambiguous external outcome: <operation/reconciliation behavior>
One-time-secret response loss: <not applicable | explicit non-replayable recovery>
Retry-After: may/shall/not used
```

## Long-running operation

If applicable:

```text
Operation type: <name>
Operation URI: /api/v1/.../operations/{operation_id}
Cancellation supported: yes/no
Terminal states: <subset>
Result resource: <type/reference>
Operation read authority: <current action/scope>
Cancel/retry/resume authority: <current action/scope>
Result dereference authority: <current target-resource action/scope>
```

`operation_id`/URL is never bearer authority. Poll/cancel/retry/resume/result access re-establishes current tenant/principal/resource authorization.

## Pagination/filter/sort

For collection endpoints:

```text
Default sort: <deterministic order>
Cursor mode: live | snapshot-like | historical-window
Allowed filters: ...
Allowed sorts: ...
Allowed includes: ...
Default limit: <value/policy>
Maximum limit: <value/policy>
Total count: absent | exact | approximate | optional
Current authorization re-evaluated on each page: yes
Cursor security binding: <tenant/query/sort plus any needed principal/scope dimensions>
```

A cursor/snapshot/watermark never freezes authorization. Each protected continuation request re-establishes current authority, and included/bulk items remain independently authorized where required.

## Data classification

Classify request/response fields:

```text
public
internal
confidential
restricted/credential
regulated/PII where applicable
```

Declare redaction/logging restrictions.

## Audit

State:

- audit required or not;
- actor/tenant/action/resource/outcome fields;
- whether audit record/intent must commit atomically with mutation;
- high-risk reason/approval/step-up metadata where applicable.

## Observability

Declare:

```text
request_id required
correlation_id propagation
operation_id linkage
tenant-safe metrics/log dimensions
provider/external-call linkage where applicable
```

No secrets in observability payloads.

## Compatibility classification

Classify externally important fields/enums and security/behavior policy dimensions. Document:

- open/closed enum behavior;
- additive evolution options;
- known future extension points;
- deprecated aliases, if any;
- what would require a new major;
- whether changing authorization/scope/idempotency/retry/consistency semantics is breaking;
- whether changing response cache class, shared-cache eligibility, variance or current-authorization revalidation is breaking/security-sensitive;
- whether changing browser-delivery/media-type/active-content-isolation or untrusted-content-processing semantics is security-sensitive or breaking for supported clients.

A cache, artifact browser-delivery or untrusted-content-processing policy becoming more permissive is never treated as an implementation-only optimization.

## Security abuse cases

List relevant abuse/failure cases such as:

- wrong tenant ID;
- known resource ID from another tenant;
- authorization attempted against stale/wrong cell placement;
- authorization consuming unvalidated caller-controlled resource/scope fields;
- revoked principal;
- stale revision;
- duplicate idempotency key;
- lost one-time-secret response;
- secret rotation with no surviving recovery authority;
- shared-cache cross-principal/tenant leakage;
- protected error cache leakage;
- stale cursor after authority revocation;
- operation ID used as bearer authority;
- wildcard/untrusted credentialed BFF origin;
- browser-active artifact executing on application/BFF origin;
- forged upload media type/filename causing inline execution or header injection;
- malicious archive/document causing parser RCE, SSRF or expansion/resource exhaustion;
- generated preview incorrectly trusted as safe inline content;
- oversized body;
- expensive filter/include abuse;
- replayed callback/ticket;
- callback-supplied SSRF target;
- provider outage;
- cross-tenant existence probing.

## Contract tests

List mandatory tests including happy path and invariant/fault cases.

At minimum, protected mutation endpoints test:

- authorized success;
- unauthenticated denial;
- wrong-tenant denial;
- authoritative placement/routing + trusted request-contract validation before cell-owned authorization where applicable;
- authorization policy does not consume unvalidated caller-controlled scope/resource fields;
- insufficient permission;
- validation bounds;
- idempotency/concurrency where applicable;
- one-time-secret response-loss behavior where applicable;
- lockout-safe surviving recovery authority/cutover where secret rotation can invalidate existing authority;
- response-cache headers/semantics and cross-principal/tenant non-reuse, including protected error variants;
- compatibility tests for cache-policy changes;
- current authorization on pagination/operation continuation where applicable;
- BFF origin/CORS/CSRF behavior where applicable;
- callback outbound-fetch/SSRF boundary where applicable;
- audit/operation linkage;
- safe error leakage;
- retry after response loss where applicable.

Artifact/binary endpoints additionally test, where applicable:

- uploader-controlled filename/extension/media type cannot force executable inline delivery;
- unknown/untrusted/browser-active content falls back to attachment/non-sniffable download semantics;
- safely encoded filename metadata cannot inject response headers;
- `safe_inline` accepts only the explicitly allowlisted validated content classes;
- `active_inline_isolated` does not receive application/BFF ambient credentials or origin/service-worker trust;
- delegated active-content delivery remains bound to the intended artifact/delivery generation and cannot become a general API credential;
- range/resume/CDN paths preserve the same browser-delivery classification and current artifact fencing;
- malicious archive/document expansion is bounded and cannot consume unbounded CPU/memory/time/output;
- parser/renderer processing cannot access ordinary application secrets or unrestricted network destinations;
- embedded scripts/macros/URLs are not executed/fetched implicitly;
- derived preview/conversion output is independently identified/classified before inline delivery.

## OPEN items

Explicitly list unresolved items. An omitted decision is not silently considered accepted.

## Evolution notes

Explain how this contract remains stable if:

- the domain is extracted into a service;
- tenant moves cells/regions;
- storage engine changes;
- provider adapter changes;
- client types multiply;
- request volume/cardinality grows substantially;
- a CDN/reverse proxy/cache layer is added or replaced;
- artifact delivery moves to a dedicated untrusted-content origin or another equivalent browser-isolation mechanism;
- artifact parsing/preview/conversion moves to a different isolated runtime or vendor without changing external artifact identity/contract.