# Capability-Specific Resilience Profiles

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document applies the common Phase 11 semantics to accepted platform capability classes. Endpoint- or Product-specific behavior remains owned by the corresponding accepted contract/profile.

## Control Plane

### Fixed behavior

- Stable already-admitted tenant traffic MAY continue during Control Plane impairment only from a trusted, versioned, unexpired placement/reference path and only when the destination cell independently admits the same tenant/generation.
- Tenant lifecycle, suspension changes, relocation, new placement and other topology/authority changes fail closed without current Control Plane authority.
- A stale positive placement/lifecycle state cannot override a newer local/current deny, retired generation or recovery quarantine.
- Control Plane recovery reconciles post-`R` placement, suspension, revocation and governance state before protected/topology decisions resume.

### OPEN

Cache duration, replication/HA mechanism, regional topology, quorum, failover product and numeric availability targets.

## Cell transactional dependency

- Affected authoritative mutations fail closed when current transactional truth is unavailable.
- Cell failure does not route writes to another cell without an accepted placement/failover authority transition and stale-writer fence.
- Unrelated cells remain available subject to genuinely shared dependencies.
- Recovery starts non-authoritative and passes whole-cell `(R,F]` continuity gates before tenant traffic, schedulers or effectful workers resume.

Database HA product, replica/quorum topology, failover timers, storage sizing and RPO/RTO remain OPEN.

## Security/session/revocation authority

- New protected decisions fail closed when current authority cannot be established.
- Locally verifiable credentials may continue only under an explicitly accepted current-verification profile; cached/stale positive membership or permission is insufficient.
- Revocation/deny generations never regress through failover or restore.
- Reversing a deny is a separate current authorized/audited action, not a reliability fallback.

## Placement/performance/security caches

- Performance cache: bypass only to authoritative truth under stampede protection; otherwise degrade.
- Placement cache: versioned last-known-good within bound and destination admission; never overrides newer generation.
- Security acceleration cache: does not grant authority when freshness/current deny cannot be proved.
- Replay/correctness state: not disposable cache; loss fails closed or advances a trusted invalidating epoch.

Exact cache products, TTLs and invalidation transports remain OPEN.

## Secret/KMS authority

- No plaintext/default secret fallback.
- Only accepted bounded current leases may continue; a stale cached secret cannot defeat revocation/rotation policy.
- Secret outage affects only operations requiring that namespace; service identities remain least-privilege.
- Recovery must restore approved key authority or preserve intentional crypto-erasure.

## External providers and adapters

- Error mapping uses canonical Phase 11 failure classes.
- Timeouts, retry budgets, circuits and concurrency are scoped by tenant/integration/provider/destination as applicable.
- Stored provider-derived state is served only with explicit permitted staleness.
- Provider unavailability cannot create platform-wide retry storms or change canonical domain identity.
- Malformed, oversized, unauthenticated or semantically hostile provider data fails boundedly at the adapter.
- Ambiguous external effects reconcile by stable operation/provider identity.
- A compromised/untrusted provider cannot publish broader platform contract/tenant authority.

Zabbix 7.4 remains one adapter instance; it does not define reliability semantics for the platform.

## Outbox and publication

- Authoritative fact and required outbox commit atomically.
- Broker outage pauses dispatch while durable outbox backlog remains bounded/admitted by policy.
- Retry republishes the same logical message identity and immutable semantic content.
- Publication acknowledgement uncertainty relies on consumer duplicate/content-integrity safety; it does not synthesize a new fact.
- Dispatcher cannot rewrite committed fact/audit evidence.

## Broker/job transport

- Transport availability controls progress, not business truth.
- No acknowledgement before durable consumer responsibility.
- Offset/receipt/visibility state is not canonical effect identity.
- Transport recovery reconciles process/inbox/effect state before progress changes.
- Queue outage/backlog recovery uses workload/tenant budgets and prevents synchronized redelivery collapse.

## Consumers, inbox and quarantine

