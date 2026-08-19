# API & Contracts Overview

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts  
**Depends on:** accepted Product/Requirements/Security/Architecture/ADR/System Design/Data Architecture baseline

## Purpose

This phase defines the stable external and boundary-facing contract model through which JLMIRROR capabilities are consumed. It translates accepted domain, security, runtime and data invariants into HTTP/browser/realtime-admission representations without making transport models the owner of business semantics.

The contract baseline is designed for the platform's maximum intended evolution: new bounded contexts, new providers, new storage engines, dedicated cells, service extraction, new clients and substantially larger scale SHALL be able to appear without forcing existing consumers to understand physical placement, database schemas, provider-native models or internal process topology.

The objective is not to pre-implement every future capability. The objective is to ensure that capabilities implemented later fit an already coherent contract system rather than creating one-off APIs that become structural debt.

## Contract surfaces

JLMIRROR distinguishes these surfaces because their trust, compatibility and lifecycle requirements differ:

1. **Platform/Public Machine API** — versioned HTTP API for authorized external machine principals and approved integrations.
2. **First-party Browser BFF API** — browser-facing confidential-session boundary. It may compose platform use cases for the Web client but SHALL NOT become a second business domain.
3. **Protected Realtime Admission** — BFF-mediated capability minting plus direct protected WebSocket admission under accepted Origin/current-authorization/replay rules. Phase 09 owns admission representation; Phase 10 owns asynchronous message/event envelope mechanics.
4. **Provider Callback Ingress** — adapter-owned inbound HTTP contracts subject to provider-specific authentication plus accepted raw-body, authenticated-freshness, canonical-entity, atomic durable replay, recovery-continuity, tenant-binding and SSRF/parser rules.
5. **Public Projection API** — deliberately public/versioned projections such as public status output; it never exposes internal tables or protected tenant resources by default.
6. **Internal Service/Application Contracts** — typed application contracts that may later cross process boundaries. HTTP is not required merely because an internal module has an explicit contract.

A surface MAY share domain schemas or generated types with another surface when semantics are genuinely identical, but shared implementation SHALL NOT erase the trust boundary between surfaces.

All externally reachable HTTP surfaces additionally inherit `http-message-framing-and-canonicalization.md`: an accepted wire request must have one canonical framing/header/authority/request-target interpretation before authentication, routing, idempotency, cache decisions or protected effects.

## Normative design goals

### Contract stability over implementation stability

Public contract identity SHALL remain independent of:

- PostgreSQL table/schema names;
- ORM entities;
- provider-native identifiers and payloads;
- cell/database/cluster placement;
- queue/cache/pub-sub vendor;
- gateway/reverse-proxy product or HTTP runtime;
- monolith versus extracted service placement;
- internal class/module/file names;
- object-storage paths or signed-URL vendor formats.

An internal implementation may change without a public breaking change when the externally meaningful semantics remain equivalent.

### Explicit ownership

Every protected operation SHALL name one owning bounded context/application capability. A transport route does not gain permission to mutate multiple domain owners directly simply because the client wants one screen to update several things.

Cross-domain orchestration is represented by an owning use case/process contract, not by exposing distributed storage coupling to the caller.

### Canonical HTTP message interpretation

HTTP transport is not trusted to be unambiguous merely because a framework produced a request object.

Before an externally received HTTP request can influence authentication, BFF session/CSRF handling, tenant routing, idempotency admission, cache selection, callback verification, realtime `101` admission or a protected use case, the accepted ingress establishes one canonical request interpretation according to `http-message-framing-and-canonicalization.md`.

The baseline therefore requires:

- fail-closed ambiguous body framing;
- explicit security-sensitive header cardinality/combine semantics;
- one trusted authority/host/proxy-metadata interpretation;
- one canonical request target consumed consistently by routing/authorization/cache/owning service;
- safe HTTP-version translation that reconstructs from canonical semantics rather than forwarding incompatible framing metadata;
- downstream propagation of only the normalized request meaning.

Exact gateway/proxy/runtime products remain replaceable.

