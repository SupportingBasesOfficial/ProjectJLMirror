# Collections, Filtering, Pagination and Bulk

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Collection contracts are designed for large cardinality from the beginning. A list endpoint SHALL NOT rely on assumptions such as "this tenant will only ever have a few hundred rows" unless the product contract actually enforces that bound.

## Default collection shape

Paginated collections return:

```json
{
  "items": [],
  "next_cursor": "opaque-or-null"
}
```

`next_cursor` is `null` or absent according to the endpoint schema when no next page exists. The contract SHALL choose one representation consistently.

Optional collection metadata MAY include:

```json
{
  "has_more": true
}
```

when it can be provided without extra expensive counting.

## No total count by default

`total_count` is not part of the default collection contract because exact counts can become disproportionately expensive under large/filtered/high-write datasets.

An endpoint MAY expose total count only when:

- the product truly needs it;
- the ownership/query model can support it safely;
- the consistency meaning of the count is documented;
- its cost is bounded or separately projected.

Approximate counts are explicitly labeled approximate.

## Pagination request

Canonical request parameters are:

```text
limit=<positive integer>
cursor=<opaque value>
```

Every collection endpoint defines:

- default `limit`;
- maximum `limit`;
- stable default sort;
- cursor binding semantics;
- whether historical snapshot consistency is promised.

Clients MUST NOT assume the maximum page size is the same across all resource families.

## Cursor requirements

A cursor is opaque. Clients store/pass it unchanged and SHALL NOT parse or modify it.

The server-issued cursor binds enough context to prevent it from being safely reused under incompatible query semantics, including as applicable:

- API major/endpoint contract;
- tenant/global scope;
- effective sort;
- filter/search shape;
- projection/query version;
- deterministic last-item key;
- expiration/version where the endpoint requires it.

Cursor opacity is a client-compatibility property, **not** a confidentiality guarantee. A cursor carried in a URL/query parameter SHALL NOT expose confidential/restricted tenant data, protected search terms, raw resource keys, credentials, provider secrets, physical placement, or sensitive internal topology merely because the token is encoded or signed.

If the cursor needs to bind protected state that would be unsafe to expose through URL/history/log/referrer surfaces, the implementation SHALL use one of the following accepted properties:

- a server-side opaque handle whose exposed value reveals no protected payload;
- a self-contained envelope providing confidentiality and integrity for the protected cursor payload;
- or another reviewed mechanism with equivalent confidentiality, tamper resistance, scope binding and revocation/expiry behavior.

Encoding/base64/signing without confidentiality is insufficient when the payload contains protected data.

Raw cursor values are security-sensitive URL material. Normal access logs, analytics, traces, referrers and support telemetry SHALL NOT record full protected cursor values by default; use redaction, hashing/reference or another accepted safe representation. A cursor SHALL NOT be copied into third-party URLs or redirect targets.

The server MAY encode/sign/encrypt cursors internally or use server-side state. Exact mechanism is implementation-specific as long as callers cannot use the cursor to weaken authorization, inject arbitrary database ordering/filter state, or recover protected payload data from URL-visible material.

A valid cursor is **not authorization**. Every page request re-establishes the current principal/session/credential state, tenant context and applicable membership/permission/resource scope before returning protected items. Revocation, tenant suspension, scope reduction or relocation between pages SHALL NOT remain bypassable merely because the caller holds an older valid cursor.

Cursor binding MAY include principal/security-scope dimensions when an endpoint needs them to prevent unsafe replay, but such binding never replaces current authorization re-evaluation.

## URL/query confidentiality

Filter/search/query values are also exposed transport metadata when carried in a URL. An endpoint SHALL classify whether its accepted query parameters may contain confidential/restricted values.

If a normal use case can require confidential search/filter input, the contract SHALL use a representation that does not depend on placing that protected input in browser/history/referrer/log-visible URL text, for example a bounded body-based query contract or a server-side opaque query handle. Exact representation is endpoint-specific.

Public/non-sensitive query parameters MAY remain in the URL, but logs/analytics still follow the endpoint data-classification policy. Sensitive query state is never considered safe merely because HTTPS encrypts the network hop.

## Stable ordering

Every cursor-paginated endpoint has a deterministic ordering with a stable tie-breaker.

Example logical ordering:

```text
updated_at DESC, id DESC
```

The exact fields depend on the resource/query contract. A non-deterministic sort is not acceptable for cursor pagination.

## Concurrent mutation semantics

Collection contracts SHALL state whether pagination is:

- **live traversal** — newly inserted/updated rows may appear/move between pages under deterministic cursor rules;
- **snapshot-like** — a stable query snapshot/version is maintained for the paging window;
- **historical window** — query is bounded by explicit time/watermark.

The default does not promise database transaction snapshot isolation across multiple HTTP requests.

Clients must not assume a multi-page traversal is a perfectly frozen dataset unless the endpoint explicitly promises it.

A snapshot-like data view, when provided, freezes query-data semantics only to the documented extent; it does not freeze authorization. Each page still requires current authority.

## Offset pagination

Offset/page-number pagination MAY be offered for small bounded administrative projections, but it is not the default for large mutable operational collections.

An endpoint using offset semantics documents cardinality/cost bounds and may later require a new endpoint/version if those assumptions stop being valid.