- One logical executor/effect per trusted scoped message identity when duplicate-sensitive.
- Same identity requires equivalent immutable content; mismatch is integrity failure.
- Co-resident receipt/effect/result commits atomically; cross-authority effect uses stable outcome identity/reconciliation.
- Poison/unsupported work reaches governed quarantine after bounded policy.
- Redrive cannot bypass current authorization, placement, dedup, equivalence, generation or capacity admission.

## Realtime

- Realtime is advisory; authoritative writes and reads remain independent where dependencies permit.
- Gateway/fanout loss causes reconnect/resync, not business-state loss.
- Overload may reject new connections/subscriptions or shed non-authoritative detail under a declared profile.
- Current authorization, replay uniqueness/continuity and placement generation remain mandatory under pressure.
- Stale/revoked/source-retired subscriptions stop; resume/cursor does not restore authority.
- Reconnect storms are isolated and admitted by tenant/principal/connection budgets.

Phase 12 owns connection/health SLIs, signals and alerting; Phase 13 owns runtime/fanout topology.

## Outbound webhooks

Outbound webhook families remain Product-gated. When a profile is accepted:

- originating business fact does not roll back because a destination is slow/down;
- attempts are isolated per tenant/subscription/destination generation;
- same delivery ID retains immutable contract/source/scope/payload meaning and bound destination generation;
- destination change never retargets an old obligation;
- ambiguous attempt reconciles; at-least-once redelivery remains possible only under the original eligible generation;
- retired generation leads to fence/cancel/quarantine or a new caused delivery identity under Product policy;
- SSRF, response-size, redirect, concurrency and secret rules remain mandatory.

Exact signature, egress mechanism, retry numerics and Product cancellation/reissue policy remain OPEN.

## Artifacts and object storage

- Transactional metadata/generation remains release authority; object presence alone is not availability.
- Upload/finalize, delivery lease and erasure use accepted generation/fencing semantics.
- Storage outage leaves explicit preparing/unavailable/reconciliation state; no false ready/erased success.
- Download/release rechecks current authorization/releasability and generation before protected bytes.
- Active streams and late lease admission are reconciled/fenced before confirmed erasure.
- Object/metadata mismatch is unavailable/quarantined, never guessed.
- Legal hold/governance uncertainty blocks destructive deletion; erasure uncertainty blocks re-exposure.

## Telemetry plane

- Telemetry pressure/outage cannot exhaust transactional core.
- Ingest buffering is bounded and durable only where the accepted telemetry contract requires it.
- Drop/gap/backpressure behavior is explicit by data class; missing telemetry is not fabricated completeness.
- Ordering/dedup identity is scoped by trusted tenant/integration/source/generation.
- Current-state transitions and required signals retain accepted atomic/recoverable advancement semantics.
- Raw volume is not forced through the general event broker.

Exact telemetry store, buffer, retention and loss thresholds remain OPEN.

## Reporting, AIOps and derived workloads

- Separate pool/queue/concurrency from core transactional and security/recovery work.
- May delay, shed or enter brownout when Product contract permits.
- Cannot silently become authority for identity, authorization, tenant placement, retry/recovery eligibility, release or incident closure.
- Derived rebuilds use isolated generation and cannot erase production dedup/current projection truth.

## Automation, parsers, SQL, admin, migration and recovery

- Use smaller trust envelopes, explicit target scope, resource/time/output/egress bounds and current authority.
- Dangerous execution does not share the primary API worker pool or unrestricted credentials.
- Timeout/termination does not prove external/destructive effect absence.
- Recovery/admin priority cannot bypass tenant, audit, governance or idempotency gates.
- A generic platform admin/network position is not unrestricted cross-tenant authority.

Phase 13 defines runtime isolation mechanisms; Phase 15 defines runbook/break-glass procedure.

## Cell/region failure preparation

- Cell is the normal operational blast-radius unit.
- Second-cell addition does not change API/event/business identities.
- Cell failure/failover/relocation uses current placement generation, source fencing and target admission.
- Regional hierarchy, active-active/passive and residency topology remain OPEN until Product/compliance/capacity evidence.
- No contract assumes global synchronous dependency merely for convenience.

