# D4-C OPEN-EVT-015 Ledger Promotion

## Status

This artifact records the **separate reviewed promotion** of `OPEN-EVT-015` source evidence into the D4-C ledger.

It does not select a D4-C candidate and does not grant D4, product, Wave 4, production, or C3 numeric/topology authority.

## Promoted obligation

- source decision: `OPEN-EVT-015`
- evidence: `historical_reader_upcaster_semantic_and_equivalence_continuity`
- D4-C ledger transition: **7/9 → 8/9**
- D4-wide transition: **19/26 → 20/26**
- remaining D4-C evidence: `recovery_generation_rf_inventory_reconciliation_and_activation_gates`

## Immutable source binding

The promotion is bound to the merged source-evidence PR and exact reviewed source HEAD:

- source PR: `#103`
- source reviewed HEAD: `90371a0e91da9e9a29f344231ab04461e47026d4`
- source merge commit / promotion base: `5f4711f388ac1b07de4e544ee31b9e09a2fec481`
- exact-head review id: `5126450377`
- review mode: `independent_exact_head_adversarial_clean_after_exact_head_ci`
- unresolved material review threads: `0`

## Immutable workflow provenance

The credited source run is the successful post-ready exact-HEAD run:

- workflow id: `351770101`
- workflow: `.github/workflows/d4-c-historical-reader-upcaster-source-evidence.yml`
- event: `pull_request`
- source branch: `d4c/open-evt-015-historical-reader-source`
- run id: `34056103551`
- run attempt: `1`
- job id: `101548179099`
- job: `D4-C OPEN-EVT-015 source evidence`
- artifact id: `9995996278`
- artifact: `d4-c-historical-reader-source-90371a0e91da9e9a29f344231ab04461e47026d4-34056103551-1`
- artifact digest: `sha256:dae09cfdc630d4bdc62d6e1fd56502535ba5e879ca39cc58519ac8788cdde3a0`

The artifact itself records:

- repository SHA equal to the reviewed HEAD;
- exact run/job identity;
- `source_decision=OPEN-EVT-015`;
- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- `selection=not_selected`;
- all candidate results eligible for evidence execution;
- all seven OPEN-EVT-015 proof obligations true.

## Source manifest binding

- path: `implementation/d4-eventing-async/source-evidence/d4-c-historical-reader-upcaster-source.json`
- SHA-256: `192a3997d406e93581b72a734a1db2f9f071f1dc9ad3178ee56f166c24b4567f`

Promotion CI recomputes this digest and requires it to match both the promotion record and the immutable source-run provenance.

## Authority boundary

After this promotion:

- D4-C remains `candidate_selection_open`;
- D4-C candidate remains `null`;
- D4-C selection authority remains `not_granted`;
- D4-D remains `0/5`;
- D4 remains `scoped`;
- D4 transport authority remains `selected_not_granted`;
- canonical product implementation authority remains `not_granted`;
- Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

`OPEN-EVT-025` remains the only uncredited D4-C evidence axis and requires its own source-evidence and separate promotion gates.
