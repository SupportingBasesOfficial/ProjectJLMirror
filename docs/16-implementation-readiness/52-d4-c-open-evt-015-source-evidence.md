# D4-C — OPEN-EVT-015 Historical Reader / Upcaster Source Evidence

## Status

Source-evidence only. This artifact does **not** select a D4-C candidate, grant ledger credit, accept D4, grant transport authority, authorize Wave 4/product implementation, or grant production authority.

Current canonical projection at source time remains D4-C **7/9** and D4-wide **19/26**.

## Decision and evidence

- Decision: `OPEN-EVT-015`
- Evidence: `historical_reader_upcaster_semantic_and_equivalence_continuity`
- Mode: candidate evaluation only
- Selection: none
- Current-run auto-credit: forbidden

The three concrete candidate classes evaluated are:

1. `in_process_versioned_reader_upcaster_registry`
2. `sidecar_or_library_historical_reader_profile`
3. `offline_replay_transform_pipeline_profile`

`equivalent_reviewed_profile` remains allowed by the normative candidate plan but is not asserted eligible by this concrete source run.

## Required proofs

The executable source package must prove all seven OPEN-EVT-015 requirements:

- historical semantic meaning remains immutable;
- upcasting cannot fabricate newer historical facts;
- tenant, contract, source message and occurrence semantics remain traceable;
- supported retained history remains interpretable;
- equivalence evidence and comparison-profile semantics are preserved or deterministically mapped;
- reader/upcaster version is explicit and historically recoverable;
- historical reading does not require dynamic untrusted code or schema execution.

## Executable boundary

The source model uses an explicit versioned reader registry. Unsupported historical versions fail closed. A record whose declared reader does not match its historical schema version fails closed. The model rejects unknown comparison profiles and refuses representation transforms that introduce fields outside the immutable historical semantic shape.

Equivalence continuity is demonstrated by mapping the retained `eq-v1` profile to the explicit compatibility profile `eq-v2-compat` while hashing the same canonical structured semantic interpretation. This mapping is deterministic and does not turn comparison evidence into identity, authorization, routing or current-source authority.

Dynamic code execution is represented only as a negative control and is rejected. Candidate eligibility therefore never depends on loading historical executable code, untrusted schema code, or provider-specific runtime semantics.

## Falsification controls

The package includes negative controls for:

- fabricated newer historical fields;
- historical payload semantic-shape drift;
- unsupported historical schema version;
- wrong or mismatched reader version;
- unknown historical equivalence profile;
- dynamic untrusted execution.

A candidate is `eligible_for_evidence_execution` only when every positive check and every negative control passes for all seven proof obligations.

## Authority boundary

At source time:

- D4-C remains `candidate_selection_open`, 7/9;
- `OPEN-EVT-015` remains uncredited;
- D4-D remains 0/5;
- D4 remains scoped;
- D4 transport authority remains `selected_not_granted`;
- product and Wave 4 implementation authority remain `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

A separate promotion change, based on immutable exact-run provenance and separate review, is required before OPEN-EVT-015 may enter the D4-C ledger.

## Provenance

The workflow emits and retains:

- `candidate-results.json` — deterministic candidate/proof/check results;
- `resolved-source-run-provenance.json` — exact repository SHA, workflow run/attempt, job identity, hashes of the source manifest and candidate results, and explicit non-selection/non-credit state.

The source workflow verifies exact analyzed HEAD before execution and persists the two artifacts with bounded retention. Artifact existence alone grants no ledger credit.
