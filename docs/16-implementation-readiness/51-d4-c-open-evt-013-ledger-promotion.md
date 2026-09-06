# D4-C OPEN-EVT-013 — Reviewed Source Ledger Promotion

## Status

Ledger-promotion package only for `OPEN-EVT-013` / `producer_generation_nonresurrection_across_failover_restore`.

This promotion grants exactly one reviewed D4-C evidence credit. It does **not** select a D4-C candidate and does **not** grant Product/Wave4, production, transport, or C3 numeric/topology authority.

Promotion base: `main@8b9761a0469040ee26499902cd64aea25ee0016d`.

## Source evidence admitted

The promotion is bound to the already reviewed and squash-merged source PR #82:

- exact reviewed source HEAD: `317479d2e71108a6854d16f35e063648365d9b62`;
- source squash/main commit: `8b9761a0469040ee26499902cd64aea25ee0016d`;
- final panoramic/adversarial review: `5124310737`;
- source workflow: `.github/workflows/d4-c-producer-generation-source-evidence.yml` / workflow id `351350724`;
- admitted post-ready run: `34014396915`, attempt `1`;
- exact job: `101435567019` / `D4-C OPEN-EVT-013 source evidence`;
- artifact: `9983444885` / `d4-c-producer-generation-source-317479d2e71108a6854d16f35e063648365d9b62-34014396915-1`;
- artifact digest: `sha256:03f2dcbb8929e385a539147a1d2a9cd5068f41d090d1273f6db7ffb2dc56733f`;
- source manifest SHA-256: `f1bbb8b35ffa9da6920d1db8ec54e1a626fa277afe7409aa81e99d172eee2345`.

The promotion gate revalidates this evidence from live GitHub state and fails closed on mismatch.

## Ledger transition

Before this promotion:

- D4-A: `7/7`;
- D4-B: `5/5`;
- D4-C: `5/9`;
- D4-D: `0/5`;
- D4-wide: `17/26`.

After this promotion:

- D4-A: `7/7`;
- D4-B: `5/5`;
- D4-C: `6/9`;
- D4-D: `0/5`;
- D4-wide: `18/26`.

The newly credited evidence is exactly:

`producer_generation_nonresurrection_across_failover_restore`

No other evidence credit is granted.

## Authority boundary

The promotion preserves all non-authority invariants:

- D4-C candidate: `null / not_selected / candidate_selection_open`;
- D4 gate: `scoped`;
- transport authority: `selected_not_granted`;
- Product/Wave4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`;
- D4-D remains `0/5` and unselected.

Candidate selection and D4 acceptance remain separate reviewed decisions.

## Remaining D4-C evidence

After this promotion, three evidence obligations remain uncredited:

1. `privileged_bounded_replay_with_original_identity_and_effect_safety` (`OPEN-EVT-014`);
2. `historical_reader_upcaster_semantic_and_equivalence_continuity` (`OPEN-EVT-015`);
3. `recovery_generation_rf_inventory_reconciliation_and_activation_gates` (`OPEN-EVT-025`).

The next source-evidence PR must remain separate from this promotion.
