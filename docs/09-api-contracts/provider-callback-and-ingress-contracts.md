# Provider Callback and Ingress Contracts

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

Provider callbacks/webhooks are external untrusted ingress contracts. They are not ordinary tenant API routes and do not inherit tenant authority from payload fields.

This document defines the stable JLMIRROR ingress boundary while allowing each provider adapter to implement its required signature/certificate/token protocol.

## Canonical HTTP ingress

Every callback profile inherits `http-message-framing-and-canonicalization.md` before signature/freshness/replay/domain processing.

The platform first establishes one unambiguous HTTP request framing/header/request-target interpretation. Ambiguous `Content-Length`/`Transfer-Encoding`, multiple conflicting body lengths, malformed transfer framing, conflicting authority, or duplicate/conflicting provider security headers without an explicit canonical rule fail closed.

If a provider signature protocol signs the raw request body, verification uses the exact bounded raw body bytes associated with the already accepted framing. A gateway, adapter and downstream processor SHALL NOT verify one byte sequence while normalizing/parsing another as the callback body.

Provider authentication/signature/timestamp/nonce headers declare explicit cardinality semantics. Competing values are rejected rather than selected by first/last/framework behavior.

## Namespace

Where a generic platform prefix is applicable, callback routes use:

```text
/callbacks/v1/<provider-profile>/<opaque-callback-or-integration-reference>
```

Some providers may require a provider-mandated path shape. Such exceptions remain adapter-owned and SHALL preserve the same framing/trust/size/replay/tenant-binding invariants.

No callback URI contains a database address, cell ID, secret value or other physical placement authority.

## Opaque callback reference

A callback path MAY contain an opaque reference used to locate the configured integration. That reference is lookup input, not sufficient authentication by itself.

Possession of a callback URL SHALL NOT automatically grant mutation authority unless an explicitly reviewed provider protocol defines the URL secret itself as one factor and the security requirements accept that model.

## Tenant binding

The adapter resolves `tenant_id` and integration/source identity from trusted configured integration state after locating/authenticating the callback.

Payload fields such as:

```json
{
  "tenant_id": "...",
  "account": "...",
  "organization": "..."
}
```

are treated as untrusted provider data unless independently matched to trusted configuration. They cannot reroute the callback to another tenant.

## Raw-body hard limit

After canonical framing admission establishes which bytes belong to this request body, ingress SHALL enforce a hard raw transport byte limit while reading and before complete buffering or expensive signature/authentication/parsing work.

`Content-Length` MAY permit early rejection but is not trusted as the only bound. Chunked/streamed input is counted and terminated when it exceeds the accepted raw-body limit.

Ambiguous framing is rejected before the adapter treats any body as authentic callback input; the hard raw bound cannot be bypassed by making different hops disagree about where the body ends.

Provider profiles define a concrete maximum raw-body size before implementation/release. If not yet measured/accepted, the value is explicitly `OPEN`; unlimited callback bodies are prohibited.

## Authentication/freshness/replay ordering

Conceptual processing:

```text
network/protocol admission
  -> canonical HTTP framing/header/request-target admission
  -> hard raw byte bound while reading the accepted body
  -> obtain bounded exact raw representation
  -> provider/integration lookup from trusted route/config
  -> verify provider authenticity mechanism over the required exact representation
  -> verify timestamp/freshness/nonce where available outside semantic parsing
  -> bounded minimal extraction/parse only if required to establish trusted event/replay identity
  -> enforce replay/dedup admission before protected logical effect
  -> bounded full parse/decompress/normalize semantic payload
  -> resolve owning domain use case
  -> authoritative mutation / operation contract
```

The exact cryptographic verification sequence may depend on a provider that requires untouched raw bytes. The adapter preserves those exact accepted raw bytes inside the hard limit.

HTTP framing/header canonicalization does not rewrite the signed body. It only ensures every hop agrees which bounded bytes constitute that body and which single security-header values/profile apply.

