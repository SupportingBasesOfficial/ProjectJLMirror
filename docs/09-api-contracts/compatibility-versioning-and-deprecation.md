# Compatibility, Versioning and Deprecation

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Contract evolution is explicit. JLMIRROR SHALL NOT treat application version, database schema version, gateway/proxy/runtime/parser replacement or service extraction as a reason for consumers to change or for the same accepted request/response to acquire a different security meaning.

## Major version namespace

Externally supported HTTP surfaces use explicit major versions:

```text
/api/v1/...
/bff/v1/...
/realtime/v1/...
/public/v1/...
/callbacks/v1/...
```

A major version is a semantic compatibility family. Patch/minor application releases do not appear in the URI.

## Compatibility within a major

Within one supported major, changes SHALL be backward compatible for conforming clients unless an explicitly accepted exception exists.

Generally compatible response evolution includes:

- adding an optional response field;
- adding an endpoint/resource family;
- adding an optional request field whose omission preserves prior behavior;
- adding link/metadata fields under already accepted response-header/representation semantics;
- adding a value to an enum explicitly classified open;
- increasing implementation capability without changing existing semantics.

## Breaking/security-sensitive changes

The following are breaking or security-sensitive by default:

- removing/renaming a field;
- changing type/semantic meaning;
- changing tenant/global ownership or stable identifier meaning;
- making an optional request field mandatory;
- incompatibly reducing documented ranges;
- changing a closed enum;
- changing accepted HTTP framing/header/method/trailer/content-coding/path/query/trusted-proxy interpretation;
- making a previously rejected ambiguous request accepted after gateway/proxy/runtime/parser change;
- changing query multiplicity/duplicate/order semantics;
- **changing structured request entity parsing**, duplicate/alias member semantics, multipart part/boundary semantics, name normalization or which canonical entity is consumed by validation/auth/idempotency/use case;
- changing success/error semantics affecting retry or authorization;
- changing idempotency scope/meaning;
- changing callback freshness binding, trusted replay-identity scope, atomic replay admission, durable work coupling or reconciliation semantics;
- changing pagination/cursor semantics beyond documented lifecycle;
- weakening cursor payload confidentiality, exposed-token classification, browser-history-safe transport or URL/log/referrer redaction;
- forcing protected query input into URL-visible transport;
- **changing response-header grammar/cardinality/serialization ownership** so the same logical response may emit a different security/cache/redirect meaning;
- allowing application/proxy/CDN layers to add a conflicting singleton response header that was previously unique;
- changing response-cache/shared-cache/current-authorization semantics;
- weakening artifact media/safe-filename/browser isolation/parser/archive/XML semantics;
- exposing physical/provider implementation semantics as required client input.

Breaking changes require a new major or another explicitly governed mechanism when client-visible semantics truly change. A pure security tightening MAY remain within the same major if conforming clients remain valid, but still requires explicit security/compatibility review.

A security policy becoming more permissive is never treated as an implementation-only optimization.

## Open versus closed enums

```text
open enum   -> clients tolerate unknown future values
closed enum -> unknown value indicates incompatible contract/client update requirement
```

Adding a value to a closed enum is breaking unless governance changes the classification before consumers rely on closure.

## Unknown response fields

Conforming clients ignore response fields they do not understand unless the representation is explicitly closed.

## Unknown request fields

Servers reject unknown request fields by default. Request extensibility uses explicit versioned schemas or documented extension namespaces, not silent passthrough.

## Semantic compatibility

Schema compatibility is necessary but insufficient.

Changing current-authoritative state into an approximation, retry/idempotency meaning, callback freshness/replay authority, cache reuse, query multiplicity, structured-body duplicate semantics, response-header serialization, browser cursor transport, archive identity or XML parser policy can be security-breaking even if JSON/OpenAPI schemas do not change.

Review evaluates behavior, HTTP/request entity interpretation, response serialization, consistency, security, ownership, authorization, idempotency, retry, callback authentication/freshness/replay/durability, cache, continuation, artifact/parser and realtime semantics in addition to shape.

## HTTP message/framing compatibility

`http-message-framing-and-canonicalization.md` is part of every external surface's security/compatibility contract.

Compatibility review compares at least:

- body framing and ambiguity rejection;
- `Content-Length`/`Transfer-Encoding` handling;
- unsafe-rejection connection retirement;
- security-sensitive request-header cardinality;
- request trailer and method-override policy;
- BFF cookie/header parsing;
- Host/authority/trusted-proxy interpretation;
- canonical path decoding before placement;
- slash/dot/encoded-separator/percent/UTF-8/double-decoding behavior;
- canonical query decoding/multiplicity;
- content-coding/raw/decoded limits;
- HTTP-version translation;
- callback exact-raw-body/signature semantics;
- realtime pre-`101` ingress;
- cache/proxy canonical request interpretation.

