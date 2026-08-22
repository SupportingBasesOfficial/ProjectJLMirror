# Phase 12 — Correlation and Context Propagation

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE  
**Primary upstream authority:** ADR-014, Phase 09 request/correlation contracts, Phase 10 message envelope, Phase 11 reliability/recovery semantics

## Purpose

This document defines how diagnostic context survives important JLMIRROR boundaries without becoming trust, authority or an unbounded correlation oracle.

## Identity roles

Correlation uses distinct identifiers with distinct meaning:

| Identifier | Meaning |
|---|---|
| `trace_id` / `span_id` | distributed execution trace context |
| `request_id` | server-generated identity of one accepted request handling attempt |
| `correlation_id` | bounded workflow/business diagnostic correlation context |
| `operation_id` | stable durable long-running/reconcilable operation identity where accepted upstream |
| `causation_id` | identity of the immediate logical cause when the contract defines one |
| `message_id` | Phase 10 logical message identity within its trusted scope |
| `delivery_id` | delivery-attempt/obligation identity where the specialized contract defines one |
| `replay_id` | identity of a replay/redrive execution context; historical message identity remains unchanged |
| `recovery_operation_id` | recovery/reconciliation operation identity |
| generation/fence reference | diagnostic reference to accepted authority generation/fence; never the authority itself |

No one identifier substitutes for another merely because they happen to share a value.

## Request boundary

Every normal API/BFF request retains the accepted server-generated `request_id`. A client correlation value is validated and bounded before becoming the effective correlation ID. Client-supplied trace context MAY be accepted under a strict profile but does not grant tenant/resource authority and may be replaced when malformed or unsafe.

Before trusted tenant context exists, telemetry SHALL NOT label the request with a caller-asserted tenant identity as authoritative tenant context.

## Async boundary

When a request/use case produces an outbox message/job:

- the new message keeps its own Phase 10 `message_id`;
- accepted `correlation_id` propagates when relevant;
- `causation_id` points to the immediate accepted cause where defined;
- trace context MAY continue or a new linked trace MAY begin according to the tracing profile;
- no consumer treats correlation/trace context as authorization, deduplication scope or retry eligibility.

Redelivery keeps the logical message identity and may create a new processing span/attempt identity. Reusing a trace span as a business deduplication identity is prohibited.

## Provider/integration boundary

Outbound provider calls propagate only safe supported context. Internal tenant/principal identifiers SHALL NOT be disclosed to a provider merely for diagnostic convenience.

Provider-native request IDs may be recorded as adapter diagnostic correlation, bounded and classified, but never replace JLMIRROR operation/resource identity.

For callbacks, provider-supplied correlation fields remain untrusted until the specialized callback authentication/canonicalization boundary succeeds. They do not select tenant or replay scope.

## Realtime boundary

Realtime connection/subscription admission remains owned by Phase 09. Observability records connection/subscription/resync lifecycle using safe connection/session diagnostic identities. An open socket or trace continuity never freezes authorization.

Messages projected to realtime retain only the correlation fields allowed by their protocol/classification profile. Internal trace detail need not be exposed to browser clients.

## Webhook boundary

Outbound webhook observability distinguishes:

```text
webhook logical event/message identity
webhook_delivery_id
attempt identity
destination generation
```

Destination changes do not rewrite historical delivery identity. Correlation telemetry cannot authorize a retry when the delivery contract says the external effect is ambiguous.

## Recovery and replay

Recovery/replay diagnostics SHALL preserve the distinction between:

- original historical identity;
- new replay/recovery execution identity;
- current authority generation/fence;
- restored evidence state;
- reconciliation outcome.

A missing trace after restore is evidence loss, not proof the original effect was absent. Replayed work must remain visible as replay/recovery context so operators do not mistake it for first execution.

## Baggage/propagated attributes

Generic distributed-tracing baggage is deny-by-default for protected/high-cardinality data. Any propagated field requires an allowlisted semantic profile with:

- source/trust level;
- maximum size/count;
- classification;
- hop scope;
- whether it may leave JLMIRROR;
- cardinality implications;
- redaction behavior.

Secrets, credentials, raw authorization tokens, cookies, private keys, raw protected URLs/queries, cursor payloads and one-time capabilities SHALL NOT be propagated as telemetry baggage.

## Cross-tenant oracle prevention

Observability query/access layers SHALL enforce the same logical tenant separation required by accepted security authority. Correlation identifiers SHALL NOT provide a public/global lookup oracle into another tenant's traces, logs or operational events.

A privileged cross-tenant diagnostic operation, if later implemented, is a distinct audited administrative capability with explicit scope; it is not an implicit wildcard query.

## Broken propagation

Broken trace/correlation propagation is observable itself. Where a required boundary cannot continue a context:

- the child evidence records a bounded `propagation_break` class/reason where safe;
- the system does not fabricate a parent;
- diagnostic reconstruction can fall back to stable request/operation/message/delivery identities;
- missing propagation is a validation finding for critical flows.

## Validation obligations

Synthetic tests SHALL cover request -> persistence -> outbox/job -> worker -> provider -> event -> notification/realtime paths, including duplicate delivery, callback, replay and recovery cases. Tests must prove both continuity where required and non-authority of all correlation inputs.