## Filtering

Filters are allowlisted per endpoint. Canonical simple filter syntax is:

```text
filter[field]=value
filter[field]=value1,value2
```

An endpoint contract defines each allowed operator/value syntax. The API SHALL NOT translate arbitrary client field names/operators directly into SQL.

Advanced filter expressions, if introduced later, require their own bounded grammar, authorization review, complexity limits and compatibility contract.

Filter values follow the URL/query confidentiality rule above. A protected value SHALL NOT be forced into a URL solely because the simple filter syntax supports it.

## Search

Free-text/fuzzy search uses an explicit parameter such as:

```text
q=<text>
```

Search semantics are endpoint-specific and SHOULD declare whether results are exact, prefix, token, fuzzy or provider-backed.

Search ranking is not treated as stable ordering unless the contract explicitly defines a stable rank/tie-break behavior.

If search text may contain confidential customer/tenant data, credentials, secrets, regulated values or other protected content, the endpoint SHALL NOT require that value in a URL-visible `q` parameter. It uses an accepted non-URL-sensitive query representation instead.

## Sorting

Canonical sort syntax:

```text
sort=field,-other_field
```

Ascending is the default; `-` indicates descending.

Sortable fields are allowlisted. Unknown/unsupported sort fields are rejected rather than ignored.

The server SHALL add a deterministic tie-breaker internally when the requested sort is not unique.

## Includes/expansions

Related-resource expansion uses an allowlisted parameter such as:

```text
include=assignee,service
```

Includes are bounded and explicitly costed. They SHALL NOT provide arbitrary graph traversal or bypass ownership/authorization boundaries.

An included resource is authorized independently as required. A caller authorized to read an incident does not automatically gain access to every referenced protected object.

## Sparse fields

Sparse fieldsets MAY be introduced for high-volume/read-sensitive endpoints when they provide measurable value. They are not assumed globally.

If supported, the endpoint uses an allowlisted schema and does not permit requesting hidden/unauthorized fields by name.

## Historical telemetry queries

High-volume telemetry/history endpoints SHALL require bounded query dimensions such as time range and resource/metric scope.

An unbounded "return all history" contract is prohibited.

The endpoint defines maximum time span/result volume or an asynchronous export path for larger requests.

Historical pagination identity remains based on platform-owned resource/observation semantics and SHALL NOT expose physical telemetry partitions or confidential cursor payload data.

Current authorization is re-evaluated for each historical page/export admission; possession of an old cursor/watermark does not preserve access after revocation or scope reduction.

## Bulk reads

Bulk lookup endpoints MAY accept bounded sets of stable IDs when they materially reduce N+1 behavior.

They declare:

- maximum IDs per request;
- input ordering behavior;
- duplicate input behavior;
- missing/unauthorized item behavior;
- output ordering guarantees;
- whether existence concealment is required.

Every item/result remains subject to current tenant/resource authorization. Batch membership does not turn one authorized ID into authority over neighboring requested IDs.

A bulk read SHALL NOT become an unbounded arbitrary-query API.

## Bulk mutations

Bulk mutations are explicit endpoints/contracts, not repeated single-resource JSON embedded under a generic endpoint without semantics.

A bulk mutation declares one of:

```text
atomic_all_or_nothing
per_item_independent
durable_operation
```

`atomic_all_or_nothing` is allowed only when the entire batch belongs to one authoritative transaction boundary and is safely bounded.

Large, cross-domain, external-effect or long-running bulk work uses a durable operation.

Authorization scope for the batch is explicit. A bulk mutation SHALL NOT partially apply unauthorized items unless the endpoint's accepted per-item semantics intentionally permit mixed authorization outcomes without leaking protected existence.

## Per-item result shape

Per-item independent bulk operations return stable item correlation such as:

```json
{
  "items": [
    {
      "client_ref": "caller-opaque-ref",
      "status": "succeeded",
      "resource_id": "res_..."
    },
    {
      "client_ref": "another-ref",
      "status": "failed",
      "error": {
        "code": "validation.semantic_conflict"
      }
    }
  ]
}
```

The endpoint defines whether `client_ref` is required and how per-item idempotency is established.

Where existence concealment applies, per-item error shape SHALL NOT reveal which foreign-tenant resource IDs exist.

## Imports instead of giant bulk payloads

When data volume exceeds normal HTTP/bulk bounds, the platform uses the governed import/process/artifact contract rather than increasing body/page limits indefinitely.

Import parsing/validation and eventual protected mutation remain subject to current execution-time authorization and resource controls.

## Export instead of giant list traversal

When a consumer needs a very large coherent dataset, the API SHOULD expose an asynchronous export/report artifact contract rather than encouraging millions of paginated interactive calls.

The export remains authorization-, retention- and artifact-governance-aware.

## Query complexity as a resource

The platform MAY enforce query complexity budgets based on filter count, include depth, time range, groupings or other cost dimensions.

A rejected query returns a stable error explaining the supported bound at a safe level; it does not expose query plans or database internals.

## Future index/storage evolution

Changing from PostgreSQL query execution to a read model, search engine, columnar store or extracted service SHALL NOT require changing the collection contract when externally meaningful filtering/sorting/pagination semantics remain equivalent.