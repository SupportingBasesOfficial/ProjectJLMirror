# Phase 09 — OPEN Decisions

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

This file records intentionally unresolved Phase 09 details so they cannot be mistaken for omissions or silently decided in implementation.

An OPEN item remains unresolved until accepted through the appropriate contract/ADR/RFC/governance change. Implementation MAY prototype candidates, but a prototype does not become canonical by accident.

## OPEN-API-001 — Authentication/token profile

**Question:** Which concrete protocol/profile and credential transport are used for human API sessions, machine/API principals and internal service credentials where not already fixed by the accepted browser/BFF model?

**Already fixed:**

- first-party browser uses the BFF confidential session boundary;
- browser JS does not receive long-lived platform access/refresh credentials;
- machine credentials are independently revocable, attributable and tenant/permission scoped;
- protected direct realtime requires BFF-minted bounded connection capability plus current authorization before `101`.

**Must not be decided by:** an arbitrary framework default or one identity provider's native model.

## OPEN-API-002 — Browser session/CSRF/origin profile

**Question:** Exact cookie names/attributes across deployment topology, exact anti-CSRF token/header mechanism, and the concrete trusted browser Origin/CORS allowlist/credential profile for deployments that require cross-origin BFF access.

**Already fixed:**

- HttpOnly/confidential BFF boundary and explicit CSRF protection for state-changing cookie-authenticated browser requests;
- credentialed BFF access is deny-by-default for untrusted origins;
- any accepted cross-origin credentialed profile uses explicit trusted origins rather than wildcard credentialed access;
- CORS/Origin enforcement does not replace authentication, CSRF, tenant context or authorization.

## OPEN-API-003 — Realtime ticket presentation encoding

**Question:** Exact browser-compatible pre-upgrade ticket presentation mechanism for `/realtime/v1/connect`.

Candidates may include a narrowly reviewed/redacted query representation or another browser-compatible mechanism.

**Already fixed:** evidence is available before `101`; ambient cookie alone is insufficient; ticket is short-lived/single-use/scope-bound; expected Origin/current auth/replay continuity/atomic consume all happen before upgrade; ticket material is excluded from ordinary logs.

## OPEN-API-004 — Numeric request/page/bulk limits

**Question:** Concrete defaults/maxima for:

- JSON request body;
- idempotency-key transport length/character profile;
- per-endpoint strings/lists/nesting;
- collection `limit`;
- bulk item count;
- include/filter complexity;
- telemetry time windows;
- direct-query limits;
- import/export thresholds.

**Resolution evidence:** product usage model, abuse/security posture and benchmark/capacity evidence.

Unlimited values are not an accepted default while this remains OPEN.

## OPEN-API-005 — Idempotency retention windows

**Question:** Minimum claim/result retention by operation class.

**Already fixed:** retention must cover the documented client retry/replay/recovery window in which losing evidence could duplicate an effect. The API cannot advertise a longer safe retry window than durability supports.

One-time-secret material is never made replayable merely to satisfy this retention window; secret-bearing retry semantics follow the explicit non-replayable recovery contract.

## OPEN-API-006 — Deprecation/support duration

**Question:** Minimum support period for a deprecated major/contract element and policy differences by public API/BFF/provider/public projection.

**Already fixed:** normal supported contract elements are not removed casually inside a supported major; retirement is governed and instrumented.

## OPEN-API-007 — Exact media/content profiles for binary upload

**Question:** Multipart, resumable/chunked or dedicated staged-upload representation for large imports/attachments.

**Already fixed:** protected bytes have stable artifact/staging identity before unmanaged persistence can become undiscoverable; upload is bounded/reconcilable/governed and cannot bypass current tenant authorization. Uploader-supplied filename, extension or media type is untrusted metadata and cannot by itself authorize inline browser execution or define the authoritative delivery media type.

## OPEN-API-008 — Artifact range/download optimization

**Question:** Which artifact classes support HTTP range/resume/CDN acceleration and through which implementation mechanism.

**Already fixed:** every new/resumed release remains subject to current auth/releasability/delivery-generation admission, active-stream fencing and the artifact's accepted browser-delivery profile; optimization may not weaken prompt erasure or active-content isolation.

## OPEN-API-009 — Exact tracing propagation profile

**Question:** Which distributed trace propagation standard/headers are accepted at external/internal boundaries.

**Already fixed:** `request_id` and effective correlation are available; tracing context is never tenant/auth/idempotency authority and cannot leak secrets.

## OPEN-API-010 — Contract composition tooling

**Question:** Exact OpenAPI composition/lint/diff/code-generation toolchain.

**Already fixed:** reviewed contract is canonical; bundled machine-readable contract is reproducible; breaking-change CI exists; implementation DTO/ORM schema cannot silently become public truth.

## OPEN-API-011 — Public API SDK languages

**Question:** Which official SDKs, if any, are first-class and their release/support policy.

**Already fixed:** generated/official clients preserve opaque IDs/cursors/revisions, tolerate compatible response evolution and only auto-retry operations whose contract proves safety.

## OPEN-API-012 — Rate-limit representation

