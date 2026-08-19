# Compatibility, Versioning and Deprecation

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Contract evolution is explicit. JLMIRROR SHALL NOT treat application deployment version, database schema version, gateway/proxy/runtime replacement or service extraction as a reason for external consumers to change or for the same accepted request to acquire a different security meaning.

## Major version namespace

Externally supported HTTP surfaces use an explicit major version in the URI:

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

- adding a new optional response field;
- adding a new endpoint/resource family;
- adding a new optional request field whose omission preserves prior behavior;
- adding a new link/metadata field;
- adding a new value to an enum explicitly classified as open;
- increasing server capability without changing existing semantics.

## Breaking/security-sensitive changes

The following are breaking or security-sensitive by default:

- removing or renaming a field;
- changing a field's type or semantic meaning;
- changing tenant/global ownership/scope;
- changing a stable identifier's meaning;
- making a previously optional request field mandatory;
- reducing a documented allowed value/range in a way existing valid clients may violate;
- changing a closed-enum value set;
- changing accepted HTTP framing/header/method/trailer/content-coding/path/query/trusted-proxy interpretation so the same wire request can acquire a different security/routing meaning;
- making a previously rejected ambiguous request accepted because of gateway/proxy/runtime/parser change;
- changing query multiplicity/duplicate behavior so first/last/list semantics differ from the accepted contract;
- changing success/error semantics in a way that alters safe retry or authorization behavior;
- changing idempotency scope/meaning such that an existing key can duplicate or suppress a different logical effect;
- changing pagination ordering/cursor semantics in a way that invalidates active traversal beyond the cursor contract's documented lifecycle;
- weakening cursor payload confidentiality, exposed-token classification, browser-history-safe transport or URL/log/referrer redaction;
- forcing previously protected filter/search input into URL-visible query transport;
- changing an endpoint's response-cache class, shared-cache eligibility, variance dimensions or current-authorization revalidation requirements in a way that can make previously private/protected data more broadly reusable;
- weakening artifact media classification, safe filename, browser-delivery/active-content isolation, parser sandbox/egress/resource bounds, archive extraction containment, canonical archive-member collision policy, atomic no-replace materialization or XML DTD/external-resolution semantics;
- exposing previously hidden physical/provider implementation semantics as required client input.

Breaking changes require a new major contract or another explicitly governed compatibility mechanism when client-visible semantics truly change. A pure security tightening MAY remain within the same major if conforming client behavior remains valid, but it still requires explicit security/compatibility review.

A security-tightening HTTP/cache/cursor/artifact/parser change MAY be deployable inside the same major when it preserves functional semantics for conforming clients, but a security policy becoming more permissive is never treated as an implementation-only optimization.

## Open versus closed enums

Enum extensibility is part of the field schema:

```text
open enum   -> unknown future value must be tolerated by clients
closed enum -> unknown value indicates incompatible contract or client update requirement
```

Adding a new value to a closed enum is treated as breaking unless the field's compatibility classification is changed through governance before consumers rely on closure.

## Unknown response fields

Conforming clients MUST ignore response fields they do not understand unless the representation is explicitly closed.

Generated SDKs SHALL preserve this behavior rather than failing deserialization merely because a compatible field was added.

## Unknown request fields

Servers reject unknown request fields by default. This prevents typos and unsupported writes from appearing successful.

Request extensibility occurs through explicit versioned schemas or documented extension namespaces, not silent unknown-field passthrough.

## Semantic compatibility

Schema compatibility is necessary but not sufficient.

Changing a field from "current authoritative state" to "eventually consistent approximation", changing whether an operation is idempotent/retry-safe, changing response-cache reuse semantics, changing query/parser multiplicity, exposing cursor tokens in browser history, weakening archive scanner-to-consumer identity, accepting DTDs that were previously rejected, or changing how HTTP hops interpret the same request can be a semantic breaking/security change even if JSON/OpenAPI schemas are unchanged.

Contract review therefore evaluates behavior, HTTP message interpretation, consistency, security, ownership, authorization, idempotency, retry, cache, continuation confidentiality/transport, artifact delivery/archive processing and parser semantics in addition to shape.

## HTTP message/framing compatibility

`http-message-framing-and-canonicalization.md` is part of the security/compatibility contract for every externally reachable HTTP surface.

Compatibility review SHALL compare at least:

- accepted body framing and ambiguity rejection;
- `Content-Length`/`Transfer-Encoding` handling;
- security-sensitive header cardinality/combine semantics;
- request-trailer policy;
- method-override policy;
- BFF security-relevant cookie/header parsing profile;
- Host/authority and trusted-proxy metadata interpretation;
- canonical path decoding before tenant placement;
- repeated slash, dot-segment, encoded-separator, percent/UTF-8/double-decoding behavior;
- canonical query decoding and singleton/repeated parameter multiplicity;
- `Content-Encoding`/decoded-body semantics and raw/decoded bounds;
- HTTP-version translation behavior and hop-by-hop field handling;
- callback exact-raw-body/signature consistency;
- realtime canonical-ingress requirement before `101`;
- cache/proxy interpretation of canonical request keys.

