# HTTP Message Framing and Canonicalization

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

Every externally reachable HTTP surface SHALL convert the received wire message into one unambiguous canonical request before authentication, tenant routing, idempotency admission, authorization, cache lookup, callback verification or protected effects may rely on that request.

The security property is:

> one accepted wire message -> one canonical request interpretation -> one canonical structured entity where applicable -> the same logical meaning at every protected consumer.

A request that accepted hops/parsers can interpret differently is rejected fail-closed.

This applies to machine API, BFF/browser routes, public projections, provider callbacks, realtime/WebSocket pre-`101` admission, reverse proxies/gateways/load balancers and service-to-service HTTP translation reconstructing accepted external requests.

Exact gateway/proxy/runtime/parser products remain implementation choices.

## Threats addressed

This boundary prevents or contains:

- HTTP request smuggling/desynchronization;
- ambiguous body boundaries;
- authentication/header confusion;
- duplicate idempotency effects;
- cache poisoning/key disagreement;
- route/authority/path/query confusion;
- method override/trailer privilege injection;
- content-decoding disagreement;
- unsafe connection reuse after rejection;
- **structured-body parser differentials**, including duplicate/alias JSON members and multipart part/boundary ambiguity;
- HTTP-version translation inconsistencies;
- callback signature/body mismatch;
- WebSocket upgrade on ambiguous input.

## Canonical ingress ordering

Conceptual ordering:

```text
connection/protocol admission
  -> wire framing validation
  -> header syntax/cardinality/trailer validation
  -> authoritative method/request-target + path/query canonicalization
  -> trusted proxy normalization
  -> raw body hard bounds while reading
  -> content-coding/media-type admission
  -> canonical request envelope established
  -> authentication / logical tenant / trusted placement / authoritative route / cell admission / TenantContext
  -> canonical structured entity parse where body fields are protected inputs
  -> request-contract validation
  -> owning authorization
  -> idempotency/effect/use case under endpoint-specific ordering
```

Cheap fail-fast checks MAY occur earlier, but no protected decision treats uncanonicalized transport, target/query or structured entity as authoritative.

Placement routing never extracts authoritative tenant/resource scope from a non-canonical path/query.

Raw-body verification protocols preserve the exact bounded accepted bytes for signature verification; canonicalization SHALL NOT rewrite signed bytes before authenticity verification.

## Framing ambiguity is fail-closed

Ingress rejects ambiguous body/message boundaries. At minimum the accepted profile prevents:

- conflicting `Content-Length` and `Transfer-Encoding` semantics;
- multiple differing `Content-Length` values;
- malformed/unsupported/ambiguous transfer-coding chains;
- invalid chunk framing;
- protocol-invalid hop/framing metadata surviving translation;
- downstream body-length/framing interpretation differing from ingress.

Protocol-defined equivalent duplicate representation, if allowed, is reduced to one canonical interpretation before forwarding. Application code does not repair ambiguity after a proxy has already routed/authenticated it.

## Unsafe rejection and connection reuse

Rejecting one logical request is insufficient if unread/ambiguous bytes survive on a reusable transport.

After framing, chunking, boundary, early-size, content-coding or equivalent rejection:

- protocol-safe drain MAY occur only when the rejected request boundary is provably known and the parser chain guarantees draining cannot reinterpret attacker bytes as another request;
- unknown/ambiguous/malformed/truncated/unsafe-to-drain boundaries cause affected client and downstream/backend connection retirement;
- an ambiguously/partially forwarded backend connection is retired independently; closing only the client side is insufficient;
- early body-size rejection does not imply safe reuse while unread body bytes remain;
- `Expect: 100-continue` and interim responses cannot make frontend/backend disagree whether body bytes belong to the rejected/current/next request;
- rejected ambiguity never becomes a prefix of a later accepted request.

HTTP/2/3 MAY retire only the affected stream when implementation proves connection state and cross-stream isolation are intact. Connection-level uncertainty or unsafe translation requires broader retirement.

Exact drain/close primitive is OPEN; unsafe reuse is not.

## HTTP-version translation

HTTP/1.x, HTTP/2 and HTTP/3 translation SHALL:

