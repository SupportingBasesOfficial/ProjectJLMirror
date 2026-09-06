# D4-C OPEN-EVT-010 ledger promotion

Status: **reviewed source evidence promotion only; no candidate selection, no implementation authority, no full D4 acceptance**.

Promotion base: `main@0266d406b91906587dbcb6ab7e96c2ce2802384c`.

## Governed transition

This promotion credits exactly one already-reviewed D4-C evidence obligation:

- source decision: `OPEN-EVT-010`;
- evidence id: `bounded_message_batch_compression_and_parser_limits`;
- D4-C ledger: `2/9 -> 3/9`;
- D4-wide ledger: `14/26 -> 15/26`.

No other evidence credit is granted.

## Immutable source provenance

The credit is bound to the accepted source package from PR #76:

- reviewed source HEAD: `08a2d3c1fb34d8ff5fbe164f7c9315615f6aab22`;
- source squash merge: `0266d406b91906587dbcb6ab7e96c2ce2802384c`;
- independent exact-HEAD review id: `5123374309`;
- source workflow id: `351206153`;
- source workflow run: `33997326798`, attempt `1`;
- source job: `101390021787`, `D4-C OPEN-EVT-010 source evidence`;
- artifact id: `9978515069`;
- artifact: `d4-c-bounded-parser-source-08a2d3c1fb34d8ff5fbe164f7c9315615f6aab22-33997326798-1`;
- artifact digest: `sha256:d4b58eba717323689cef2849428636ed5cff62df13cad154fddf9c38d202703e`;
- source manifest SHA-256: `a81715abe1c3e705d31d1949d0c98bc73605ab5c5f8453a28e2a63beb88959f1`.

The promotion gate admits this provenance from live GitHub state when the promotion authority changes. Subsequent steady-state validation relies on the durable promotion record and byte digest rather than reactivating artifact-retention dependency.

## Source history remains immutable

The OPEN-EVT-010 source manifest remains a source-time record. It continues to say that its run itself granted no credit and that D4-C was 2/9 when the source package was produced. Promotion does not rewrite that historical truth.

Current-state validators independently require the post-promotion state to be 3/9 and 15/26.

## Non-authority boundary

After this promotion, all authority boundaries remain unchanged:

- D4-C candidate: `null`;
- D4-C candidate status: `not_selected`;
- D4-C state: `candidate_selection_open`;
- D4-D: `0/5`;
- D4 gate: `scoped`;
- transport authority: `selected_not_granted`;
- Product implementation authority: `not_granted`;
- Wave4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

This promotion does not select production message sizes, compression ratios, parser implementations, codecs, transports, topology, retry numerics, retention horizons, or any D4-C candidate.

## Remaining D4-C evidence

After promotion, six obligations remain:

1. `scoped_content_equivalence_confidentiality_and_conflict_rejection` (`OPEN-EVT-011`);
2. `outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity` (`OPEN-EVT-012`);
3. `producer_generation_nonresurrection_across_failover_restore` (`OPEN-EVT-013`);
4. `privileged_bounded_replay_with_original_identity_and_effect_safety` (`OPEN-EVT-014`);
5. `historical_reader_upcaster_semantic_and_equivalence_continuity` (`OPEN-EVT-015`);
6. `recovery_generation_rf_inventory_reconciliation_and_activation_gates` (`OPEN-EVT-025`).

Candidate selection and full D4 acceptance remain separate future governed transitions.
