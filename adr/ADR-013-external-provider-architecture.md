# ADR-013 — External Provider Adapter Architecture

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible if domain ports remain stable

## Context

Monitoring, ITSM, payment, identity and notification systems are outside the platform trust boundary. Provider outages/payloads must not define JLMIRROR availability or ubiquitous language. Tenant-configured URLs can create SSRF risk. Inbound callbacks/webhooks add a separate risk: structurally valid input is not proof of provider authenticity or message freshness, and replay can duplicate side effects.

Drivers: `FR-MON-001..002`, `FR-ITSM-005`, `FR-ID-003`, `FR-COM-002`, `INV-EXT-*`, `INV-ASYNC-001`, `SEC-INT-*`, `QA-AVAIL-001`, `TM-005`, `TM-006`, `TM-011`.

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

Where the provider supports an authentication/signature protocol, the adapter MUST:

- verify the provider-defined signature/MAC/certificate/authentication mechanism before accepting domain effects;
- preserve/use the exact raw request representation when required by the provider signing scheme;
- bind verification to the expected integration/tenant configuration rather than trusting a caller-supplied `tenant_id` or provider identity;
- enforce timestamp/nonce/event-ID freshness semantics provided by the protocol, including a bounded accepted clock-skew window when timestamps are used;
- persist or otherwise durably recognize replay/deduplication identifiers when replay could cause a side effect;
- reject invalid/expired authentication before domain mutation;
- validate payload schema, size and semantics after authenticity checks and then normalize into platform-owned contracts.

If a provider cannot offer a callback authentication mechanism strong enough for the feature threat model, a callback MUST NOT silently gain full trusted-command authority. The integration must instead use an explicitly reviewed weaker-trust design—for example treating the callback as a hint followed by an authenticated provider read/reconciliation—or obtain an explicit feature-specific security decision/RFC documenting the residual risk.

Inbound callback processing assumes at-least-once/replay is possible. Side effects follow stable operation/event identity and idempotency/deduplication rules from ADR-008/009/010 as applicable.

Initial Monitoring Source support MAY include Zabbix, but Zabbix concepts SHALL NOT become the only canonical Monitoring model.

## Consequences

### Positive
- provider replacement/addition does not rewrite domain rules;
- resilience/security controls are concentrated at trust boundary;
- provider failure can be isolated by tenant/provider;
- forged or replayed callbacks cannot rely on schema validity alone to obtain authority.

### Negative / cost
- adapter normalization adds mapping code;
- callback signature/replay handling is provider-specific;
- provider-specific capabilities may require explicit extension points rather than leaking native models.

## Validation

Contract/security tests include malformed/oversized payloads, timeout, auth failure, redirect/SSRF attempts, provider outage, invalid callback signature, stale timestamp/nonce and duplicate callback/event ID.

A validly shaped but unauthenticated callback MUST NOT cause a protected domain mutation where provider authentication is required. Replaying an already accepted callback MUST NOT repeat an irreversible logical effect. Verify one tenant provider failure does not block unrelated tenants.

## Exit / revisit conditions

A provider may receive a specialized service/runtime if independent scale or SDK/runtime requirements justify extraction under ADR-020. Callback trust requirements may be specialized per provider only through an explicit feature/security decision that preserves `SEC-INT-003` or documents an accepted exception.