Changing gateway, proxy, HTTP server/library, protocol mix, connection-pooling topology or service extraction is implementation evolution only if these semantics remain equivalent and deployed-path ambiguity tests pass.

Numeric limits and exact gateway mechanics may remain OPEN; parser agreement and fail-closed semantics are not OPEN.

## Structured request entity compatibility

Structured body parsing is a security/compatibility dimension independent of schema shape.

Compatibility review SHALL compare:

- accepted structured media types;
- member/field/part-name normalization;
- duplicate member/part policy;
- alias/collision detection after accepted normalization;
- JSON duplicate-key behavior;
- number/string/Unicode interpretation used by validation and idempotency fingerprinting;
- multipart outer/nested boundary interpretation;
- multipart repeated-part semantics and per-part header/media metadata rules;
- nesting/container limits;
- which canonical parsed entity is propagated to request validation, owning authorization inputs, idempotency fingerprinting, callback semantics and use-case mapping;
- whether any layer reparses raw body bytes independently after canonical entity establishment.

A parser/library/framework replacement is **not compatible** merely because it accepts the same nominal JSON schema or multipart fields. It is incompatible/security-sensitive if first-value, last-value, duplicate merge, Unicode aliasing, multipart boundary or per-part interpretation changes the logical entity.

A change that lets authorization validate one entity while idempotency/use case executes another is a P1-class compatibility regression regardless of OpenAPI diff.

## Response-header compatibility

Every endpoint's `response_header_profile` and serialization owner are part of the semantic/security contract.

Compatibility review SHALL compare:

- emitted dynamic/security-relevant header set;
- per-header grammar;
- singleton/list/multi-value cardinality;
- control-character/CRLF/NUL rejection;
- URI/authority encoding rules for `Location`, `Link` and redirects;
- `ETag`, `Retry-After`, `Content-Disposition`, cache/security/CORS/authentication header serialization;
- request/correlation ID validation and output grammar;
- which layer owns serialization;
- whether BFF/proxy/CDN/application may append/combine values;
- response-header behavior after a business mutation has already committed.

Changing framework, response library, gateway, BFF, CDN or reverse-proxy configuration is security-sensitive if it alters these properties even when response bodies and OpenAPI schemas are unchanged.

A deployment is not compatible if untrusted metadata can newly inject CRLF/control delimiters, a singleton can become duplicated/conflicting, list serialization becomes parser-dependent, or an unsafe redirect/`Location` meaning appears.

Response serialization failure after commit does not change authoritative business outcome. Compatibility changes must preserve idempotency/operation/read recovery rather than creating new automatic mutation replay behavior.

## Response-cache compatibility

Compatibility review compares cache class, shared eligibility, key/variance dimensions, validators/revalidation, current authorization before reuse and security-relevant freshness/invalidation.

A CDN/framework change cannot make an endpoint more cache-permissive without reviewed contract change. `Vary` or caller-supplied tenant/principal labels do not substitute for authorization.

Cache/proxy cannot interpret request or response headers differently from the owning service.

## Cursor/query compatibility

Review compares cursor payload protection, exposed-token classification, browser transport, current authorization on continuation, URL/history/log/referrer handling, protected query URL policy and query multiplicity.

Moving a protected reusable browser continuation token into address/history-visible URL transport, exposing protected plaintext via encoded/signed cursor or changing singleton query semantics to first/last parser defaults is a security regression.

A machine-to-machine profile may accept a sensitive URL cursor only under an explicit non-browser profile; that does not relax browser policy.

## Artifact/parser/archive compatibility

Review compares:

- authoritative media type;
- safe `Content-Disposition`/filename;
- opaque/safe-inline/active-inline isolation;
- active-content capability/origin isolation;
- range/CDN preservation of erasure/delivery fencing;
- parser isolation/secret/egress policy;
- decompression/resource bounds;
- archive staging-root containment;
- canonical archive-member normalization/collision rejection;
- scanner-to-consumer byte equivalence;
- no-follow atomic/no-replace materialization;
- default DTD rejection;
- XML external entity/include/schema/stylesheet/resource policy;
- derivative artifact classification.

Framework/CDN/parser/archive/filesystem/runtime changes that weaken these properties are security-sensitive even without route/schema changes.

## Deprecation

Deprecation identifies the element/version, replacement, reason when useful, earliest removal boundary/version, migration notes and compatibility constraints.