**Question:** Exact response headers/body metadata for quota/rate limit state and whether plan-specific limits are discoverable through management APIs.

**Already fixed:** throttling uses stable `429`/problem semantics where applicable; limits are enforceable by principal/tenant/route/integration/cost dimensions; Retry-After may be used when safe.

## OPEN-API-013 — Exact error problem media profile

**Question:** Whether the canonical problem representation is registered under a specific standard media type/profile or plain `application/json` with the same semantic fields.

**Already fixed:** stable machine-readable `code`, HTTP status, safe title/detail, request/correlation identity and bounded validation errors; no secret/topology leakage.

## OPEN-API-014 — Public projection resource detail

**Question:** Exact public status/resource families and schemas once Product scope for public projections is finalized.

**Already fixed:** public output is a deliberate projection, versioned separately and does not expose internal operational tables/protected tenant state by omission of auth.

## OPEN-API-015 — Direct SQL/query HTTP profile

**Question:** Exact request language, result pagination/streaming format and execution-resource representation for privileged direct query.

**Already fixed:** dedicated least privilege, trusted tenant binding not caller-mutable, read-only default, time/row/result bounds, immutable audit and no superuser/migration owner.

## OPEN-API-016 — Endpoint-specific contracts

The cross-cutting Phase 09 baseline does not itself finalize every domain endpoint/request/response schema.

Endpoint-level contracts are added incrementally using the canonical endpoint template and domain surface map. A future endpoint is allowed only when its Product/domain use case exists; the absence of an endpoint today does not require changing the cross-cutting contract architecture later.

## OPEN-API-017 — Response-cache tuning and exact header profiles

**Question:** Exact freshness durations, stale allowances, validator policy and optional cache-control header combinations for endpoints whose accepted semantic class is `private_revalidate`, `public_shared` or `artifact_delivery_guarded`.

**Already fixed:**

- every endpoint declares a cache class before implementation;
- secret-bearing responses are `no_store` and cannot be replayed from cache;
- protected API/BFF data cannot become shared-cacheable because of framework/CDN defaults;
- protected authentication/authorization/existence-concealing error variants cannot be shared across principals/tenants by default;
- `Vary` or caller-supplied tenant/principal metadata is not authorization;
- `public_shared` is limited to deliberately public projections independent of protected caller authority;
- protected artifact caching must preserve current authorization/releasability/delivery-generation/active-stream/browser-delivery fencing or remain non-shared.

**Resolution evidence:** Product freshness expectations, security classification, revocation/erasure semantics, traffic/capacity evidence and cache/CDN implementation proofs. Numeric TTLs are not invented in advance.

## OPEN-API-018 — Active browser artifact isolation profile

**Question:** If Product later requires inline rendering of browser-active/script-capable protected artifacts, what exact isolated hostname/origin, delegated delivery-capability representation, sandbox/content-security/navigation/opener/referrer/cross-origin header profile and browser integration are accepted?

**Already fixed:**

- authorization to download bytes does not authorize those bytes to execute in the application/BFF security origin;
- unknown/untrusted/browser-active content defaults to `opaque_download` with server-controlled media type, attachment behavior and `nosniff`-equivalent protection;
- uploader-supplied filename, extension or `Content-Type` cannot opt content into inline execution;
- `safe_inline` is restricted to explicitly accepted, independently classified browser-inert content classes;
- active-inline content requires an isolated untrusted-content browser boundary with no application/BFF ambient session cookies/credential authority and no application/BFF DOM/service-worker origin trust;
- any delegated capability remains bounded to the intended artifact/delivery generation and cannot become a general API credential;
- current artifact authorization, releasability, delivery-generation admission and active-stream erasure fencing remain mandatory.

**Resolution evidence:** concrete Product need for active inline rendering, browser threat model, content classes/formats, CSP/sandbox design, cookie/origin topology, delegated-delivery revocation proof and end-to-end stored-XSS/security tests.

No active-inline implementation may ship merely because an object store/CDN/browser can render the bytes while this profile remains unresolved.

## Not Phase 09 OPENs

The following remain outside Phase 09 and are not silently decided here:

- queue/cache/replay/pub-sub/event-broker vendor;
- broker acknowledgement/partition/transport mechanics — Phase 10;
- event/realtime message envelope — Phase 10;
- telemetry physical storage engine;
- object-storage vendor;
- secret manager/KMS vendor;
- cloud/orchestrator product;
- exact global ID generation algorithm;
- numeric SLO/RPO/RTO/latency/lag/revalidation targets;
- benchmark-driven topology/sizing/partition/rollup choices;
- supply-chain artifact signing/provenance policy deferred by TM-014;
- future service extraction decisions governed by ADR-020.

## Closure discipline

When an OPEN item is resolved, the accepting change SHALL:

1. document chosen semantics and rejected materially different alternatives where useful;
2. update affected Phase 09 docs/machine-readable schemas;
3. add/adjust contract tests;
4. identify compatibility/security implications;
5. use an ADR/RFC when the choice changes a higher-level accepted architecture/security decision;
6. remove or mark the OPEN item resolved rather than leaving contradictory prose.