# D4-C — Bounded C2 Delivery and Recovery Profile Selection

## Status

This record governs the transition from **D4-C evidence complete (9/9), selection pending** to a **bounded C2 delivery/recovery profile selection**.

Canonical selection base:

- `main@8d49980d45256a86a6005a93cc71f5518622cc90`

Source decisions: `OPEN-EVT-008`, `009`, `010`, `011`, `012`, `013`, `014`, `015`, and `025`.

The historical candidate-evaluation plan and all nine source-evidence records remain immutable source-time truth. This selection is current authority only.

## Selected bounded C2 profile

1. **Ack / lease / checkpoint:** `durable_inbox_claim_then_broker_ack_profile` — durable platform responsibility precedes broker progress; ambiguous lease/takeover is fenced and fail-closed.
2. **Quarantine / redrive:** `hybrid_platform_quarantine_store_plus_broker_dlq` — canonical quarantine truth stays platform-owned; broker DLQ is transport assistance only.
3. **Message / batch / compression bounds:** `layered_transport_and_application_bounds_profile` — application contract limits are authoritative and transport limits are defense in depth.
4. **Scoped content equivalence:** `hybrid_equivalence_authority_profile` — same scoped identity is benign only with durable proof of equivalent immutable semantics; conflict fails closed.
5. **Outbox claim / dispatch:** `compare_and_swap_lease_claim_profile` — authoritative mutation and outbox fact remain atomic; ownership transfer is fenced; ack ambiguity retries the same identity and meaning.
6. **Producer/source generation:** `authority_issued_epoch_generation` — current source authority is explicit; retired generations cannot resurrect after failover or restore.
7. **Privileged replay/history:** `hybrid_history_archive_plus_replay_controller_profile` — replay is privileged, bounded, audited and preserves original identity/meaning without bypassing dedup/equivalence.
8. **Historical reader/upcaster:** `in_process_versioned_reader_upcaster_registry` — historical meaning remains immutable; upcasters are explicit/versioned and cannot require dynamic untrusted code.
9. **Recovery/reconciliation/activation:** `hybrid_generation_manifest_plus_multi_store_reconciler_profile` — `(R,F]` reconciliation is generation-scoped and reproducible; effectful activation fails closed until required continuity is proven.

## Cross-axis invariants

- message identity, content equivalence, ordering, source generation and authorization remain distinct authorities;
- broker-native features never become canonical business, quarantine, replay or recovery truth;
- redrive, replay and recovery activation re-establish current authority;
- historical meaning plus required equivalence/verifier authority remain reproducible for the supported horizon;
- uncertainty never becomes absence, benign duplicate or effect eligibility;
- dynamic untrusted code/schema/parser execution remains forbidden;
- selected mechanism classes are replaceable C2 profiles beneath canonical platform authority.

## Selection is not D4 acceptance or implementation authority

After this transition:

- D4-C remains `9/9` evidence complete;
- D4-wide remains `26/26`;
- D4-C becomes `selected_candidate`;
- all four D4 tracks now have reviewed selected C2 dispositions;
- D4 global gate remains `scoped`;
- `d4_transport_authority=selected_not_granted`;
- canonical Product implementation authority remains `not_granted`;
- Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`;
- full D4 acceptance remains a separate governed transition.

This selection does not choose production retry/backoff, retention, replay, quarantine, recovery, capacity or topology numerics.

## Historical truth remains immutable

The D4-C candidate-evaluation plan intentionally retains `selection_state=not_selected`, `selection_authority=not_granted`, and `separate_selection_required=true` because it is historical evaluation authority, not current selection authority. Source-evidence records remain source-time evidence and are not rewritten by this transition.

Current D4-C selection authority is represented only by:

- `implementation/d4-eventing-async/d4-c-selection-record.json`;
- `implementation/d4-eventing-async/d4-c-evidence-plan.json`;
- `implementation/d4-eventing-async/state-manifest.json`.

## Replacement governance

A material change to any selected D4-C mechanism class requires a separate governed transition with equivalent-or-stronger evidence for that axis. Physical implementations may be replaced only while preserving the selected semantics and authority boundaries.

## Merge governance

Merge requires exact-HEAD CI, panoramic/adversarial review, zero unresolved material threads, mergeability, and separate explicit user authorization for squash merge.

Merging this selection still does not constitute D4 acceptance. It merely completes the missing terminal C2 disposition prerequisite so that a separate D4 acceptance transition may be evaluated next.
