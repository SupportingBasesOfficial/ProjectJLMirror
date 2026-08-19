# HTTP Message Framing and Canonicalization

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

Every externally reachable HTTP surface SHALL convert the received wire message into one unambiguous canonical request before authentication, tenant routing, idempotency admission, authorization, cache lookup, callback verification or protected effects may rely on that request.

The security property is simple:

> one accepted wire message -> one canonical request interpretation -> the same interpretation at every downstream hop.

A request that can be interpreted differently by two accepted hops is rejected fail-closed rather than normalized differently by each hop.

This contract applies to:

- machine API;
- BFF/browser HTTP routes;
- public HTTP projections;
- provider callback/webhook ingress;
- realtime/WebSocket HTTP upgrade admission before `101`;
- reverse proxies, gateways, load balancers and service-to-service HTTP translation that terminate or reconstruct an accepted external request.

Exact gateway/proxy/runtime products remain implementation choices.

## Threats addressed

This boundary exists to prevent or contain:

- HTTP request smuggling/desynchronization;
- ambiguous request-body boundaries;
- authentication/header confusion;
- duplicate idempotency execution caused by different header interpretations;
- cache poisoning or cache-key disagreement;
- route/authority confusion;
- trusted-proxy header spoofing;
- HTTP-version translation inconsistencies;
- callback signature/body verification against bytes different from those processed by the application;
- WebSocket upgrade admission on an ambiguously framed request.

## Canonical ingress ordering

Conceptual ordering for a normal accepted HTTP request:

```text
connection/protocol admission
  -> wire framing validation
  -> header syntax/cardinality validation
  -> trusted proxy metadata normalization
  -> authoritative request-target normalization
  -> request/body hard bounds while reading
  -> canonical request envelope established
  -> surface-specific authentication / tenant routing / authorization / callback verification / cache / use case
```

A surface MAY perform cheaper transport rejection earlier, but no protected decision treats an uncanonicalized message as authoritative input.

Provider callback signatures that require exact raw bytes are evaluated against the bounded raw body associated with the already accepted framing; canonicalization SHALL NOT silently rewrite signed body bytes before signature verification.

## Framing ambiguity is fail-closed

Ingress SHALL reject requests whose body/message boundary is ambiguous under the accepted protocol profile.

At minimum the accepted profile prevents:

- conflicting `Content-Length` and `Transfer-Encoding` semantics;
- multiple differing `Content-Length` values;
- malformed, unsupported or ambiguous transfer-coding chains;
- invalid chunk framing;
- protocol-version-invalid hop/framing headers surviving translation;
- a downstream hop receiving a body length/framing interpretation different from the ingress interpretation.

If an accepted intermediary permits a protocol-defined equivalent duplicate representation, it MUST reduce that representation to one canonical interpretation before forwarding. Ambiguity or parser disagreement fails closed.

The platform SHALL NOT rely on application code to repair an ambiguous message after a proxy/gateway has already routed or authenticated it.

## HTTP-version translation

HTTP/1.x, HTTP/2 and HTTP/3 have different wire/framing rules. A gateway translating between versions SHALL:

- validate the source protocol before translation;
- reject prohibited/invalid hop-specific framing metadata;
- generate the target protocol message from the canonical request rather than blindly forwarding raw framing headers;
- preserve one authoritative method, scheme, authority, request target and body;
- never make an invalid source request valid merely by translation.

Connection-specific/hop-by-hop fields that are not valid across the target protocol boundary are stripped/reconstructed according to the accepted protocol profile, not propagated as application metadata.

## Security-sensitive header cardinality

Header names are case-insensitive, but duplicate field lines and multi-value semantics are not automatically safe.

Every security-sensitive header used by a contract SHALL have an accepted cardinality/combine rule. Categories include:

```text
strict_singleton
protocol_defined_list
multi_value_with_canonical_rule
not_accepted
```

Examples of values normally requiring strict single interpretation include authentication credentials, idempotency keys and trusted routing/proxy metadata.

`Authorization` and `Idempotency-Key` SHALL NOT have two competing values reach protected application logic. Duplicate/conflicting instances are rejected rather than choosing first/last arbitrarily.

Conditional headers such as `If-Match` may have protocol-defined list semantics; where supported, the ingress parses that grammar once and propagates one canonical parsed meaning. Duplicate field lines cannot be allowed to produce different effective preconditions at different hops.

