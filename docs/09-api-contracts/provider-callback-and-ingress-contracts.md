# Provider Callback and Ingress Contracts

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

Provider callbacks/webhooks are external untrusted ingress contracts. They are not ordinary tenant API routes and do not inherit tenant authority from payload fields.

This document defines the stable JLMIRROR ingress boundary while allowing each provider adapter to implement its required signature/certificate/token protocol.

## Namespace

Where a generic platform prefix is applicable, callback routes use:

```text
/callbacks/v1/<provider-profile>/<opaque-callback-or-integration-reference>
```

Some providers may require a provider-mandated path shape. Such exceptions remain adapter-owned and SHALL preserve the same trust/size/replay/tenant-binding invariants.

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

The ingress SHALL enforce a hard raw transport byte limit before complete buffering or expensive signature/authentication/parsing work.

`Content-Length` MAY permit early rejection but is not trusted as the only bound. Chunked/streamed input is counted and terminated when it exceeds the accepted raw-body limit.

Provider profiles define a concrete maximum raw-body size before implementation/release. If not yet measured/accepted, the value is explicitly `OPEN`; unlimited callback bodies are prohibited.

## Authentication/freshness ordering

Conceptual processing:

```text
network/route admission
  -> hard raw byte bound while reading
  -> obtain bounded raw representation
  -> provider/integration lookup from trusted route/config
  -> verify provider authenticity mechanism
  -> verify timestamp/freshness/nonce/event identity where protocol supports it
  -> enforce replay/dedup admission for harmful duplicate effects
  -> only then parse/decompress/normalize semantic payload
  -> apply bounded parsed/decompressed complexity limits
  -> resolve owning domain use case
  -> authoritative mutation / operation contract
```

The exact cryptographic verification sequence may depend on a provider that requires the untouched raw bytes. The adapter preserves those raw bytes inside the accepted limit.

## Post-auth parse/decompression limits

Authentication does not make the payload safe to parse without bounds.

After authenticity/freshness checks, adapters enforce independent limits for:

- decompressed byte size;
- JSON/XML/object nesting depth;
- collection item count;
- field/string size;
- archive/member count where accepted;
- parser execution/resource budget.

A small authenticated compressed body is not allowed to expand without bound.

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

Callback errors are intentionally sparse. They SHALL NOT expose tenant existence, internal stack traces, signature comparison detail, secret references or physical topology.

Provider profiles MAY require specific status codes to control retry behavior. Such mapping is documented per provider and cannot turn an unsafe/ambiguous effect into blind re-execution.

## Rate/abuse protection

Callback ingress supports independent protection by:

- provider/integration identity;
- source network/profile where safe;
- endpoint;
- tenant after trusted resolution;
- body/parse cost;
- concurrency.

A noisy/compromised provider integration SHALL NOT consume unbounded global capacity.

## SSRF distinction

Inbound callback processing SHALL NOT automatically fetch arbitrary URLs contained in callback payloads.

If the provider contract requires follow-up retrieval, that retrieval uses the accepted outbound connector boundary with destination/protocol/redirect/size/timeout policy and trusted provider configuration.

## Secrets/logging

Callback headers, signatures, tokens and raw payloads are classified. Normal logs SHALL NOT record credentials/signature secrets or unrestricted raw payloads.

Safe telemetry records callback profile, trusted integration/tenant identity, provider event ID hash/reference where appropriate, validation outcome, latency and correlation without leaking secret/regulated content.

## Versioning

Provider callback profiles version independently from the canonical domain API. A provider protocol change may add `/callbacks/v2` or provider-specific version handling without requiring `/api/v2` for JLMIRROR resources.

The adapter normalizes multiple supported provider protocol versions into stable platform-owned application/domain contracts.

## Testing

Every callback profile SHALL test:

- over-limit chunked body rejected before complete buffering/authentication;
- invalid authentication/signature rejected;
- stale timestamp/nonce/event replay rejected/deduplicated as appropriate;
- tenant/integration payload forgery cannot reroute trusted tenant context;
- post-auth parser/decompression expansion is bounded;
- exact duplicate does not repeat protected effect;
- same provider-local event ID in two trusted identity scopes is independently processable;
- process crash after durable acceptance does not lose callback work;
- process crash before durable acceptance does not return false success;
- provider outage/follow-up fetch failure remains isolated to the integration/workload.