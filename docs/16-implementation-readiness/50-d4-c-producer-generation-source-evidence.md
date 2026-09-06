# D4-C OPEN-EVT-013 — Producer Generation Non-Resurrection Source Evidence

## Status

Source-evidence package only. This document does **not** select a D4-C candidate, does **not** grant ledger credit, and does **not** grant Product/Wave4, production, transport, or C3 numeric/topology authority.

Canonical source decision: `OPEN-EVT-013`.

Evidence obligation: `producer_generation_nonresurrection_across_failover_restore`.

Canonical base for this source run: `main@33a401dc525662a20a0162dc3e576d2b61470bc3`.

Current governed state remains:

- D4-A: `7/7`;
- D4-B: `5/5`;
- D4-C: `5/9`;
- D4-D: `0/5`;
- D4-wide: `17/26`;
- D4-C candidate: `null / not_selected / candidate_selection_open`;
- D4: `scoped`;
- transport authority: `selected_not_granted`;
- Product/Wave4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

## Candidate classes under evidence

The accepted D4-C evaluation plan permits these concrete candidate classes for this axis:

1. `positive_integer_fenced_generation`;
2. `opaque_fenced_generation_token`;
3. `authority_issued_epoch_generation`.

The generic `equivalent_reviewed_profile` remains an admissible future class but is not auto-credited by this source package.

No candidate is selected or preferred by this source run.

## Required proofs

The source package must prove all seven contract obligations for every concrete candidate class:

1. current platform source generation is explicitly validated at every effectful admission boundary;
2. a retired generation can never regain current authority;
3. failover or restore cannot resurrect a retired source generation;
4. historical fact identity and its historical generation remain distinct from current source authority;
5. tenant/logical source identity remains stable across generation rotation and placement movement;
6. generation comparison is unambiguous and grants authority only by exact equality with the durable current platform generation — numeric magnitude or lexical ordering grants nothing;
7. provider or broker generation metadata cannot become platform source generation by implication or substitution.

## Recovery and failover model

The evidence model treats the durable current platform generation plus durable retirement evidence as the surviving activation fence. A restored snapshot may contribute historical data, but it cannot lower, overwrite, or resurrect the surviving authority state.

Failover may change placement while preserving the same tenant/logical source identity. Placement therefore is not generation, and generation is not tenant/logical identity.

A historical message may remain readable and traceable with the generation that produced it. That historical generation is evidence about origin, not permission to perform a new effect.

## Comparison semantics

This package deliberately rejects the tempting but unsafe rule “larger generation wins.” The effectful admission rule is only:

`presented_platform_generation == durable_current_platform_generation`

subject to the presented generation not being retired.

Therefore:

- a future-looking integer is rejected unless it is exactly current;
- a lexically greater opaque token is rejected unless it is exactly current;
- a provider/broker generation equal to the current platform generation cannot substitute for a stale or missing platform generation.

This prevents accidental ordering semantics from being granted by representation choice.

## Historical/source boundary

The source manifest remains non-promoting:

- `current_run_auto_credit = false`;
- `ledger_credit = []`;
- `OPEN-EVT-013` remains uncredited during this PR;
- current D4-C remains `5/9` and D4-wide remains `17/26`.

If this source PR later passes exact-HEAD CI, provenance admission, panoramic/adversarial review, and is squash-merged with explicit user authorization, a **separate reviewed ledger-promotion PR** is required to move D4-C from `5/9 -> 6/9` and D4-wide from `17/26 -> 18/26`.

That future promotion must still leave D4-C candidate selection and all broader authorities unchanged unless separately reviewed and authorized.

## Machine-enforced evidence

The package contains:

- a deterministic candidate evaluator;
- adversarial falsification tests for stale/future/retired generations, restore resurrection, historical-authority confusion, and provider/broker substitution;
- an exact-schema source validator;
- immutable source-run provenance emission bound to the exact PR HEAD, workflow run, run attempt, job, source manifest, and runtime candidate result digest;
- a dedicated GitHub Actions workflow that re-runs global D4 state assurance and the Phase 10 contract suite.

The workflow uses bounded retries for GitHub Actions job-identity lookup so transient API transport resets do not masquerade as semantic evidence failures; failure after the bounded retry window remains fail-closed.