If replay identity is carried inside the authenticated body, the adapter MAY perform only the minimum parsing/decompression needed to extract that identity before replay admission. That extraction is itself subject to explicit byte/depth/item/parser limits and SHALL NOT execute domain behavior, follow URLs or allocate unbounded structures.

A provider profile SHALL NOT weaken replay protection merely because event identity requires bounded parsing; duplicate admission still occurs before the protected logical effect.

## Post-auth parse/decompression limits

Authentication does not make the payload safe to parse without bounds.

After authenticity/freshness checks, all parsing/decompression—including any minimal replay-identity extraction—enforces independent limits for:

- decompressed byte size;
- JSON/XML/object nesting depth;
- collection item count;
- field/string size;
- archive/member count where accepted;
- parser execution/resource budget.

A small authenticated compressed body is not allowed to expand without bound.

## XML and active parser features

Provider authenticity does not make XML parser features trustworthy. Any callback profile that accepts XML or an XML-derived format SHALL use an explicitly hardened parser profile.

By default, the callback parser SHALL disable or reject:

- DTD processing where it can introduce entity or external-resource behavior;
- general and parameter external entities;
- external entity resolution against local files, network URLs or platform resources;
- XInclude processing;
- external schema/stylesheet/resource resolution;
- parser features that perform implicit network/file retrieval or code/script execution.

If a provider contract genuinely requires a schema/catalog or another external-looking dependency, the accepted profile SHALL use a pinned/trusted local resource or an explicitly isolated resolver with deny-by-default file/network access, strict allowlisting and bounded resource usage. Provider-controlled URIs SHALL NOT become resolver authority.

XML parser selection/configuration is security-sensitive contract metadata for profiles that accept XML. A framework/library upgrade SHALL NOT silently re-enable active XML features.

The same principle applies to other structured formats with equivalent active resolution/include/import behavior: external resource resolution is deny-by-default unless a separately accepted bounded resolver profile proves necessity and isolation.

## Replay identity

Where a provider supplies a trustworthy stable event/callback ID, the adapter defines a canonical trusted identity scope including all dimensions needed to avoid cross-tenant/source collisions.

Conceptual identity:

```text
callback_identity_scope + provider_event_id
```

The same raw provider event ID from two different authoritative integrations/tenants/sources SHALL NOT suppress one another.

If no safe provider-native identity exists, the adapter establishes an accepted platform operation/observation identity according to the owning contract.

## Callback acknowledgement

A successful HTTP callback response means only what the provider profile documents.

Preferred semantics distinguish:

- callback authenticated/validated and durably accepted for later processing;
- callback fully processed synchronously;
- duplicate callback safely recognized;
- callback rejected permanently;
- callback temporarily unavailable before safe acceptance.

The adapter SHALL NOT return a success code merely to stop provider retries if the platform has neither completed nor durably accepted the required logical work.

A request rejected by canonical HTTP ingress never creates a false durable-acceptance or idempotency/replay state merely because a downstream parser would have accepted one interpretation.

## Durable acceptance

If callback processing will continue asynchronously, success acknowledgement requires a durable acceptance record/outbox/job/observation boundary that survives process crash.

A callback received only in process memory is not durably accepted.

## Duplicate behavior

Duplicate/replayed callbacks do not repeat irreversible logical effects.

The adapter/owner uses the accepted inbox/idempotency/observation-identity protocol appropriate to the callback type.

Provider retry frequency does not weaken the platform's durable deduplication window required for correctness.

## Weakly authenticated providers

If a provider cannot securely authenticate callbacks, the integration requires an explicit weaker-trust design.

Preferred fallback pattern:

```text
untrusted callback
  -> bounded trigger/hint only
  -> authenticated outbound provider read/reconciliation
  -> normalized current authoritative provider state
  -> owning-domain mutation
```