Changing gateway, reverse proxy, HTTP server/library, protocol-version mix or service topology is implementation evolution only if those canonical semantics remain equivalent and the deployed cross-hop ambiguity tests still pass.

A deployment change that makes a previously ambiguous/rejected request reach protected authentication/idempotency/placement/authorization/effect logic is a security regression even when clients see the same OpenAPI schema.

Numeric header/body limits and exact gateway configuration may remain `OPEN-API-021`; parser agreement/fail-closed semantics are not OPEN.

## Response-cache compatibility

Each endpoint's accepted cache policy is part of its semantic/security contract.

Compatibility review SHALL compare at least:

- cache class (`no_store`, `private_revalidate`, `public_shared`, `artifact_delivery_guarded`);
- whether shared-cache reuse is permitted;
- cache key/variance dimensions that are contractually meaningful;
- validator/revalidation behavior;
- whether current authorization/releasability must be re-evaluated before reuse;
- security-relevant freshness/invalidation semantics where accepted.

A deployment, CDN or framework change SHALL NOT make an endpoint more cache-permissive than its accepted contract without a reviewed contract change. `Vary`, URL partitioning or tenant/principal labels do not substitute for authorization.

A cache/proxy also cannot treat method/authority/path/query/header/content-coding ambiguity differently from the owning service. Canonical message interpretation precedes safe cache eligibility.

Numeric TTL tuning may remain `OPEN-API-017` when not yet accepted, but the absence of a number does not make cache class or authorization/revalidation semantics implementation-private.

## Cursor/query compatibility

Continuation/query transport is part of the security contract.

Compatibility review SHALL compare:

- cursor payload protection: server-side opaque handle, confidentiality+integrity envelope or equivalent;
- exposed cursor-token classification: URL-safe non-sensitive handle versus protected continuation token;
- browser transport: URL-visible versus required non-URL-visible continuation;
- current-authorization re-evaluation on continuation;
- cursor URL/history/log/analytics/referrer/redirect handling;
- whether protected filter/search values are permitted in query strings;
- query decoding/multiplicity, duplicate and ordering semantics.

Changing from a confidentiality-safe cursor/query design to signed/encoded plaintext, moving a protected reusable browser continuation token into address/history-visible URL transport, or changing singleton query behavior to framework-specific first/last semantics is a security regression even if clients still treat the cursor as opaque.

A machine-to-machine profile may intentionally permit a URL-visible sensitive cursor only when that non-browser profile explicitly accepts and controls the full token as sensitive transport. That does not relax the default browser policy.

## Artifact/parser/archive compatibility

Artifact delivery and untrusted-content processing carry security semantics independent of JSON schema.

Compatibility review SHALL compare:

- authoritative media-type classification;
- safe download-name and `Content-Disposition` semantics;
- `opaque_download` / `safe_inline` / active-inline isolation class;
- active-content origin/capability isolation;
- CDN/range/resume preservation of browser-delivery and erasure fencing;
- parser/renderer isolation, secret scope and egress policy;
- decompression/resource bounds;
- archive staging-root containment;
- canonical archive-member normalization under target filesystem semantics;
- duplicate/Unicode/case/platform alias collision rejection;
- scanner-to-consumer canonical member/byte equivalence;
- no-follow atomic/no-replace materialization or equivalent;
- **DTD rejection under the default XML profile**;
- XML/structured-parser external entity/include/schema/stylesheet/resource resolution;
- derived artifact independent classification.

A framework/CDN/parser/archive/filesystem/runtime change that weakens one of these properties is security-sensitive even when no route/schema changes.

An archive runtime is not equivalent merely because both implementations keep paths inside one root; if their case/Unicode/path normalization permits different colliding members or scan-then-overwrite behavior, the security contract changed.

An XML parser/library upgrade is not equivalent if it begins accepting a DTD or enables active resolution under the default profile.

## Deprecation

A supported contract element is deprecated before removal when practical.

Deprecation SHALL identify:

- deprecated operation/field/version;
- recommended replacement;
- reason when useful;
- earliest removal boundary/version;
- migration notes;
- compatibility constraints.

Numeric minimum support/deprecation duration remains a commercial/SLO/governance decision until separately accepted. A removal SHALL NOT occur earlier than the accepted support policy applicable to that consumer class.

## No removal inside a supported major by default

Externally supported fields/routes SHOULD remain available for the lifetime of their supported major unless:

- continuing them creates a material security/compliance risk;
- the contract was explicitly experimental/non-stable;
- an accepted emergency governance decision documents the exception.

Normal cleanup pressure is not sufficient reason to break consumers.

## Experimental contracts