Numeric support duration remains separately governed.

## No removal inside a supported major by default

Supported fields/routes SHOULD remain for the lifetime of their major unless continuation creates material security/compliance risk, the contract was explicitly experimental, or accepted emergency governance documents an exception.

## Experimental contracts

Experimental/preview lifecycle must be explicit. Experimental endpoints do not silently become critical production dependencies without formal promotion.

## BFF compatibility

BFF may evolve tightly with the first-party Web client but still preserves explicit major semantics and browser security invariants.

BFF changes cannot bypass downstream domain/API governance. Gateway/BFF/session/parser changes preserve canonical HTTP ingress, canonical structured entity interpretation, response-header profile, cursor transport and trusted proxy/origin semantics.

## Provider callback compatibility

Provider callback adapters may version independently while normalizing into stable JLMIRROR semantics.

A callback parser/library change must preserve raw-body authenticity semantics, canonical structured entity interpretation after verification, default DTD rejection and external-resolution policy. Signature verification over one byte/entity meaning while adapter logic processes another is incompatible and unsafe.

A provider protocol, SDK, gateway or callback middleware change must also preserve:

- which timestamp/nonce/sequence values are accepted as security freshness evidence;
- how each freshness value is bound to the authenticated callback body/identity or independently trusted protocol metadata;
- trusted replay-identity scope across tenant/integration/source dimensions;
- atomic create-or-observe replay admission;
- one-logical-executor behavior under concurrent delivery;
- durable inbox/work/effect coupling or explicit cross-authority reconciliation;
- crash behavior between replay admission, durable responsibility and acknowledgement;
- replay retention/expiry behavior for unresolved prior effects.

A time-window check over metadata that is no longer authenticator-bound is not a compatible implementation change. Replacing an atomic durable replay protocol with a read-then-record duplicate check is likewise a security regression even when callback schemas and provider IDs are unchanged.

## Public projection compatibility

Public projections remain subject to canonical request and response-header/cache semantics. Public does not mean parser ambiguity or unsafe response serialization is acceptable.

## Webhook/event boundary

Outbound webhook/event envelope compatibility belongs to Phase 10. Phase 09 management API version does not automatically version event envelopes.

## Database/schema changes

Database evolution is internal unless externally meaningful API semantics change. Mixed application/schema versions must continue serving declared-compatible API majors safely.

## Service extraction

Moving an owning context into a service SHALL NOT create a public break. Public IDs/routes/tenant scope/auth/idempotency/canonical request entity/response-header semantics remain stable unless separately governed.

Introducing proxy/service hops triggers framing/header/path/query/body-parser and response-header multi-hop tests.

## Provider replacement

Replacing external providers does not require consumers to replace canonical JLMIRROR IDs/paths. Provider-specific capabilities use explicit extensions rather than redefining core resources.

## Compatibility tests

CI SHALL compare proposed contract/manifest changes with accepted baseline and flag likely breaking/security-sensitive changes in:

- paths/methods;
- HTTP framing/method/trailer/content-coding/connection-rejection profile;
- request header cardinality;
- trusted proxy/authority/path/query normalization;
- query multiplicity;
- **structured request entity profile, duplicate/alias rules, multipart semantics and canonical propagation**;
- protocol-translation/parser boundaries;
- request requiredness/type and response fields/types;
- enum/status/error semantics;
- idempotency/authorization/consistency;
- **callback freshness binding, replay identity scope, atomic replay admission, durable coupling/reconciliation**;
- **response-header profile, grammar/cardinality/serialization owner/multi-hop composition**;
- pagination/cursor confidentiality/browser transport/logging;
- protected query URL policy;
- response cache class/variance/revalidation/current-auth semantics;
- artifact media/filename/browser/parser/archive/XML policies.

Automated schema diff is advisory. Human architecture/security review remains required for semantic changes invisible to schema.

Gateway/proxy/runtime/provider-SDK tests SHOULD exercise conflicting framing, request-header/query ambiguity, path normalization, structured JSON/multipart differential parsing, callback raw-body/entity equivalence, authenticated freshness binding, atomic replay admission/crash recovery and realtime pre-`101` admission.

Response-path tests SHOULD exercise dynamic header injection, duplicate singleton behavior across app/BFF/proxy/CDN and safe URI/list serialization.

Parser/archive tests SHOULD exercise duplicate/alias JSON fields, multipart ambiguity, DTD/XXE, archive collisions/no-replace and scanner-to-consumer byte equivalence.

## Version retirement

Retiring a major is governed product/operational work including consumer inventory where possible, migration guidance, usage telemetry, security/support posture and controlled disablement.