An unauthenticated callback does not become a trusted command merely because the provider documentation says webhooks are convenient.

## Error responses

Callback errors are intentionally sparse. They SHALL NOT expose tenant existence, internal stack traces, signature comparison detail, secret references, physical topology or which intermediary/parser would have accepted an ambiguous transport interpretation.

Provider profiles MAY require specific status codes to control retry behavior. Such mapping is documented per provider and cannot turn an unsafe/ambiguous effect into blind re-execution.

## Rate/abuse protection

Callback ingress supports independent protection by:

- provider/integration identity;
- source network/profile where safe;
- endpoint;
- tenant after trusted resolution;
- body/parse cost;
- header/framing cost;
- concurrency.

A noisy/compromised provider integration SHALL NOT consume unbounded global capacity.

## SSRF distinction

Inbound callback processing SHALL NOT automatically fetch arbitrary URLs contained in callback payloads.

If the provider contract requires follow-up retrieval, that retrieval uses the accepted outbound connector boundary with destination/protocol/redirect/size/timeout policy and trusted provider configuration.

XML/XInclude/schema/entity resolution is not an exception to this rule. Parser-level external retrieval is disabled by default and cannot bypass the connector/SSRF boundary.

## Secrets/logging

Callback headers, signatures, tokens and raw payloads are classified. Normal logs SHALL NOT record credentials/signature secrets or unrestricted raw payloads.

Safe telemetry records callback profile, trusted integration/tenant identity, provider event ID hash/reference where appropriate, validation outcome, latency and correlation without leaking secret/regulated content.

Framing/header rejection telemetry records only a safe rejection class such as `framing_conflict` or `duplicate_security_header`; it does not log competing signature/token values or unrestricted malicious payload bytes.

## Versioning

Provider callback profiles version independently from the canonical domain API. A provider protocol change may add `/callbacks/v2` or provider-specific version handling without requiring `/api/v2` for JLMIRROR resources.

The adapter normalizes multiple supported provider protocol versions into stable platform-owned application/domain contracts.

Changing callback gateway/proxy/runtime or HTTP-version translation SHALL NOT alter which exact raw body/security-header meaning the provider profile authenticates. Such infrastructure changes trigger the canonical HTTP ingress regression tests.

## Testing

Every callback profile SHALL test:

- conflicting `Content-Length`/`Transfer-Encoding`, multiple differing lengths or malformed framing rejected before signature/domain processing;
- gateway/adapter signature verification and semantic processing observe the same exact bounded raw body;
- duplicate/conflicting provider signature/auth/timestamp/nonce headers fail closed unless the provider profile defines one canonical protocol rule;
- untrusted forwarded/authority metadata cannot reroute or alter trusted callback security context;
- over-limit chunked/streamed body rejected before complete buffering/authentication;
- invalid authentication/signature rejected;
- stale timestamp/nonce/event replay rejected/deduplicated as appropriate;
- bounded minimal replay-identity extraction cannot cause unbounded decompression/parser work or domain side effects;
- tenant/integration payload forgery cannot reroute trusted tenant context;
- post-auth parser/decompression expansion is bounded;
- XML profiles reject DTD/external general or parameter entities, XInclude and external schema/stylesheet/resource resolution by default;
- XML/local-file entity attempts cannot read host/runtime files;
- XML/network entity/include/schema attempts cannot reach metadata services, loopback/private control endpoints or arbitrary external URLs;
- any accepted resolver profile proves deny-by-default file/network policy, allowlisted trusted resources and bounded execution;
- exact duplicate does not repeat protected effect;
- same provider-local event ID in two trusted identity scopes is independently processable;
- process crash after durable acceptance does not lose callback work;
- process crash before durable acceptance does not return false success;
- callback-supplied URLs cannot bypass trusted outbound destination/redirect/size/timeout policy;
- provider outage/follow-up fetch failure remains isolated to the integration/workload.