# Implementation Readiness — Unresolved Risk & Exception Register

**Status:** proposed gate baseline

## Rule

An unresolved risk is not an authority waiver. An exception cannot convert a fixed invariant into an implementation preference.

## Current readiness risks

### IR-RISK-001 — GitHub `main` hosting enforcement absent

`main` is not currently protected by platform-enforced required status checks. This is a hosting/control-plane enforcement gap, tracked separately from semantic readiness.

Mitigation until resolved:

- expected-head SHA pinned on every merge;
- exact-HEAD deterministic assurance checked manually through the connector;
- explicit separate merge authorization;
- observer-only workflow permissions;
- no automatic merge authority.

This risk does not authorize weakening repository governance and cannot be marked resolved by documentation.

### IR-RISK-002 — C2 mechanism choices not yet selected

Cloud/runtime/broker/cache/observability/release/operations products remain intentionally OPEN. Risk is controlled by fixed logical profiles, bounded spike authority, compatibility classification and conformance tests.

No C2 choice may become canonical merely because it is scaffolded first.

### IR-RISK-003 — C3 production numerics absent

SLO/RPO/RTO, limits, retention, sizing, scaling, rollout and operational cadence values remain evidence-dependent. Non-production implementation may expose bounded provisional configuration only when clearly non-authoritative and non-production.

### IR-RISK-004 — Product-gated/deferred capability leakage

Framework defaults may accidentally expose routes/webhooks/inline rendering/public surfaces. Controls: explicit slice registry, deny-by-default routing/configuration and tests that deferred capabilities are absent/unreachable.

### IR-RISK-005 — identity/fencing profile implementation complexity

IR-D-001/002/003 are concrete enough to implement but require high-quality security/concurrency testing. They are not considered proven until implementation evidence exists.

## Exception policy

Allowed readiness exceptions are only:

- bounded evidence spike for a C2 decision;
- explicit Product/architecture deferral of a C4/C5 capability;
- temporary non-production C3 configuration used solely to generate evidence.

An exception SHALL record:

```text
exception_id
owning authority
exact scope
reason
which fixed semantics still apply
forbidden effects
time/expiry or closure condition
evidence generated
cleanup/retirement
```

## Forbidden exceptions

No exception may waive:

- tenant isolation/current authorization;
- API/event canonical meaning;
- idempotency/ambiguity/reconciliation;
- recovery continuity `(R,F]`;
- revocation/erasure/legal hold/audit/crypto continuity;
- runtime/release fencing;
- source/artifact trust;
- Product applicability authority;
- AI/tool non-authority;
- exact-HEAD assurance/explicit merge authorization.
