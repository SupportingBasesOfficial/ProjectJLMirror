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

## Tenant/global scope

```text
Tenant requirement: none | required | explicit cross-tenant privileged
Tenant source: path | trusted integration mapping | platform operation target
Physical placement input from caller: prohibited
```

For tenant-scoped routes, document where trusted placement is resolved and where authoritative membership/resource authorization occurs. If membership/resource policy is cell-owned, placement resolution -> authoritative routing -> cell admission -> trusted TenantContext MUST precede the owning authorization decision. Earlier ingress/global checks are narrowing/fail-fast only.

Explain any legitimate global scope.

## Authorization

```text
Action: <domain.resource.verb>
Scope: platform | tenant | resource/group refinement
Step-up: none | policy-driven | required
Audit class: none | normal | privileged | security-critical
Existence concealment: yes | no | conditional
Owning authorization authority: <cell/domain/control-plane authority>
```

Define any resource-level scope rules and distinguish ingress/global prechecks from the final owning authorization decision.

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
Secret response-loss recovery: <not applicable | safe metadata + explicit rotate/reissue/revoke flow>
```

For external effects, describe stable `operation_id` / reconciliation behavior.

If the endpoint creates/rotates/reissues non-retrievable secret material, document that the secret is excluded from idempotent replay state, a same-key response-loss retry cannot recreate the effect or re-present the secret, and the explicit authorized recovery action does not require possession of the lost secret.

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
```

Rules:

- secret-bearing responses are always `no_store`;
- protected API/BFF responses cannot become shared-cacheable from framework/CDN defaults;
- `Vary` or equivalent keying is not authorization;
- `public_shared` requires a deliberately public projection independent of protected caller authority;
- protected artifact caching must preserve current authorization/releasability/delivery-generation/active-stream fencing or fall back to non-shared behavior.

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
```

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
```

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

Classify externally important fields/enums as open/closed and document:

- additive evolution options;
- known future extension points;
- deprecated aliases, if any;
- what would require a new major.

## Security abuse cases

List relevant abuse/failure cases such as:

- wrong tenant ID;
- known resource ID from another tenant;
- authorization attempted against stale/wrong cell placement;
- revoked principal;
- stale revision;
- duplicate idempotency key;
- lost one-time-secret response;
- shared-cache cross-principal/tenant leakage;
- oversized body;
- expensive filter/include abuse;
- replayed callback/ticket;
- provider outage;
- cross-tenant existence probing.

## Contract tests

List mandatory tests including happy path and invariant/fault cases.

At minimum, protected mutation endpoints test:

- authorized success;
- unauthenticated denial;
- wrong-tenant denial;
- authoritative placement/routing before cell-owned authorization where applicable;
- insufficient permission;
- validation bounds;
- idempotency/concurrency where applicable;
- one-time-secret response-loss behavior where applicable;
- response-cache headers/semantics and cross-principal/tenant non-reuse;
- audit/operation linkage;
- safe error leakage;
- retry after response loss where applicable.

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
- a CDN/reverse proxy/cache layer is added or replaced.