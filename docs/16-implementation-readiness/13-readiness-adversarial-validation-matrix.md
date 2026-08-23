# Implementation Readiness — Adversarial Validation Matrix

**Status:** proposed gate baseline

## Purpose

These vectors falsify the readiness claim itself. They ask whether implementation would still have room to invent protected semantics.

## IRV vectors

### IRV-001 — Framework default becomes API authority
Inject: implementation framework emits route/body/error behavior not present in Phase 09.
Required: implementation fails conformance or requires reviewed contract amendment.

### IRV-002 — ORM schema becomes business/data contract
Required: rejected; owning use case/Data authority remains canonical.

### IRV-003 — Broker capability becomes exactly-once business claim
Required: rejected; inbox/effect/idempotency semantics remain authoritative.

### IRV-004 — Product-gated route/webhook appears because module is installed
Required: route/delivery remains absent or fail-closed until Product authority.

### IRV-005 — C1 OPEN left for implementer choice
Required: gate blocked.

### IRV-006 — C2 spike silently becomes canonical
Required: no canonical merge/use until reviewed decision + conformance evidence.

### IRV-007 — C3 provisional number presented as production target
Required: production eligibility blocked; provenance labels value as non-production evidence configuration.

### IRV-008 — OIDC token valid but membership revoked
Required: protected action denied by current authorization.

### IRV-009 — Browser obtains platform refresh/access credential
Required: BFF profile violation; implementation blocked.

### IRV-010 — Machine principal uses shared unattributable secret
Required: violates IR-D-001 asymmetric attributable machine profile.

### IRV-011 — Workload mTLS identity grants tenant wildcard
Required: denied; service authentication != tenant authorization.

### IRV-012 — Validation workload certificate authenticates as production
Required: trust-domain/environment boundary rejects it.

### IRV-013 — Old runtime holder acts after successor fence epoch
Required: old effect rejected.

### IRV-014 — Restore exposes lower fence epoch as current
Required: quarantine/reconciliation/forward fence; no protected admission.

### IRV-015 — Lease expires and new worker assumes old effect absent
Required: ambiguity remains governed by stable operation/effect evidence.

### IRV-016 — Deployment controller green substitutes for running artifact proof
Required: release admission blocked until actual runtime identity/current config proven.

### IRV-017 — Health green substitutes for recovery admission
Required: blocked until F, `(R,F]` and current authorities proven.

### IRV-018 — Logs reconstruct missing audit
Required: ordinary observability cannot replace mandatory audit authority.

### IRV-019 — AI risk score changes retry/recovery/release eligibility
Required: prohibited regardless of human/deterministic wrapper.

### IRV-020 — Deferred capability hidden in config but reachable
Required: gate/implementation test fails; deferred means absent from protected Product surface.

### IRV-021 — Open registry range misses a live source OPEN ID
Required: readiness gate fails until every source ID has exactly one class/disposition.

### IRV-022 — Downstream closure claimed without owning authority
Required: source OPEN remains unresolved; readiness blocked.

### IRV-023 — Same-key reliability/observability/operations joins drift
Required: conformance fails until exact IDs align.

### IRV-024 — C2 vendor replacement requires canonical identity/schema rewrite
Required: replacement is not compatible; architecture amendment required.

### IRV-025 — Implementation PR changes normative docs to make tests pass
Required: protected semantic change routed through owning governance, not smuggled with implementation.

### IRV-026 — One tenant/provider/replay storm exhausts unrelated global capacity
Required: bulkhead/admission/backpressure evidence required.

### IRV-027 — Recovery/relocation/release overlap creates two current writers/executors
Required: generation/release fences admit only one current authority; ambiguity reconciles.

### IRV-028 — Product state unproven converted to N/A by absent code
Required: upstream OPEN remains OPEN.

### IRV-029 — Exact-HEAD deterministic run belongs to older SHA
Required: invalid gate evidence.

### IRV-030 — Gate merge interpreted as implementation authorization
Required: implementation remains prohibited until separate explicit authorization.

## Acceptance rule

The gate cannot reach `READY_FOR_MERGE` while an applicable `IRV-001..030` vector lacks an expected result/evidence path or while the final panoramic audit identifies an unmodeled class that implementation could decide silently.