### Canonical structured request entity

Transport framing proves which bytes belong to a request; it does not permit each protected component to choose its own interpretation of structured body fields.

For JSON, multipart, XML and any other accepted structured request media type, the contract establishes one bounded canonical parsed entity before protected body fields are consumed by request validation, owning authorization, idempotency fingerprinting, body-carried callback replay/freshness identity or use-case/domain mapping.

Duplicate/alias member names, multipart part-name/metadata/boundary ambiguity and equivalent parser disagreement fail closed under the accepted media-type profile. Retained raw bytes may remain necessary for provider signatures or audit evidence, but after canonical entity establishment they are not independently reparsed as a second semantic authority.

Changing parser/library/runtime is implementation evolution only if the same accepted raw request still produces the same canonical entity and all protected consumers continue to observe that one entity.

### Explicit tenant semantics

Every tenant-scoped contract SHALL carry an unambiguous logical `tenant_id` through its contract scope. A caller may identify the logical tenant it intends to operate on, but that value is never authority for physical placement and never bypasses membership/authorization.

When membership/resource policy is cell-owned, the contract preserves the accepted lifecycle: canonical HTTP ingress -> authentication -> logical tenant -> trusted placement -> authoritative route/cell admission -> trusted `TenantContext` -> request-contract validation -> owning authorization -> use case. Caller-controlled request fields are never promoted into trusted authorization/resource scope before validation under that context.

### Explicit retry semantics

Every effectful contract SHALL classify whether client retry is:

- inherently safe;
- safe only with the Phase 09 idempotency contract;
- unsafe without first resolving an operation resource;
- prohibited because a new business decision is required.

"Client can retry on timeout" is never an undocumented assumption.

One-time secret creation/rotation additionally declares non-replayable secret-delivery recovery and proves a surviving recovery authority or staged cutover when an existing credential could be invalidated.

### Explicit recovery continuity

Retry/dedup safety must survive recovery, not only ordinary runtime concurrency.

Idempotency, callback replay and realtime single-use authority inherit the accepted Gate B recovery principle: after restore/PITR/partial loss, **missing or older local replay state is not proof that an operation/event/capability was never used**. A restored authority remains quarantined/fail-closed until the applicable `(R,F]` continuity interval is reconciled against surviving operation/outcome/inbox/outbox/audit/provider/external-effect/security authorities.

The contract therefore preserves:

```text
uncertainty != absence
recovered missing state != never executed
restore/PITR != retry permission
```

Exact backup vendor, replay/idempotency store, generation/epoch representation and recovery topology remain implementation/Data Architecture choices. The fail-closed continuity property is part of the API/ingress contract because it determines whether a repeated request or callback may create another logical executor/effect after recovery.

### Explicit callback freshness and replay durability

Provider callback authenticity, freshness, replay admission and durable responsibility form one security/correctness chain.

For every callback profile:

- freshness evidence used for security is bound to the authenticated callback body/identity by the accepted authenticator or comes from independently trusted protocol metadata associated with the same callback;
- a clock-window check alone cannot make unbound metadata authoritative;
- body-carried freshness and replay identity come from the same canonical entity consumed by domain mapping;
- replay identity is scoped by trusted tenant/integration/source dimensions;
- replay admission is atomic create-or-observe and yields one logical executor under concurrent delivery;
- replay admission is coupled to durable inbox/work/effect responsibility, or cross-authority ambiguity enters durable reconciliation before another execution may be admitted;
- replay restore/PITR/partial loss cannot turn missing/older replay state into unused identity; a still-fresh authenticated retry remains blocked while recovery continuity is unresolved;
- success acknowledgement never outruns durable responsibility;
- retention expiry does not make unresolved ambiguous irreversible work blindly executable again.

Exact provider authenticator, signed-header set, numeric freshness window, replay storage product, transaction topology and reconciliation implementation remain `OPEN-API-022` until evidence accepts them.

### Explicit consistency semantics

Every operation SHALL identify whether its response represents:

