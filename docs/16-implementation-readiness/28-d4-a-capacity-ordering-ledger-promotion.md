# D4-A — Capacity + Ordering Ledger Promotion

**Status:** governed ledger promotion only  
**Promotion base:** `main@80ee52a0057cd30dbfd84a4176a0bbb0144e45bb`  
**Source PR:** #59  
**Source reviewed HEAD:** `da86d9442b9091f3255f2bf643d6ab1dc87baa7f`

## Purpose

Promote exactly two independently reviewed source-evidence obligations into the D4-A ledger:

- `capacity_envelope_baseline_growth_stress`;
- `ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency`.

This transition is exactly **4/7 → 6/7**. It does not create new source evidence and does not satisfy the final recovery obligation.

## Pinned source run

The promotion record pins the reviewed source execution from PR #59:

- workflow run `33818533105`, attempt `1`;
- job `100855875375` — `D4-A capacity ordering source evidence`;
- artifact `9917494653`;
- artifact digest `sha256:b961f2febbeae8c42f2d821f8ac1ab14887b44a041418c975d6e2b500d0c40c7`;
- exact source HEAD `da86d9442b9091f3255f2bf643d6ab1dc87baa7f`;
- independent adversarial exact-HEAD review `PRR_kwDOT7x07M8AAAABMHNIGQ`;
- fresh Codex exact-HEAD review `PRR_kwDOT7x07M8AAAABMHOEcg`;
- final gate comment `5533586795`.

The source run closed seven material P1 findings before final review: immutable Kafka image pinning; real degradation measurement; loaded partition-ceiling probes; canonical KeySerialExecutor execution; tier-relative admission; actual over-ceiling fallback; and explicit device/resource cardinality.

## Promotion-time admission versus steady-state validation

GitHub Actions artifacts are retention-bounded storage and must not become permanent ledger truth.

Therefore the ledger gate has two distinct modes:

1. **Promotion-time admission:** when this promotion record or the authoritative D4-A ledger/state changes, CI requires the historical source artifact to still be live, downloads it, opens it, and cross-checks run/job/artifact metadata, source manifest digest, benchmark-results digest, evidence IDs/kinds, Kafka candidate pin, numeric non-authority, review identities and final gate.
2. **Steady-state validation:** later unrelated PRs continue validating the immutable promotion chain and source/promotion byte digests, but do not require the temporary Actions artifact to remain unexpired forever.

This prevents artifact-retention expiry from becoming a deterministic future failure while preserving strict proof at the authority transition where the evidence is admitted.

## Resulting ledger

After this promotion, D4-A has exactly six promoted obligations. The sole remaining obligation is:

`broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark`

D4-A is therefore still incomplete.

## Authority boundary

The promotion preserves all non-authority boundaries:

- Kafka remains `not_selected`;
- D4 remains `scoped`;
- D4 transport authority remains `not_selected_not_granted`;
- Product implementation authority remains `not_granted`;
- Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`;
- bounded benchmark numerics remain test evidence only.

A 6/7 ledger does **not** select Kafka and does **not** make D4-A eligible for final acceptance while recovery evidence remains open.

## Chain rule

The new promotion record is cryptographically chained to `d4-a-data-topology-promotion-v1.json`, and the source manifest is byte-digest pinned. Any rewrite of prior promotion history, source manifest bytes, source run identity, review identity, evidence inventory or authority state must fail CI.
