# Phase 13 — Stateful Dependency and Data-Plane Ports

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines the logical runtime ports through which JLMIRROR reaches durable or specialized state. Ports preserve accepted ownership and failure semantics while keeping storage/broker/cache/vendor products replaceable.

A port is an architectural capability contract, not a vendor SDK.

## Port taxonomy

| Port | Authority / purpose | Runtime rules |
|---|---|---|
| `port.control-placement@1` | tenant/cell registry, placement/lifecycle authority | Control Plane-owned; trusted version/generation; ordinary callers cannot write physical placement |
| `port.transactional@1` | tenant business transactional truth | application-owned transactions; tenant/data-layer isolation; no cross-cell distributed mutation |
| `port.reliability-state@1` | inbox/outbox/idempotency/replay/reconciliation/fence state | preserves Phase 10/11 effect/ambiguity continuity; absence after restore is not effect absence |
| `port.audit@1` | immutable/protected accountability evidence or durable audit intent | ordinary runtime cannot mutate/delete protected evidence; separate from logs |
| `port.customer-telemetry@1` | customer monitoring durable observations/projections | distinct from platform observability; tenant/ordering semantics preserved |
| `port.artifact@1` | protected artifact bytes/lifecycle integration | bytes never become releasable solely from upload; metadata/generation/lease governance controls release |
| `port.ephemeral@1` | cache/ephemeral coordination/performance state | non-authoritative unless a specialized accepted replay/coordination authority explicitly says otherwise |
| `port.job-event-transport@1` | durable delivery/transport | at-least-once transport; ACK after durable responsibility; broker identity != business identity |
| `port.observability@1` | logs/metrics/traces/operational evidence | Phase 12 semantics; telemetry != business/security/recovery authority |
| `port.secret-key@1` | secret/key/verifier authority | workload-scoped references; currentness/rotation/revocation; secret values excluded from ordinary state |
| `port.object-staging@1` | temporary/staged artifact/object transfer where used | non-authoritative until owning lifecycle metadata reaches verified terminal state |

## Ownership rule

Physical co-location does not merge logical ownership. A database cluster containing several logical schemas or stores does not allow one bounded context/runtime to mutate another owner's state directly.

The application/runtime profile receives only the port capabilities it needs. A universal database/storage credential is prohibited as the normal serving identity.

## Transactional port

`port.transactional@1` SHALL support:

- tenant-scoped connection/transaction context derived from trusted TenantContext;
- local transaction semantics required by application use cases;
- same-transaction mutation + audit intent/outbox where accepted;
- separation between serving application role and schema/migration owner;
- restoration/recovery hooks that do not bypass current authority reconciliation.

Connection endpoint, database product, pooler and physical schema layout remain OPEN where not already accepted.

## Reliability-state port

This port is correctness-sensitive. It stores/serves durable evidence required for:

- API idempotency;
- consumer inbox/equivalence;
- outbox publication identity;
- replay consumption/epochs;
- operation/reconciliation outcomes;
- recovery fences and continuity evidence where owned here.

A cache or broker delivery guarantee cannot silently replace this port's business-correctness obligations.

## Ephemeral/coordination port

Default use is performance and coordination. Values may be lost without becoming business truth.

If a capability requires stronger authority — such as single-winner replay consumption or a lease/fence — its specific authority/durability/currentness contract must be explicit. Calling a product "cache" does not make an authority ephemeral; calling a product "database" does not make every value authoritative.

## Broker/job-event transport

The runtime transport must support the accepted Phase 10/11 semantics but exact product/topic/partition/ack primitive remains OPEN.

Required runtime properties:

- bounded message size and workload isolation;
- delivery metadata does not create tenant/placement authority;
- redelivery/lease expiry/process death do not prove prior effect absence;
- transport backlog is observable and bounded;
- poison/unsupported work remains discoverable/quarantinable;
- replay uses accepted identity/dedup semantics rather than transport reset as business replay authority.

## Artifact/object port

Runtime access follows accepted artifact lifecycle, delivery-generation, active-stream/lease and erasure/legal-hold fences.

Direct object-store capability alone cannot authorize protected release. Serving runtimes do not receive unrestricted bucket/account owner credentials.

## Customer telemetry vs observability ports

`port.customer-telemetry@1` and `port.observability@1` remain distinct even if one physical product later serves both.

Failure of platform observability does not redefine customer telemetry durable-acceptance semantics; customer telemetry existence does not replace platform diagnostic evidence.

## Port currentness and generation

Where a port's authority can become stale/security-sensitive, runtime evidence identifies an accepted configuration/authority generation sufficient to detect stale bindings.

A restored runtime SHALL NOT reconnect to an obsolete port endpoint/credential/generation and treat it as current merely because connectivity succeeds.

## Failure and degradation

Every port maps to one or more accepted Phase 11 reliability profiles and Phase 12 health/observability bindings. Phase 13 specifies how runtimes attach to the port; it does not change retry eligibility, fail-closed behavior or reconciliation requirements.

## Portability rule

Vendor migration is valid only when the replacement preserves:

- authority/durability meaning;
- tenant isolation;
- transaction/atomicity semantics;
- failure/ambiguity behavior;
- generation/fencing/recovery continuity;
- security/secret boundaries;
- Phase 12 signal/health meaning.

A compatible SDK or wire protocol alone is insufficient evidence of semantic portability.