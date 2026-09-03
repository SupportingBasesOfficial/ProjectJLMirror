# D4-A — Semantic Boundary Ledger Promotion

**Status:** proposed reviewed-source ledger promotion — partial D4-A evidence credit only  
**Promotion base:** `main@8863f66a0fb6457ad05b72286ef983eb4e8a1c5e`  
**Source PR:** #54  
**Reviewed source HEAD:** `d6872579dca7d4f08c9ded82e34b94f8e87ec1e9`

## Purpose

This change performs the separate ledger action required by the accepted D4-A evidence policy. It does not generate new broker evidence. It promotes exactly the two evidence IDs proven by the already-reviewed semantic-boundary source run:

- `broker_neutral_anti_corruption_stub_swap`
- `exactly_once_guardrail_consumer_inbox_enforcement`

After this promotion, D4-A moves from **0/7 to 2/7**. The remaining five D4-A obligations stay open.

## Exact source provenance

The promoted run is pinned by `implementation/d4-eventing-async/ledger-promotions/d4-a-semantic-boundary-promotion-v1.json`:

- repository SHA: `d6872579dca7d4f08c9ded82e34b94f8e87ec1e9`;
- workflow run: `33790608658`, attempt `1`;
- workflow job: `100766024114` — `D4-A semantic boundary source evidence`;
- source artifact ID: `9907159265`;
- artifact name: `d4-a-semantic-boundary-source-d6872579dca7d4f08c9ded82e34b94f8e87ec1e9-33790608658-1`;
- artifact digest: `sha256:8b4c4031270479ff3cb0912ae5469df575459f8afaf9e3ff226fb3b73e18ae6a`;
- source-manifest SHA-256: `690cdc59af819e27a7922cd2eea04d537c20dcd0e005ce4dbd4dac977eb525a1`.

The source run completed successfully, produced immutable runtime-resolved provenance, passed the exact-HEAD CI gate, and received an independent adversarial exact-HEAD CLEAN review under the documented Codex-availability substitution. No older Codex review is treated as the clean review for the promoted source HEAD.

## Promotion semantics

`source-evidence-manifest.json` remains unchanged and continues to state `current_run_auto_credit=false` and `ledger_credit=[]`. That is deliberate: source packages do not rewrite themselves after review.

The separate promotion changes the machine-owned D4 ledger and evidence-plan state to record the reviewed outcome. Assurance requires all three representations to agree:

1. the immutable source package and its digest;
2. the exact promotion provenance record;
3. the D4-A `evidence_completed` / `evidence_remaining` partition.

A provenance mismatch, additional evidence credit, missing promoted ID, changed evidence kind, changed source SHA/run/job/artifact digest, or source-manifest byte drift fails the D4-A assurance gate.

## External provenance revalidation

The D4-A workflow uses GitHub Actions read authority to re-read the pinned source run, source job and artifact metadata during this promotion PR. It requires:

- the exact source run SHA;
- run and job `completed/success`;
- the exact job identity;
- the exact artifact ID/name/digest;
- a non-expired artifact at promotion time.

Repository-side validators independently pin the same values and the source-manifest bytes, so changing workflow metadata alone cannot authorize another source run.

## Authority boundary

This promotion does **not** mean Kafka has been selected. It does not claim a live Kafka broker execution and does not satisfy any real-candidate capacity, ordering/partition, or outage/recovery evidence package.

The following remain unchanged:

- Kafka selection: `not_selected`;
- D4 transport authority: `not_selected_not_granted`;
- D4 gate state: `scoped`;
- Product implementation authority: `not_granted`;
- Wave 4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

D4-A remains `candidate_leading_closure_pending` because five evidence obligations remain.

## Remaining D4-A evidence

After the promotion, these remain uncredited:

1. `capacity_envelope_baseline_growth_stress`;
2. `regulated_payload_erasure_granularity`;
3. `ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency`;
4. `physical_naming_routing_and_cell_topology_adapter_mapping`;
5. `broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark`.

Per the accepted execution order, the next source-evidence work should close the regulated-payload boundary and physical topology adapter before real-candidate capacity/ordering and outage/recovery benchmarks.

## Merge gate

This promotion may merge only after:

- exact-HEAD CI is clean;
- the source run/job/artifact provenance revalidation is clean;
- panoramic review confirms the source package is not mutated or over-promoted;
- adversarial review on the exact promotion HEAD is clean, using the documented independent substitution only if Codex remains unavailable;
- zero unresolved material review threads remain;
- separate explicit user authorization is given.

Merge credits exactly **2/7 D4-A evidence** and nothing else.