- committed authoritative state;
- accepted durable asynchronous work;
- a stale-tolerant/derived projection;
- a reconciliation/ambiguous outcome requiring operation tracking.

A `2xx` response does not silently mean more consistency than the owning use case can prove.

### Explicit response-header semantics

Response headers are part of the contract/security boundary rather than string-formatted implementation decoration.

Every endpoint inherits or declares a `response_header_profile` and one serialization/composition owner model for dynamic/security-relevant headers such as `Location`, `Link`, `ETag`, `Retry-After`, `Content-Disposition`, redirects, cache/security/CORS/authentication headers and request/correlation IDs.

The profile defines bounded grammar/cardinality/serialization behavior and prevents CR/LF/NUL/control injection, obsolete folding, conflicting singleton output and app/BFF/proxy/CDN layers from independently appending security-relevant values with different meanings.

A response-header serialization failure after an authoritative mutation committed does not make the business operation retryable. Idempotency, durable operation state or authoritative read/recovery semantics determine the outcome.

### Explicit cache semantics

Every endpoint SHALL declare whether its responses are `no_store`, `private_revalidate`, `public_shared` or `artifact_delivery_guarded`, including shared-cache eligibility, variance/revalidation/current-auth behavior and security-relevant compatibility semantics.

Framework, reverse-proxy and CDN defaults SHALL NOT silently make a protected response more cache-permissive than the accepted contract.

A cache/proxy cannot key or accept a request under an interpretation different from the canonical request consumed by the owning service.

### Explicit artifact browser-execution and processing semantics

Authorization to access protected artifact bytes SHALL NOT implicitly authorize those bytes to execute within the first-party application/BFF browser security origin.

Browser-reachable artifact contracts declare a server-controlled media classification and browser-delivery profile. Unknown, untrusted or browser-active/script-capable content fails toward non-executable download behavior. Inline browser-active rendering requires a separately accepted isolated untrusted-content boundary that does not share application/BFF ambient credential or origin/service-worker trust and still preserves current artifact authorization/releasability/delivery fencing.

Complex parsing, archive expansion, preview generation, conversion or metadata extraction of untrusted bytes is a separate processing trust boundary. Such work is isolated and bounded when it exists; upload authorization or successful persistence does not make document/media parsers safe to run with ordinary application secrets or unrestricted egress.

## Initial URI namespaces

The proposed major-version namespaces are:

```text
/api/v1/...       versioned machine/platform API
/bff/v1/...       first-party browser BFF contract
/realtime/v1/...  protected realtime handshake/admission endpoint
/public/v1/...    deliberate unauthenticated/public projections
/callbacks/v1/... provider/integration callback adapters where a generic prefix is applicable
```

Exact hostnames/deployment routing remain infrastructure choices. URI paths never encode cell, database, shard, region-internal host, provider secret or other physical placement authority.

URI/request-target interpretation is canonical per surface; edge and owning service cannot independently normalize one wire target into different logical routes/resources.

## API major version

`v1` is the first externally supported major contract family. Compatible additive evolution occurs within a major version under the compatibility rules in this phase. Breaking semantic changes require a new major contract or another explicitly accepted compatibility mechanism.

Major API version is a contract version, not a deployment version. Multiple application releases may serve the same API major.

## Contract-first rule

A new externally consumed use case is not implementation-ready until its contract declares at minimum:

- owning domain/capability;
- stable operation identity/name;
- surface and major version;
- method/path or non-HTTP invocation shape;
- canonical HTTP message/framing profile where HTTP is used;
- security-sensitive header cardinality, request-target and trusted-proxy semantics where applicable;
- structured request entity profile, duplicate/alias/boundary semantics and canonical-entity propagation where a structured body is accepted;
- actor/principal classes;
- tenant/global scope;
- trusted placement/routing/TenantContext boundary where applicable;
- request-contract validation ordering for fields consumed by authorization/resource selection;
- required authorization action/scope and owning authorization authority;
- request schema and size/complexity bounds;
- provider callback authentication/freshness-binding/replay-identity/atomic-admission/durable-coupling/replay-recovery-continuity/reconciliation semantics where applicable;
- response/result semantics;
- response-header profile and serialization/composition owner where HTTP headers are emitted;
- response-cache class/shared-cache/revalidation/current-auth semantics;
- artifact browser-delivery/media-type/active-content-isolation semantics where bytes are exposed;
- untrusted artifact-processing isolation/resource/egress/output-classification semantics where parsing/rendering/conversion occurs;
- consistency class;
- idempotency/retry/recovery-continuity behavior;
- one-time-secret response-loss/recovery and surviving recovery authority where applicable;
- optimistic-concurrency behavior where applicable;
- long-running-operation behavior where applicable;
- stable error codes/classes;
- audit class;
- observability/request-correlation requirements;
- compatibility/deprecation implications, including HTTP framing/header/proxy/target, structured-body parser, idempotency/callback recovery continuity, callback freshness/replay, response-header serialization, cache/security/browser-delivery semantics;
- data classification and secret/PII handling constraints.

The canonical endpoint template in this phase makes those fields reviewable before implementation.

## What Phase 09 intentionally does not finalize

Phase 09 does not select:

- queue/event-broker technology;
- broker acknowledgement/partition mechanics;
- event/message envelope details owned by Phase 10;
- cloud/orchestrator/storage vendors;
- telemetry physical engine;
- exact gateway/reverse-proxy product or HTTP protocol deployment mix;
- exact identity-provider or token protocol not already accepted elsewhere;
- exact provider callback authenticator, signed-header set, freshness window, replay storage product or transaction/reconciliation topology;
- exact backup/recovery product or recovery-generation/epoch representation;
- numeric SLO/RPO/RTO/capacity targets without evidence;
- domain capabilities that have not been accepted by Product/Requirements.

Phase 09 MAY define exact HTTP representations where Gate B intentionally delegated them here, including path/version conventions, error representation, idempotency header semantics, pagination/cursor representation, long-running operation resources and conditional request conventions.

Exact implementation products for structured request parsers, response-header serialization libraries, artifact storage, malware/content scanning, parser/renderer sandboxing and isolated browser-active delivery are not selected by this baseline. Their required security properties are.

## Maximum-state evolution test

Before a Phase 09 contract is accepted, reviewers SHOULD ask whether the contract remains coherent if all of the following become true later:

- tens or hundreds of thousands of tenants exist;
- some tenants live in dedicated cells/regions;
- Monitoring telemetry uses a specialized engine;
- high-volume domains are extracted into services;
- multiple provider adapters coexist for the same capability;
- browser, CLI, automation agents and third-party integrations consume the platform concurrently;
- a resource is relocated while clients remain active;
- old and new application versions coexist during rolling deployment;
- gateway/proxy/runtime products change or HTTP/1.x, HTTP/2 and HTTP/3 translation paths are introduced without changing accepted request semantics;
- structured body parser/runtime libraries change without changing the canonical entity consumed by authorization/idempotency/use cases;
- provider callback signature/authentication SDKs, replay infrastructure or backup/recovery topology change without changing authenticated freshness, replay identity scope, durable one-executor or recovery-continuity semantics;
- response framework/proxy/CDN composition changes without weakening the accepted response-header grammar/cardinality/serialization owner profile;
- an operation times out after an external side effect may already have happened;
- a cell/store is restored to an earlier point while a later irreversible operation/callback effect or provider acknowledgement survives elsewhere;
- a credential rotation response is lost while the caller must still have a safe recovery authority;
- a cache/CDN layer is added or replaced without changing authorization/canonical-request semantics;
- a tenant/provider uploads malicious or browser-active artifact content;
- preview/conversion/archive processing moves to a specialized isolated runtime without changing artifact identity;
- a customer changes plan, identity provider, region, provider or isolation class without changing logical resource identity.

If a contract requires callers to understand or rewrite around those implementation changes, or if infrastructure replacement changes the security interpretation of the same accepted request/response contract, the contract is not sufficiently decoupled.