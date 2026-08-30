# Implementation Readiness — Initial Implementation Sequencing

**Status:** proposed gate baseline; post-D2 operational state reconciled by `18-d2-track-b-acceptance-propagation.md`

## Principle

Implementation sequence follows accepted authority and dependency structure, not framework convenience. A later slice cannot force an earlier contract to change merely because scaffolding exists.

## Wave 0 — Conformance substrate

`impl.contract-tooling@1`

Build the repository-local implementation conformance substrate first:

- exact profile/catalog IDs as code-visible generated/static contracts;
- API/event schema generation and compatibility checks;
- deterministic assurance integration for implementation code;
- test harnesses for tenant/current-authority, idempotency, ambiguity, fencing and recovery vectors;
- no Product-facing feature activation.

C2 tooling may be selected through bounded evidence while reviewed documents remain canonical.

## Wave 1 — Identity and authority skeleton

- `impl.identity-bff@1`
- `impl.control-plane@1`
- minimal `impl.platform-runtime@1`

Prerequisite: IR-D-001/002/003 accepted.

Deliver only the authority skeleton necessary for later slices:

- BFF/session/authentication boundaries;
- machine/workload identity;
- TenantContext/current authorization adapters;
- placement/currentness/fence primitives;
- config/secret-reference contracts;
- no invention of domain endpoints beyond accepted Product contracts.

## Wave 2 — Transactional cell and async correctness substrate

- `impl.cell-data-runtime@1`
- `impl.async-core@1`

Implement:

- accepted transactional business/data authority patterns;
- outbox/inbox/idempotency/reconciliation primitives;
- generation-aware worker contracts;
- quarantine/redrive authority hooks;
- reliability profile hooks and observability context.

Transport/database/cache products remain C2 choices selected through conformance evidence.

## Wave 3 — Platform observability and release chain

- `impl.observability@1`
- `impl.release-supply-chain@1`

Implement instrumentation/health semantics before dependent feature rollout and establish:

- immutable build/artifact identity;
- source trust separation;
- provenance/evidence records;
- deployment-operation fencing;
- runtime artifact/config verification;
- non-production environment mapping.

This wave does not claim production numerics or readiness.

## Wave 4 — Product/domain vertical slices

A Product/domain vertical slice may start only when its exact endpoint/event/data/authority contracts exist and a separate explicit implementation-authorization gate grants that slice.

Typical first vertical slice composition:

```text
Product use case
 -> API endpoint contract
 -> transactional use case/data authority
 -> outbox/event contracts if applicable
 -> worker/provider adapter if applicable
 -> observability/SLI bindings
 -> release/recovery/runbook joins
```

Provider-specific adapters require their trust/auth/ambiguity profile before implementation.

### Monitoring first vertical — post-D2 state

Monitoring Track A supplies the accepted domain/API/event/Zabbix contract authority. PR #40 supplied and conformed the `OPEN-REL-030` Track B durable customer-telemetry profile and merged it to `main@2ffec007d7dff32e0a45116b0bc875d5c2743b12`.

Therefore the specific Track B blocker that previously limited `impl.customer-telemetry@1` to evidence-only work is removed. Monitoring is now **eligible for a separate Wave 4 implementation-authorization decision**, subject to all other applicable slice prerequisites and remaining C2/C3/C4/C5 boundaries.

Eligibility is not authorization:

```text
Track A accepted + Track B accepted
  -> Wave 4 Monitoring eligible_for_separate_explicit_authorization
  -> exact authorization scope must name permitted implementation slices/contracts
  -> only then canonical Monitoring product code may begin
```

## Deferred slices

Initially not authorized by this sequencing document:

- `impl.realtime@1` until C5 realtime transport/presentation decisions are activated;
- Product-facing outbound webhook until Product gate closes;
- browser-active inline artifact execution until Product/security gate closes;
- public API SDK/public projection families until Product gate closes;
- privileged direct-query surface;
- any endpoint/event family not backed by accepted Product/domain contract.

## Customer telemetry

`impl.customer-telemetry@1` is now `eligible_for_implementation_authorization` for the accepted Monitoring Track B profile. It is not globally authorized, and it may not infer unbounded production settings from still-open `OPEN-REL-020` C3 capacity/performance/cost envelopes.

The accepted implementation must preserve the D2 security, concurrency, history, PITR/recovery, Timescale mediated-access and relocation/fencing invariants rather than treating the evidence harness as optional test-only behavior.

## Operations implementation

`impl.operations-recovery@1` may build records/workflows only after the underlying authority primitives exist. It never becomes a shortcut around incomplete identity, fencing, data, release or recovery semantics.

## Advancement rule

Each wave requires its own implementation PRs and exact-HEAD assurance. This sequencing document authorizes no product code by itself; explicit implementation authorization remains separate.

```text
READY_TO_AUTHORIZE != AUTHORIZED_TO_IMPLEMENT
```