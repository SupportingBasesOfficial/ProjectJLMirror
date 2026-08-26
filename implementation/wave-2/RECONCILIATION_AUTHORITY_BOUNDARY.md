# Wave 2 — Reconciliation and Cross-Authority Completion Boundary

**Status:** implementation conformance boundary  
**Authority base:** `main@ff932cec10e3b7dcc13b050bb09d4a7efd634598`  
**Slices:** `impl.cell-data-runtime@1`, `impl.async-core@1`

## Purpose

This boundary prevents an inbox receipt from becoming `completed` through a result object that is not backed by the authority that owns the protected effect.

```text
CALLER-SUPPLIED RESULT LINK != EFFECT COMPLETION AUTHORITY
OPERATION-BOUND RECEIPT != LOCAL EFFECT PATH
RECONCILIATION_REQUIRED != CALLER-ASSERTED COMPLETED
LOCAL ATOMIC COMPLETION != CROSS-AUTHORITY COMPLETION
LOCAL ATOMIC COMPLETION != POST-AMBIGUITY RECONCILIATION
```

## Local co-resident effect

When inbox state and the owning protected effect share one transaction authority, normal completion occurs through the current executor while the claim/admission is valid:

```text
current receipt claim
+ current execution admission
+ owning local effect/result
+ inbox completion/result linkage
-> same authoritative transaction boundary
```

`complete_local_effect()` models only that path. It is prohibited after the receipt has been bound to a stable cross-authority `operation_id`.

If the current local claim expires, crashes after an uncertain effect boundary, or otherwise loses deterministic completion proof, the receipt enters `reconciliation_required`. Generic Wave 2 code SHALL NOT recover that uncertainty by accepting an arbitrary caller-provided result object.

## Direct cross-authority completion

Once a current processing receipt is bound to `operation_id`, the completion authority moves to that stable operation boundary for that effect.

A direct, non-ambiguous cross-authority completion requires:

1. the current inbox claim is still valid;
2. the receipt remains bound to the same stable `operation_id`;
3. the operation authority is durably `completed`;
4. the operation has no reconciliation revision/resolution, proving this is the direct-success path rather than laundering a reconciled result through ordinary processing completion;
5. the durable operation outcome exactly matches the result linked by the inbox receipt.

`complete_cross_authority_effect()` models this path. `complete_local_effect()` SHALL reject an operation-bound receipt.

The PostgreSQL trigger enforces the same distinction for `processing -> completed`: a row with `operation_id` can complete only when the bound operation is directly `completed` with the exact same durable result and no reconciliation evidence attached.

## Reconciliation exit

A receipt in `reconciliation_required` may become `completed` only when all of the following are established:

1. the receipt is bound to a stable `operation_id`;
2. the operation authority is durably `completed`;
3. append-only reconciliation evidence records `effect_confirmed`;
4. the reconciliation revision is stable and valid;
5. the confirmed durable outcome exactly matches the result linked by the inbox receipt.

The durable PostgreSQL contract enforces the same rule through `system.async_cross_authority_operation`, `system.async_cross_authority_reconciliation`, and the guarded `system.async_consumer_inbox` transition.

Absence of an `operation_id`, unavailable operation authority, missing reconciliation revision, `still_unknown`, `effect_proven_absent`, or a mismatching outcome leaves completion fail-closed.

A reconciled operation cannot be laundered back through the ordinary `processing -> completed` path. It must use the `reconciliation_required -> completed` transition bound to the append-only reconciliation revision.

## Why no generic local reconciliation shortcut exists

Wave 2 does not invent a second local-result authority after ambiguity. A future owned local-effect reconciliation mechanism may be accepted only if it provides durable evidence equivalent to the accepted operation/reconciliation contract and is reviewed by the owning data/domain authority.

Until then:

```text
UNBOUND RECONCILIATION_REQUIRED -> COMPLETED = PROHIBITED
OPERATION-BOUND PROCESSING -> LOCAL COMPLETION = PROHIBITED
RECONCILED OPERATION -> DIRECT PROCESSING COMPLETION = PROHIBITED
```

This avoids laundering a diagnostic/caller object into proof that a protected effect committed.

## Required falsification

Tests SHALL prove:

- an operation-bound processing receipt cannot use the local completion path;
- direct cross-authority completion requires a durable `completed` operation with the exact matching outcome;
- a mismatching direct operation outcome remains processing/blocked;
- an operation completed through reconciliation cannot use the direct processing-completion path;
- an unbound reconciliation-blocked receipt cannot be completed by caller-supplied `EffectResultLink`;
- binding an operation without supplying current reconciliation authority is still insufficient;
- exact append-only `effect_confirmed` operation evidence permits reconciliation completion only for the matching result identity;
- a mismatching reconciled result remains reconciliation-blocked;
- SQL and Python reference semantics remain aligned on this boundary.
