# D4-C — Candidate Evaluation Plan

**Status:** candidate-evaluation only; no D4-C selection; no ledger credit  
**Canonical base:** `main@70a7256b23c43cbd64eb9c02cdcd9091b847204e`

## Purpose

This record defines the bounded evidence-evaluation space for D4-C without selecting an implementation profile. D4-C owns delivery acknowledgement/lease semantics, quarantine/redrive, bounded message processing, scoped content-equivalence authority, outbox dispatch, producer/source generation, replay/history, historical readers/upcasters, and recovery-generation reconciliation.

The plan is deliberately product-neutral. Broker-native features may participate in an implementation, but they cannot become business-effect, quarantine, equivalence, replay, recovery, authorization or identity authority by implication.

## Source decisions and evidence mapping

| Axis | Source OPEN | Evidence obligation |
|---|---|---|
| Ack / visibility / lease / checkpoint | `OPEN-EVT-008` | `ack_after_durable_responsibility_and_lease_ambiguity` |
| Quarantine / redrive | `OPEN-EVT-009` | `quarantine_redrive_current_authority_and_dedup_preservation` |
| Message / payload / batch / compression bounds | `OPEN-EVT-010` | `bounded_message_batch_compression_and_parser_limits` |
| Scoped content-equivalence authority | `OPEN-EVT-011` | `scoped_content_equivalence_confidentiality_and_conflict_rejection` |
| Outbox claim / dispatch / ack ambiguity | `OPEN-EVT-012` | `outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity` |
| Producer/source generation | `OPEN-EVT-013` | `producer_generation_nonresurrection_across_failover_restore` |
| Privileged replay / event history | `OPEN-EVT-014` | `privileged_bounded_replay_with_original_identity_and_effect_safety` |
| Historical reader / upcaster | `OPEN-EVT-015` | `historical_reader_upcaster_semantic_and_equivalence_continuity` |
| Recovery generation / reconciliation / activation | `OPEN-EVT-025` | `recovery_generation_rf_inventory_reconciliation_and_activation_gates` |

Each axis is independently selectable. A candidate becoming evidence-eligible on one axis does not select or prefer any candidate on another axis.

## Candidate classes

### 1. Ack / visibility / lease / checkpoint

Candidate classes:

- durable inbox claim then broker ack;
- broker visibility/lease plus durable receipt;
- database-owned work claim plus broker checkpoint;
- equivalent reviewed profile.

Any eligible profile must prove ack-after-durable-responsibility, fail-closed lease ambiguity, fenced takeover, safe redelivery/rewind and crash recovery between responsibility and broker progress.

### 2. Quarantine / redrive

Candidate classes:

- durable platform quarantine store with broker-DLQ adapter;
- broker-native DLQ with canonical platform quarantine index;
- hybrid platform quarantine plus broker DLQ;
- equivalent reviewed profile.

Broker DLQ semantics are never canonical process truth. Redrive remains privileged, audited, currently authorized and subject to the same dedup/equivalence/reconciliation rules as ordinary delivery.

### 3. Bounded message / payload / batch / compression

Candidate classes:

- contract-bound application limits with transport precheck;
- bounded envelope/codec profile;
- layered transport + application bounds;
- equivalent reviewed profile.

Eligibility requires bounded allocation, nesting/count/string sizes, decompression, recursion and CPU amplification. Transport defaults cannot silently weaken contract limits.

### 4. Scoped content-equivalence authority

Candidate classes:

- canonical collision-resistant fingerprint;
- keyed authenticated digest;
- protected retained immutable original;
- hybrid equivalence authority;
- equivalent reviewed profile.

The selected future profile must cover all immutable semantic fields for the scoped message identity while avoiding cross-tenant/cross-consumer equality oracles. Missing/unverifiable evidence is uncertainty, never benign duplicate success.

### 5. Outbox claim / dispatch / ack ambiguity

Candidate classes:

- database `SKIP LOCKED`-style polling claim;
- compare-and-swap lease claim;
- notification-assisted polling claim;
- equivalent reviewed profile.

The authoritative mutation and required outbox fact remain atomic; claim takeover is fenced; broker-ack ambiguity retries the same identity and meaning; outage preserves committed backlog.

### 6. Producer/source generation

Candidate classes:

- positive-integer fenced generation;
- opaque fenced generation token;
- authority-issued epoch/generation;
- equivalent reviewed profile.

Generation never becomes tenant identity or placement identity. Retired generations cannot regain current-source authority after failover or restore.

### 7. Privileged replay / event history

Candidate classes:

- canonical event-history store;
- broker-retained log plus authoritative history index;
- hybrid history archive plus replay controller;
- equivalent reviewed profile.

Replay stays privileged, audited and bounded; original message identity and immutable semantic meaning survive replay; irreversible effects cannot be repeated by disabling dedup.

### 8. Historical reader / upcaster

Candidate classes:

- in-process versioned reader/upcaster registry;
- sidecar/library historical reader;
- offline replay transform pipeline;
- equivalent reviewed profile.

Historical meaning is immutable. Upcasting cannot fabricate newer historical facts and must preserve or deterministically map equivalence/comparison semantics.

### 9. Recovery generation / reconciliation / activation

Candidate classes:

- restore-generation fence manifest;
- reconciliation inventory job plus activation gate;
- hybrid generation manifest plus multi-store reconciler;
- equivalent reviewed profile.

The selected future profile must make `(R,F]` reconciliation reproducible across broker/history/inbox/outbox/equivalence and surviving external/effect evidence. It must also preserve webhook recovery continuity explicitly: stable delivery identity, the semantic snapshot or reproduction authority required to recreate the original delivery meaning, and destination-generation fences. Missing state remains uncertainty and effectful async activation stays fail-closed until continuity is proven.

## Cross-axis invariants

The following remain fixed regardless of future candidate eligibility or selection:

- message identity, content equivalence, ordering, source generation and authorization are distinct authorities;
- current authority is re-established for redrive, replay and recovery activation;
- historical message meaning plus required equivalence/verifier authority remains reproducible for supported horizons;
- uncertainty never collapses into absence, safe duplicate or effect eligibility;
- dynamic untrusted code/schema/parser behavior is forbidden;
- D4-A Kafka 7/7 and the accepted D4-B profile 5/5 are preserved unchanged;
- D4-C remains 0/9 and D4-D remains 0/5 while this plan is only an evaluation artifact;
- D4-wide remains 12/26 and `gate_state=scoped`;
- transport authority remains `selected_not_granted`;
- Product/Wave4 remain `not_granted`, production remains `none`, and C3 remains `not_selected`.

## Allowed outputs

A candidate evaluation may produce only:

- `eligible_for_evidence_execution`;
- `ineligible_by_contract`;
- `insufficient_evidence`.

It may not produce selection, preference without evidence, ledger credit, full D4 acceptance, production readiness or any new authority.

## Next transition

After this plan is accepted, source-evidence execution can proceed axis-by-axis. A separate governed selection record is required only after the relevant candidate evidence is complete. Full D4 acceptance remains a still-later transition requiring all D4 tracks to reach reviewed terminal C2 disposition with their required evidence complete.
