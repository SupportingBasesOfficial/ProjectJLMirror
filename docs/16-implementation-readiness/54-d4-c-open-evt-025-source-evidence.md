# D4-C OPEN-EVT-025 Recovery Generation Source Evidence

## Status

This artifact defines **source evidence only** for the final D4-C obligation, `OPEN-EVT-025`.

It does not select a D4-C candidate, does not auto-credit the ledger, and does not grant D4, product, Wave 4, production, or C3 numeric/topology authority.

## Evidence obligation

- source decision: `OPEN-EVT-025`
- evidence: `recovery_generation_rf_inventory_reconciliation_and_activation_gates`
- source-time D4-C ledger: **8/9**
- source-time D4-wide ledger: **20/26**
- source-time OPEN-EVT-025 credit: **uncredited**

## Candidate classes exercised

1. restore-generation fence manifest profile;
2. reconciliation inventory job plus activation gate profile;
3. hybrid generation manifest plus multi-store reconciler profile.

The run evaluates all three classes without selecting one.

## Proof surface

The executable package proves all twelve OPEN-EVT-025 obligations from the canonical D4-C candidate-evaluation plan, including:

- explicit durable restore/fence generations;
- R/F inventory across broker history, inbox, outbox, equivalence evidence, external-effect evidence, and webhook delivery evidence;
- stable webhook delivery identity plus destination-generation fencing;
- missing restored state represented as uncertainty, never absence;
- stale or unverifiable equivalence evidence rejected as duplicate proof;
- stale historical verifier/comparison-profile authority rejected;
- duplicate-sensitive and effectful admission fail-closed until reconciliation is complete;
- stale producer, replay-authorization, and destination generations rejected;
- surviving external-effect evidence cannot be overridden by offsets/inbox/outbox claiming absence;
- activation remains closed until generation-scoped reconciliation succeeds;
- successful reconciliation is auditable and deterministically reproducible.

## Falsification cases

The test harness explicitly rejects:

- missing required restored stores/evidence;
- stale equivalence generation;
- blank/unverifiable comparison evidence;
- stale producer generation;
- stale replay authorization generation;
- stale destination generation;
- obsolete historical verifier generation;
- obsolete comparison-profile generation.

## Authority boundary

The source manifest and workflow require:

- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- `selection_state=not_selected`;
- D4-C remains `8/9` with OPEN-EVT-025 as the sole remaining evidence;
- D4-D remains `0/5`;
- D4 remains `scoped`;
- transport authority remains `selected_not_granted`;
- product/Wave4 authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

Any ledger promotion to D4-C `9/9` requires a separate reviewed promotion gate bound to an exact successful source run.
