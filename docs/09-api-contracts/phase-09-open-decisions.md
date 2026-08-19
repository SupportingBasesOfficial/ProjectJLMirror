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

## OPEN-API-002 — Browser session/CSRF profile

**Question:** Exact cookie names/attributes across deployment topology and the exact anti-CSRF token/header mechanism.

**Already fixed:** HttpOnly/confidential BFF boundary and explicit CSRF protection for state-changing cookie-authenticated browser requests.

## OPEN-API-003 — Realtime ticket presentation encoding

**Question:** Exact browser-compatible pre-upgrade ticket presentation mechanism for `/realtime/v1/connect`.

Candidates may include a narrowly reviewed/redacted query representation or another browser-compatible mechanism.

**Already fixed:** evidence is available before `101`; ambient cookie alone is insufficient; ticket is short-lived/single-use/scope-bound; expected Origin/current auth/replay continuity/atomic consume all happen before upgrade; ticket material is excluded from ordinary logs.

## OPEN-API-004 — Numeric request/page/bulk limits

**Question:** Concrete defaults/maxima for:

- JSON request body;
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

## OPEN-API-006 — Deprecation/support duration

**Question:** Minimum support period for a deprecated major/contract element and policy differences by public API/BFF/provider/public projection.

**Already fixed:** normal supported contract elements are not removed casually inside a supported major; retirement is governed and instrumented.

## OPEN-API-007 — Exact media/content profiles for binary upload

**Question:** Multipart, resumable/chunked or dedicated staged-upload representation for large imports/attachments.

**Already fixed:** protected bytes have stable artifact/staging identity before unmanaged persistence can become undiscoverable; upload is bounded/reconcilable/governed and cannot bypass current tenant authorization.

## OPEN-API-008 — Artifact range/download optimization

**Question:** Which artifact classes support HTTP range/resume/CDN acceleration and through which implementation mechanism.

**Already fixed:** every new/resumed release remains subject to current auth/releasability/delivery-generation admission; implementation may not weaken prompt erasure/active-stream fencing.

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