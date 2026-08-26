# Wave 2 — Reconciliation Completion Authority Boundary

**Status:** implementation conformance boundary  
**Authority base:** `main@ff932cec10e3b7dcc13b050bb09d4a7efd634598`  
**Slices:** `impl.cell-data-runtime@1`, `impl.async-core@1`

## Purpose

This boundary prevents a reconciliation-blocked inbox receipt from becoming `completed` merely because a caller presents a plausible `EffectResultLink`.

```text
CALLER-SUPPLIED RESULT LINK != RECONCILIATION COMPLETION AUTHORITY
RECONCILIATION_REQUIRED != CALLER-ASSERTED COMPLETED
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

`complete_local_effect()` models that path. It is not a recovery or reconciliation API.

If the current local claim expires, crashes after an uncertain effect boundary, or otherwise loses deterministic completion proof, the receipt enters `reconciliation_required`. Generic Wave 2 code SHALL NOT recover that uncertainty by accepting an arbitrary caller-provided result object.

## Reconciliation exit

A receipt in `reconciliation_required` may become `completed` only when all of the following are established:

1. the receipt is bound to a stable `operation_id`;
2. the operation authority is durably `completed`;
3. append-only reconciliation evidence records `effect_confirmed`;
4. the reconciliation revision is stable and valid;
5. the confirmed durable outcome exactly matches the result linked by the inbox receipt.

The durable PostgreSQL contract enforces the same rule through `system.async_cross_authority_operation`, `system.async_cross_authority_reconciliation`, and the guarded `system.async_consumer_inbox` transition.

Absence of an `operation_id`, unavailable operation authority, missing reconciliation revision, `still_unknown`, `effect_proven_absent`, or a mismatching outcome leaves completion fail-closed.

## Why no generic local reconciliation shortcut exists

Wave 2 does not invent a second local-result authority after ambiguity. A future owned local-effect reconciliation mechanism may be accepted only if it provides durable evidence equivalent to the accepted operation/reconciliation contract and is reviewed by the owning data/domain authority.

Until then:

```text
UNBOUND RECONCILIATION_REQUIRED -> COMPLETED = PROHIBITED
```

This avoids laundering a diagnostic/caller object into proof that a protected local effect committed.

## Required falsification

Tests SHALL prove:

- an unbound reconciliation-blocked receipt cannot be completed by caller-supplied `EffectResultLink`;
- binding an operation without supplying current reconciliation authority is still insufficient;
- exact append-only `effect_confirmed` operation evidence permits completion only for the matching result identity;
- a mismatching result remains reconciliation-blocked;
- SQL and Python reference semantics remain aligned on this boundary.
