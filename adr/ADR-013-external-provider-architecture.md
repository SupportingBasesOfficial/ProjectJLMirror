# ADR-013 — External Provider Adapter Architecture

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible if domain ports remain stable

## Context

Monitoring, ITSM, payment, identity and notification systems are outside the platform trust boundary. Provider outages/payloads must not define JLMIRROR availability or ubiquitous language. Tenant-configured URLs can create SSRF risk. Inbound callbacks/webhooks add a separate risk: structurally valid input is not proof of provider authenticity or message freshness, replay can duplicate side effects, and an oversized unauthenticated body can exhaust memory/bandwidth/verification CPU before signature validation.

Drivers: `FR-MON-001..002`, `FR-ITSM-005`, `FR-ID-003`, `FR-COM-002`, `INV-EXT-*`, `INV-ASYNC-001`, `SEC-INT-*`, `SEC-ABUSE-*`, `QA-AVAIL-001`, `TM-005`, `TM-006`, `TM-011`.

## Decision

Every external provider SHALL be implemented behind a platform-owned port/adapter contract. Provider-native payloads are authenticated where applicable, validated, bounded and normalized before entering owning domains.

### Outbound connector requirements

Connector execution SHALL define:

- connect/request/overall timeouts;
- retryability categories and bounded retry;
- provider/tenant rate limits where applicable;
- circuit-breaker/degraded-state policy;
- SSRF/egress policy and protocol/destination restrictions;
- response/body size limits;
- credential secret references and least privilege;
- correlation/audit/metrics without secret leakage;
- external-ID mapping separate from internal platform identity.

### Inbound callbacks/webhooks

Inbound provider callbacks are untrusted until their provider/installation identity and freshness have been established.

Before buffering the complete body or performing provider signature/authentication work, the ingress/gateway SHALL enforce a hard raw transport-body byte limit. A declared `Content-Length` MAY be used for early rejection but is not trusted as the sole control; the receiver must maintain a streaming/transport-enforced byte bound and terminate/reject once the limit is exceeded. This raw limit applies even when the signature covers the exact raw body.

After the raw body is bounded, where the provider supports an authentication/signature protocol, the adapter MUST:

- verify the provider-defined signature/MAC/certificate/authentication mechanism before accepting domain effects;
- preserve/use the exact bounded raw request representation when required by the provider signing scheme;
- bind verification to the expected integration/tenant configuration rather than trusting a caller-supplied `tenant_id` or provider identity;
- enforce timestamp/nonce/event-ID freshness semantics provided by the protocol, including a bounded accepted clock-skew window when timestamps are used;
- persist or otherwise durably recognize replay/deduplication identifiers when replay could cause a side effect;
- reject invalid/expired authentication before domain mutation.

Only after authenticity/freshness succeeds does the adapter parse/decompress/validate provider payload semantics. Parser/decompression/output limits are independently bounded so a small compressed or authenticated body cannot expand without limit. The normalized platform contract is produced only after schema, semantic and post-auth size constraints pass.

If a provider cannot offer a callback authentication mechanism strong enough for the feature threat model, a callback MUST NOT silently gain full trusted-command authority. The integration must instead use an explicitly reviewed weaker-trust design—for example treating the callback as a hint followed by an authenticated provider read/reconciliation—or obtain an explicit feature-specific security decision/RFC documenting the residual risk.

Inbound callback processing assumes at-least-once/replay is possible. Side effects follow stable operation/event identity and idempotency/deduplication rules from ADR-008/009/010 as applicable.

Initial Monitoring Source support MAY include Zabbix, but Zabbix concepts SHALL NOT become the only canonical Monitoring model.

## Consequences

### Positive
- provider replacement/addition does not rewrite domain rules;
- resilience/security controls are concentrated at trust boundary;
- provider failure can be isolated by tenant/provider;
- forged or replayed callbacks cannot rely on schema validity alone to obtain authority;
- unauthenticated oversized callback bodies are rejected before expensive full-body/signature work.

### Negative / cost
- adapter normalization adds mapping code;
- callback signature/replay/size handling is provider-specific;
- ingress and parser limits must be coordinated with legitimate provider maximum payloads;
- provider-specific capabilities may require explicit extension points rather than leaking native models.

## Validation

Contract/security tests include malformed/oversized payloads, missing/false `Content-Length`, chunked/streamed over-limit bodies, decompression expansion, timeout, auth failure, redirect/SSRF attempts, provider outage, invalid callback signature, stale timestamp/nonce and duplicate callback/event ID.

A validly shaped but unauthenticated callback MUST NOT cause a protected domain mutation where provider authentication is required. An oversized raw callback MUST be rejected before complete buffering/signature processing. Replaying an already accepted callback MUST NOT repeat an irreversible logical effect. Verify one tenant provider failure does not block unrelated tenants.

## Exit / revisit conditions

A provider may receive a specialized service/runtime if independent scale or SDK/runtime requirements justify extraction under ADR-020. Callback trust requirements may be specialized per provider only through an explicit feature/security decision that preserves `SEC-INT-003/004` or documents an accepted exception.