For cookie-authenticated BFF flows, ambiguous duplicate security-relevant cookie names or cookie parsing differences SHALL fail closed or be normalized by one accepted cookie parser before authorization/CSRF logic consumes them.

A header not explicitly accepted as multi-valued MUST NOT become multi-valued merely because a framework returns an array or concatenated string.

## Header syntax and control characters

Malformed header syntax, invalid control characters, obsolete folding or separator/whitespace forms that can cause cross-hop parser disagreement are rejected under the accepted protocol profile.

Numeric limits for total header bytes/count/per-field size remain evidence-driven, but unlimited header input is not accepted.

## Authority, host and trusted proxy metadata

The request has one authoritative external authority/host meaning for routing/security decisions.

Ingress SHALL reject or safely resolve conflicts between protocol authority metadata such as `Host`, `:authority`, absolute-form request targets and trusted proxy metadata. Two hops SHALL NOT select different tenants/routes/security policies because they disagree about authority.

`Forwarded`, `X-Forwarded-*` or equivalent deployment metadata is trusted only when inserted/rewritten by an explicitly trusted proxy boundary. Untrusted client-supplied copies are removed, ignored or replaced before application logic consumes them.

Client-controlled forwarded headers SHALL NOT select scheme, host, client identity, tenant placement, secure-cookie behavior or redirect destination.

## Request-target canonicalization

Routing, authorization, cache selection and downstream services SHALL consume the same canonical method/path/query interpretation.

The accepted request-target profile SHALL prevent parser disagreement around, as applicable:

- malformed percent encoding;
- invalid character encoding;
- dot segments;
- encoded or alternate path separators;
- duplicate/ambiguous path normalization;
- authority embedded in alternate request-target forms;
- decoding the same component more than once;
- a gateway routing one path while the owning service authorizes another.

Exact path-normalization rules MAY vary by external surface, but a surface cannot accept a request unless all participating hops share the same externally meaningful interpretation.

Canonical resource identity remains logical and SHALL NOT expose or derive physical tenant placement.

## Canonical request envelope

After successful ingress normalization, downstream application components consume a canonical request envelope rather than independently reparsing ambiguous raw HTTP metadata.

Conceptually the envelope contains validated meanings such as:

```text
method
authoritative scheme/authority
canonical route/path parameters
classified query parameters
normalized accepted headers
trusted proxy/client metadata
bounded raw body bytes where required
parsed body only after the appropriate security boundary
request_id / correlation context
```

The envelope is an internal representation, not a new public API format.

A service extraction, gateway replacement or HTTP-version change SHALL preserve the same canonical external semantics.

## Body and content interpretation

Message framing decides **where the body ends**, not what the body means.

After framing acceptance:

- raw body byte limits still apply;
- content encoding/decompression remains independently bounded;
- media type is validated by the target contract;
- callback raw-body signature protocols preserve exact accepted raw bytes;
- multipart/archive/document parsing remains subject to its own parser/security limits;
- body parsing does not retroactively change the accepted message boundary.

## BFF and browser routes

BFF Origin/CORS/CSRF/session handling operates only on the canonical request.

A duplicate/conflicting authentication/session/CSRF header or ambiguous request target cannot be resolved differently by edge infrastructure and BFF application code.

Trusted proxy metadata used to determine secure origin/scheme is accepted only from the configured proxy trust boundary.

## Realtime/WebSocket upgrade

The HTTP request that may become a realtime/WebSocket connection inherits this entire framing/canonicalization contract before any protected `101` response.

Therefore:

- ambiguous body/framing/header requests are rejected before upgrade;
- expected Origin is evaluated from the canonical request;
- ticket/capability presentation has one canonical value;
- conflicting upgrade/security header interpretations cannot result in one hop authorizing what another hop interpreted differently;
- no `101` occurs unless both this boundary and the realtime admission invariants pass.

## Provider callbacks

Callback ingress inherits this boundary before signature/freshness/replay/domain processing.

In particular:

- ambiguous framing cannot be used to make the gateway verify one body while the adapter processes another;
- the raw-body hard limit applies to the body established by the accepted framing;
- duplicate/conflicting signature, timestamp, nonce or callback-auth headers follow the provider profile's explicit cardinality rule;
- provider-specific raw-signature verification receives the exact bounded raw representation associated with the canonical request;
- HTTP normalization never turns unauthenticated alternate bytes into trusted callback content.

## Cache interaction

A cache/reverse proxy SHALL key and evaluate requests using the same canonical request semantics accepted by the application.

