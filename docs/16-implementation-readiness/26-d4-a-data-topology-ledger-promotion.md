# D4-A — Data Topology Ledger Promotion

**Status:** promotion candidate — reviewed source evidence to ledger credit only  
**Promotion base:** `main@8d493f6f6b5ced5fb56bcbd4968e01e557ab808d`  
**Track:** D4-A — broker transport, physical routing and anti-corruption boundary

## Purpose

This promotion consumes the already-reviewed source-only package merged by PR #56 and proposes exactly two additional D4-A ledger credits:

- `regulated_payload_erasure_granularity`;
- `physical_naming_routing_and_cell_topology_adapter_mapping`.

It does not create new source evidence and does not reinterpret a green promotion run as evidence. The immutable source run remains the authority for the two proofs.

```text
SOURCE RUN -> REVIEW -> SEPARATE PROMOTION
PROMOTION RUN != NEW SOURCE EVIDENCE
4/7 LEDGER != KAFKA SELECTION
4/7 LEDGER != D4 ACCEPTANCE
4/7 LEDGER != PRODUCT OR PRODUCTION AUTHORITY
```

## Pinned source provenance

The promotion record is:

`implementation/d4-eventing-async/ledger-promotions/d4-a-data-topology-promotion-v1.json`

It pins:

- source PR: `#56`;
- exact reviewed source HEAD: `b8dce5c87803a20cdf8776429f76a0b6c2cb1d96`;
- source merge commit: `8d493f6f6b5ced5fb56bcbd4968e01e557ab808d`;
- source workflow run: `33811864261`, attempt `1`;
- source job: `100835274740` — `D4-A data topology source evidence`;
- artifact: `9915088812`;
- artifact name: `d4-a-data-topology-source-b8dce5c87803a20cdf8776429f76a0b6c2cb1d96-33811864261-1`;
- artifact digest: `sha256:c9037f1bd15185a2a58063306efb92485e325611d18a11ad50fa5678393df4d6`;
- source manifest SHA-256: `269394b6e7baadd9e2c5e6410289dc5d026f99d03167a1ea212d51c5b7995093`.

The promotion is also chained to the prior semantic-boundary promotion record by exact path, promotion identity and SHA-256 digest. The first two credits therefore cannot be silently replaced while preserving only their names.

## Review provenance

The source gate records:

- exact-HEAD CI: 16/16 SUCCESS;
- initial Codex review `PRR_kwDOT7x07M8AAAABMGjwng`, which produced the two material findings later corrected;
- independent exact-HEAD adversarial review `PRR_kwDOT7x07M8AAAABMGvj3Q`;
- fresh Codex exact-HEAD review `PRR_kwDOT7x07M8AAAABMGwL3Q` on `b8dce5c87803a20cdf8776429f76a0b6c2cb1d96`;
- zero unresolved material review threads at the source final gate;
- source final-gate comment `5532846276`.

The two resolved material findings remain part of the promotion history:

1. raw regulated exceptions must be bound to trusted issuing authorities rather than caller assertions;
2. topology replacement must execute consumer-facing semantics under both physical mappings and detect route-coupled consumers.

## Ledger result

If this promotion passes exact-HEAD review and is separately authorized for merge, D4-A becomes exactly **4/7**:

Previously credited:

- `broker_neutral_anti_corruption_stub_swap`;
- `exactly_once_guardrail_consumer_inbox_enforcement`.

Newly credited by this promotion:

- `regulated_payload_erasure_granularity`;
- `physical_naming_routing_and_cell_topology_adapter_mapping`.

Still pending:

- `capacity_envelope_baseline_growth_stress`;
- `ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency`;
- `broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark`.

## Non-authority boundary

This promotion does **not**:

- select Kafka;
- claim a live Kafka broker run;
- claim capacity, ordering/partition or outage/recovery benchmark completion;
- select production topic/group/cell names;
- select production partition, retention, lag, replay or recovery numerics;
- grant D4 transport authority;
- grant Product or Wave 4 implementation authority;
- grant production authority;
- grant C3 numeric/topology authority;
- make D4-A or D4 acceptance eligible.

D4 remains `scoped`, Kafka remains `not_selected`, and the three real-candidate evidence IDs remain mandatory before D4-A can reach 7/7.

## Exit gate

This promotion PR is eligible for merge only after:

1. exact-HEAD CI is fully green;
2. the promotion validator proves the exact four-credit set and three-credit remainder;
3. source manifest bytes and the prior promotion record match their pinned SHA-256 digests;
4. the historical source run/job/artifact still resolve successfully through GitHub and match the pinned identity/digest;
5. negative controls reject fifth-credit, credit-removal, review/provenance tamper and authority escalation;
6. panoramic adversarial review is CLEAN on the exact HEAD;
7. zero unresolved material review threads remain;
8. separate explicit user authorization is given for squash merge.