- validate the source protocol;
- reject invalid/prohibited hop-specific framing metadata;
- construct target messages from canonical semantics rather than blindly forwarding framing fields;
- preserve one authoritative method/scheme/authority/target/body;
- never make an invalid source request valid merely through translation;
- retire downstream connections after partial ambiguous forwarding when safe synchronization is not proven.

## Canonical method and method override

There is one authoritative HTTP method.

Generic override mechanisms such as `X-HTTP-Method-Override`, `X-Method-Override`, form/query `_method` or framework equivalents are denied by default. A future accepted compatibility profile must make every hop derive the same effective method before routing, CSRF, authorization, idempotency, cache and use-case selection.

## Security-sensitive request-header cardinality

Every security-sensitive request header has an accepted cardinality/combine rule:

```text
strict_singleton
protocol_defined_list
multi_value_with_canonical_rule
not_accepted
```

`Authorization` and `Idempotency-Key` do not reach protected logic with competing values. Duplicates are rejected instead of first/last selection.

Protocol-defined list fields such as supported `If-Match` forms are parsed once into one canonical meaning. BFF duplicate security-relevant cookie names fail closed or are normalized by one accepted parser before auth/CSRF logic.

A header does not become safely multi-valued merely because a framework exposes an array/concatenated string.

## Request trailers

Trailers cannot introduce/override:

- authentication/session/credential fields;
- idempotency keys;
- tenant/routing/trusted-proxy metadata;
- CSRF/Origin authority;
- preconditions such as `If-Match`;
- content type/encoding/framing authority;
- callback signature/freshness/replay fields;
- realtime ticket/admission authority.

Non-security trailers require an explicit accepted profile with identical semantics across hops.

## Header syntax and control characters

Malformed request-header syntax, invalid controls, obsolete folding and whitespace/separator forms causing parser disagreement are rejected. Numeric header bounds remain evidence-driven but unlimited input is not accepted.

## Authority, host and trusted proxy metadata

The request has one authoritative scheme/authority/host meaning.

Conflicts among `Host`, `:authority`, absolute-form targets and trusted proxy metadata are rejected or safely normalized once. `Forwarded`/`X-Forwarded-*` are trusted only when inserted/rewritten by the explicit proxy trust boundary. Client-supplied copies cannot select scheme, host, client identity, tenant placement, secure-cookie behavior or redirect destination.

## Request-target canonicalization

Routing, placement, authorization, cache and downstream services consume the same canonical method/path/query.

### Path

Before placement resolution, the accepted path profile addresses/rejects:

- malformed/incomplete percent escapes;
- invalid/overlong/non-canonical encodings;
- encoded security delimiters where not explicitly permitted;
- encoded/alternate slash/backslash;
- dot segments and encoded equivalents;
- repeated/empty segment ambiguity;
- duplicate normalization or double decoding;
- Unicode normalization differences;
- authority embedded in alternate target forms;
- edge/service resource disagreement.

The canonical path is established once; downstream hops do not independently re-decode/collapse it.

### Query

Every query parameter defines decoded name/value, encoding policy, multiplicity and repetition semantics:

```text
singleton
repeated_list_with_canonical_rule
comma_list_under_singleton
not_accepted
```

Duplicate singleton parameters are rejected. Repeated parameters define order significance, duplicate treatment, maximum count and participation in cache, validation, authorization, idempotency and cursor binding.

Alternate encodings that normalize to the same logical name participate in duplicate detection. A service does not reparse raw query using framework-specific first/last/list rules.

Canonical query semantics do not make confidential URL values safe; cursor/query confidentiality remains separate.

## Canonical request envelope

After transport/target normalization, downstream components consume a canonical request envelope such as:

```text
method
authoritative scheme/authority
canonical path + route parameters
canonical classified query parameters
normalized accepted headers
trusted proxy/client metadata
bounded raw body bytes where required
accepted content-coding/media-type metadata
request_id / correlation context
```

Raw HTTP metadata is not independently reparsed into competing meanings after this boundary.

## Body, content coding and media interpretation

Framing decides where the body ends, not what it means.

After framing acceptance:

- raw body limits apply;
- content-coding is explicitly parsed and independently bounded;
- unsupported/malformed/ambiguously ordered codings are rejected;
- proxies do not transparently decode/re-encode protected bodies in a way that makes signature, size enforcement and application parse different representations unless the profile defines the transformation end-to-end;
- decoded size/nesting/parser limits are independent from raw bounds;
- duplicate/conflicting `Content-Type` meaning cannot differ across hops;
- callback signature profiles define the exact raw/entity representation authenticated;
- body parsing does not retroactively change framing boundaries.

Parser/decoded-size rejection after partial reads still obeys safe connection retirement.

## Canonical structured request entity

For structured media, canonical transport alone is insufficient. Before protected consumers use body fields, the endpoint establishes one **canonical parsed entity** under the accepted media profile.

### JSON profile

Default protected JSON semantics require:

- duplicate object member names rejected;
- member names that alias after accepted Unicode/name normalization rejected;
- no first-value/last-value/merge selection for duplicates;
- deterministic number/string/Unicode interpretation for validation and idempotency fingerprinting;
- unknown request fields handled by the endpoint schema, not silently swallowed by a parser differential;
- accepted nesting/member bounds.

A change in JSON library is safe only if these logical semantics remain equivalent.

### Multipart profile

For accepted multipart bodies:

- outer and nested boundaries have one deterministic grammar;
- duplicate/aliasing singleton part names are rejected unless the endpoint explicitly defines bounded repeated-part semantics;
- part-name normalization/multiplicity is explicit;
- conflicting per-part `Content-Disposition` names or media metadata cannot produce different logical parts across layers;
- nested multipart ambiguity fails closed;
- part count/header/decoded-size/nesting are bounded;
- a part validated under one identity cannot later be consumed under another name/type interpretation.

### Other structured media

Form encoding, XML, protobuf-like/vendor formats or future structured media require an explicit equivalent profile for field/member naming, duplicates, aliases, nesting and deterministic decoding before protected use. XML retains the separately defined DTD/external-resolution protections.

### Canonical entity propagation

Raw bytes MAY remain available for signature/audit, but after canonical entity establishment these consumers SHALL use the same logical entity and SHALL NOT independently reparse attacker-controlled raw body bytes:

```text
request-contract validation
owning authorization inputs
body-derived resource/scope inputs where permitted
idempotency fingerprinting
optimistic-concurrency/body precondition inputs
callback semantic processing after authenticity verification
cache semantics when body participates in an accepted key
use-case/domain command mapping
```

If two accepted parsers could derive different protected fields from the same accepted body, the request fails closed before owning authorization/effect.

## BFF/browser routes

BFF Origin/CORS/CSRF/session handling operates on the canonical request. Body-bearing BFF mutations additionally consume only the canonical structured entity. Duplicate cookie/header/query/body semantics cannot differ between edge and BFF application.

## Realtime/WebSocket upgrade

Realtime admission inherits canonical HTTP ingress before `101`:

- ambiguous framing/header/path/query rejected;
- expected Origin evaluated from canonical request;
- ticket presentation has one canonical value;
- conflicting upgrade/security interpretation cannot authorize differently;
- method/trailer cannot introduce authority;
- no `101` until canonical ingress and realtime invariants pass.

Rejected/aborted upgrades obey safe connection retirement when byte-stream synchronization is uncertain.

## Provider callbacks

Callback ingress inherits canonical transport before signature/freshness/replay/domain processing.

- raw bound applies to accepted framing;
- callback auth/signature/timestamp/nonce headers have explicit cardinality;
- security fields cannot enter via trailers;
- signature verification receives the exact bounded representation required by provider profile;
- content decoding cannot authenticate one representation while processing another;
- after authenticity verification, structured callback bodies establish a canonical entity before semantic mapping/effect;
- authenticated raw bytes are not reparsed by multiple components into different provider/resource/action values;
- rejected partial bodies obey safe connection retirement.

## Cache interaction

Cache/reverse proxy uses the same canonical request semantics as the application. It cannot depend on alternate method, authority, path/query, request-header, trailer, framing/content-coding or structured-body interpretation.

If body participates in an accepted cache key/eligibility decision, it uses canonical entity semantics; raw parser-dependent duplicate behavior cannot split cache and origin meaning.

A proxy rejecting after partial body forwarding does not return an uncertain backend connection to a pool.