A contract MAY be labeled experimental/preview only when that lifecycle is explicit in the schema/docs and consumers are told that compatibility guarantees differ.

Experimental endpoints SHALL NOT silently become critical production dependencies without formal promotion to the normal supported contract policy.

## BFF compatibility

The first-party BFF may evolve more tightly with the first-party Web client than the machine API, but it still uses explicit major-version semantics and SHALL preserve the accepted browser security invariants.

A BFF change cannot bypass downstream API/domain governance merely because the browser is deployed by the same organization.

Gateway/BFF/session/parser changes also preserve canonical HTTP ingress, security-relevant cookie/header interpretation, canonical path/query semantics, protected cursor transport and trusted proxy/origin semantics.

## Provider callback compatibility

Provider callback adapters version independently when external provider protocols require it. Provider-specific payload changes are normalized behind the adapter and SHALL NOT leak into unrelated public domain contracts.

Where a provider changes a callback protocol incompatibly, the adapter may temporarily support multiple provider versions while producing one stable JLMIRROR domain/application contract.

A parser/library/profile change for XML or another active structured format must preserve **default DTD rejection** and accepted external-resolution policy. A library default that re-enables DTD/entities/includes/schema/network resolution is a security regression, not a compatible implementation detail.

A gateway/runtime change must also preserve the exact bounded raw body/security-header/content-coding interpretation authenticated by the callback profile. Signature verification over bytes different from those processed by the adapter is incompatible and unsafe.

## Public projection compatibility

Public status/projection consumers may be unauthenticated and difficult to inventory. Their compatibility changes therefore require the same or stronger caution as authenticated public APIs.

Public does not mean ambiguity-safe by default; request framing/cache/path/query interpretation still follows the canonical HTTP ingress profile.

## Webhook/event boundary

Outbound webhook/event envelope compatibility belongs to Phase 10. Phase 09 management APIs for subscriptions/configuration SHALL NOT assume that changing an HTTP management API major automatically changes the event envelope major.

## Database/schema changes

Expand/migrate/contract database evolution is internal. A database column/table rename does not trigger an API major version unless it changes externally meaningful semantics.

Mixed application/schema versions during rolling deployment SHALL continue serving the accepted API major combinations declared safe by migration/release design.

## Service extraction

Moving an owning context from the modular monolith into a separately deployed service SHALL NOT create a public API break.

Internal routing may change. Public operation identity, tenant scope, authorization, idempotency, resource representation and canonical HTTP request meaning remain stable unless a separately governed external contract change is accepted.

Introducing a new proxy/service hop during extraction triggers cross-hop framing/header/path/query/content-coding regression tests; extra distribution cannot create a new parser-confusion authority boundary by accident.

## Provider replacement

Replacing Zabbix, a payment provider, notification provider, object store or other external dependency SHALL NOT require consumers to replace canonical JLMIRROR resource IDs or paths.

Provider-specific capabilities that genuinely differ are exposed as explicit capability metadata or provider-specific extension contracts rather than redefining the core resource.

## Compatibility tests

CI SHALL compare proposed contract changes with the currently accepted baseline and flag likely breaking/security-sensitive changes in:

- paths/methods;
- HTTP message/framing/method/trailer/content-coding profile;
- security-sensitive header cardinality/combine rules;
- trusted proxy/authority/path/query normalization;
- query multiplicity/duplicate/order semantics;
- HTTP-version translation profile/parser boundary;
- request requiredness/type;
- response fields/types;
- enum compatibility classification;
- status/error codes;
- operation idempotency declaration;
- authorization declaration;
- pagination/sort contract;
- cursor confidentiality, exposed-token classification and browser transport;
- cursor URL/log/referrer policy;
- protected query URL policy;
- resource identity/scope;
- response cache class/shared-cache eligibility;
- cache variance/validator/revalidation/current-authorization semantics;
- artifact media/safe-filename/browser-delivery/active-content isolation;
- parser/renderer isolation/egress/resource limits;
- archive canonical-member/collision/materialization policy;
- XML default DTD/external-resolution policy.

Automated schema diff is advisory for semantic compatibility; human/architecture/security review remains required for meaning changes, especially changes that alter HTTP parser/security interpretation, expose protected tokens/data, or grant active content/parser/archive behavior without changing schema.

Gateway/proxy/runtime changes SHOULD execute the deployed-path ambiguity suite, including conflicting framing, duplicate security headers/query parameters, authority/proxy spoofing, path normalization before placement, method/trailer/content-coding behavior, callback raw-body/signature equivalence and realtime pre-`101` canonical-ingress cases.

Parser/archive changes SHOULD execute DTD/XXE, archive duplicate/normalization collision, no-follow/no-replace and scanner-to-consumer byte-equivalence tests.

## Version retirement

Retiring a major version is a governed product/operational process, not merely deleting routes.

Retirement includes consumer inventory where possible, migration guidance, telemetry on remaining usage, security/support posture and a controlled disablement plan.