Cache behavior MUST NOT depend on an alternate interpretation of:

- authority/host;
- path/query normalization;
- duplicate headers;
- content negotiation;
- authentication/security headers;
- body framing.

Requests with ambiguous cache-relevant/security-relevant metadata fail closed rather than being cached under one interpretation and served under another.

## Logging and observability

Security observability records the canonical request interpretation and the reason for rejected ambiguity without logging unrestricted raw credentials, protected query/cursor material or full malicious payloads.

Useful safe evidence may include:

- protocol/version;
- ingress profile;
- normalized route template;
- rejection class such as `framing_conflict`, `duplicate_security_header`, `authority_conflict`, `invalid_request_target`;
- request/correlation identity;
- trusted proxy identity where applicable.

Logs SHALL NOT become an oracle containing the rejected secret/header values themselves.

## Error behavior

Framing/canonicalization rejection occurs before the request is treated as a valid protected application operation.

External errors are deliberately sparse and do not reveal which intermediary/parser would have accepted the alternate interpretation.

A framing rejection SHALL NOT create an idempotency claim, durable operation or protected domain effect.

## Contract metadata

Endpoint/surface contracts SHALL declare or inherit:

```text
http_message_profile
security_header_cardinality
trusted_proxy_metadata_policy
request_target_profile
body_framing_policy
```

A common platform profile MAY satisfy these fields for ordinary routes; an endpoint only specializes where its protocol requires it.

Provider callback and realtime profiles additionally declare their protocol-specific security header/cardinality requirements.

## Required tests

Edge/integration testing SHALL include, where protocol support makes the case applicable:

- `Content-Length` plus conflicting `Transfer-Encoding` rejected;
- multiple differing `Content-Length` rejected;
- malformed chunk framing rejected;
- unsupported/prohibited framing metadata rejected during HTTP-version translation;
- duplicate/conflicting `Authorization` rejected;
- duplicate/conflicting `Idempotency-Key` rejected before claim/effect;
- conditional-header multi-value input has one documented canonical interpretation;
- duplicate security-relevant cookie ambiguity cannot change BFF auth/CSRF outcome;
- conflicting `Host`/authority forms rejected;
- untrusted `Forwarded`/`X-Forwarded-*` cannot spoof trusted scheme/host/client metadata;
- ambiguous/malformed percent-encoding/path normalization cannot route and authorize different resources;
- gateway -> service propagation contains only the canonical interpretation;
- callback signature verification and callback processing use the same accepted raw body;
- callback raw-body limit cannot be bypassed by alternate framing;
- realtime upgrade rejects ambiguous framing/security headers before `101`;
- cache/proxy and origin service cannot derive different cache/security meaning from duplicate/ambiguous metadata.

Tests SHOULD exercise the actual deployed protocol translation path where one exists, not only an in-process controller test.

## Release-blocking failures

The following block implementation/release:

- two accepted hops can disagree on where one request ends and the next begins;
- conflicting framing reaches application authentication or body processing;
- duplicate security-sensitive headers are resolved by arbitrary first/last/framework behavior;
- a gateway and owning service can authorize different credentials/idempotency keys/preconditions from one wire request;
- untrusted forwarded metadata can override trusted scheme/authority/client identity;
- routing and authorization can observe different normalized request targets;
- callback signature verification can cover bytes different from those processed as the callback body;
- an ambiguous request can receive `101` realtime upgrade;
- a proxy/cache can accept/cache a request interpretation the owning service would reject or interpret differently.

## Compatibility and evolution

Framing/header/request-target security semantics are part of the security contract even though they are often implemented in infrastructure.

Changing gateway, proxy, HTTP runtime, protocol version or service topology SHALL trigger regression testing of this boundary.

A change that makes ambiguity more permissive or alters security-sensitive header interpretation requires explicit security/compatibility review even when OpenAPI request/response schemas are unchanged.

## Intentionally OPEN

The following remain implementation/profile decisions until evidence requires standardization:

- exact gateway/reverse-proxy product;
- exact HTTP/1.x, HTTP/2 and HTTP/3 deployment mix;
- exact numeric header count/byte limits;
- exact trusted-proxy topology/configuration syntax;
- exact library used to construct the canonical internal request envelope;
- exact rejection status mapping for malformed transport requests where the HTTP stack can safely return one.

These OPENs do **not** make ambiguity acceptance optional. The one-wire-message/one-canonical-interpretation property is normative.