## Logging and observability

Security telemetry records safe canonical rejection classes without raw credentials/protected query/body payloads. Examples:

```text
framing_conflict
duplicate_security_header
authority_conflict
invalid_request_target
duplicate_singleton_query
method_override_rejected
security_trailer_rejected
content_coding_conflict
structured_entity_duplicate_member
structured_entity_alias_collision
multipart_boundary_ambiguity
connection_retired_after_rejection
```

Logs do not become an oracle for rejected secret/header/query/body values.

## Error behavior

Canonicalization rejection occurs before the request is treated as a valid protected operation and SHALL NOT create idempotency claim, durable operation or protected effect.

External errors remain sparse. When synchronization is uncertain, connection safety takes precedence over preserving keep-alive or returning a rich error.

## Contract metadata

Endpoint/surface contracts declare/inherit:

```text
http_message_profile
security_header_cardinality
request_trailer_policy
method_override_policy
trusted_proxy_metadata_policy
request_target_profile
query_multiplicity_policy
body_framing_policy
content_coding_policy
connection_rejection_policy
structured_request_entity_profile
structured_entity_duplicate_policy
structured_entity_alias_normalization_policy
structured_entity_canonical_propagation_policy
```

Provider callback/realtime profiles add protocol-specific security requirements.

## Required tests

Where applicable, deployed-path tests include:

- conflicting CL/TE and differing lengths;
- malformed chunking;
- protocol translation invalid framing;
- duplicate `Authorization`/`Idempotency-Key`;
- canonical `If-Match` semantics;
- BFF duplicate security cookie ambiguity;
- security trailer rejection;
- method override rejection;
- Host/authority/forwarded spoofing;
- slash/dot/encoded separator/UTF-8/percent/double-decoding path cases;
- duplicate singleton/alternate-encoded query keys;
- repeated query canonical rule;
- content-coding disagreement;
- early size/framing rejection followed by attempted connection reuse;
- backend pool retirement after ambiguous partial forwarding;
- `Expect: 100-continue` synchronization;
- duplicate JSON members and normalization aliases;
- multipart duplicate/alias part names, per-part metadata conflict and ambiguous nested boundary;
- parser differential vectors proving one canonical entity;
- validation/auth/idempotency/use-case entity equivalence;
- callback raw signature and canonical semantic entity equivalence;
- realtime rejection before `101`;
- cache/origin canonical meaning equivalence.

Tests exercise real protocol/parser boundaries where present, not only controller unit tests.

## Release-blocking failures

Release is blocked if:

- accepted hops disagree where a request ends;
- rejected ambiguity leaves reusable uncertain connection state;
- request headers/method/trailers/authority/path/query/content coding have competing meanings;
- placement consumes non-canonical path/query;
- a structured body can produce two logical entities under accepted parsers;
- duplicate/alias JSON fields can be first/last/merged differently;
- multipart part/boundary/per-part metadata ambiguity can make protected layers observe different fields;
- owning authorization, idempotency or use case reparses raw body into a different entity after canonical parse;
- callback signature verifies one body while semantic processing consumes another logical entity;
- cache and origin derive different request meaning;
- an ambiguous request receives realtime `101`.

## Compatibility and evolution

Framing/header/method/trailer/content-coding/connection-rejection/path/query/**structured-entity** semantics are part of the security contract.

Changing gateway, proxy, HTTP runtime, protocol version, connection pool, JSON/multipart parser, framework or service topology triggers regression review. A parser/library change that accepts previously rejected duplicate/alias/boundary ambiguity is security-sensitive even when OpenAPI schema is unchanged.

## Intentionally OPEN

Implementation/profile decisions remain OPEN for:

- gateway/reverse-proxy product;
- HTTP version mix;
- numeric header/body/entity limits;
- trusted-proxy configuration syntax;
- canonical internal request-envelope library;
- allowed path character repertoire per surface;
- supported non-identity content codings;
- exact safe drain/close primitive;
- exact JSON/multipart/parser library **provided canonical entity semantics are equivalent**;
- malformed transport status mapping where safe to return one.

These OPENs never make ambiguity, parser differential acceptance or unsafe connection reuse optional.
