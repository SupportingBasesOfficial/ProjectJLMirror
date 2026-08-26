# Wave 2 — Reconciliation and Cross-Authority Completion Boundary

**Status:** implementation conformance boundary  
**Authority base:** `main@ff932cec10e3b7dcc13b050bb09d4a7efd634598`  
**Slices:** `impl.cell-data-runtime@1`, `impl.async-core@1`

## Purpose

This boundary prevents an inbox receipt from becoming `completed` through a result object that is not backed by the authority that owns the protected effect, prevents reconciliation evidence from one attempt from becoming current authority for its successor, prevents TOCTOU assembly of an operation decision from mutually inconsistent reads, and prevents a technical inbox/operation identifier from laundering tenant or owner authority.

```text
CALLER-SUPPLIED RESULT LINK != EFFECT COMPLETION AUTHORITY
CANONICAL INBOX LOOKUP KEY != COMPLETE TRUSTED RECEIPT IDENTITY
OPERATION ID != OPERATION AUTHORITY SCOPE
OPERATION-BOUND RECEIPT != LOCAL EFFECT PATH
RECONCILIATION_REQUIRED != CALLER-ASSERTED COMPLETED
LOCAL ATOMIC COMPLETION != CROSS-AUTHORITY COMPLETION
LOCAL ATOMIC COMPLETION != POST-AMBIGUITY RECONCILIATION
RECONCILIATION HISTORY != CURRENT ATTEMPT RESOLUTION
PRIOR ATTEMPT ABSENCE PROOF != SUCCESSOR ATTEMPT OUTCOME
PRIOR ATTEMPT RECONCILIATION EVIDENCE != LATER ATTEMPT RETRY AUTHORITY
RECONCILIATION REVISION != ATTEMPT-GENERATION-AGNOSTIC CAPABILITY
SPLIT OPERATION READS != ATOMIC AUTHORITY SNAPSHOT
```

## Trusted receipt identity

`(consumer_contract, message_identity_scope, message_id)` is the canonical inbox lookup key, but a lookup-key hit does not authorize use of a receipt under a different supplemental trusted binding.

Every authority-bearing lookup compares the supplied `ScopedMessageIdentity` to the exact stored identity before current execution admission, claim mutation, completion or reconciliation can proceed. In particular, a caller cannot reuse the same three-part key with another `tenant_id` and cause current execution authority to be requested for that different tenant.

```text
SAME LOOKUP KEY + DIFFERENT TRUSTED TENANT != SAME RECEIPT AUTHORITY
```

## Immutable operation authority scope

A stable cross-authority operation is identified and authorized by the tuple:

```text
operation_id
+ tenant_id            # nullable only for genuinely global operation scope
+ owner_contract
```

The `operation_id` is stable identity, not a capability token. When an inbox receipt is bound to an operation, the operation authority must prove that its exact immutable tenant and owner contract match the receipt's stored trusted `tenant_id` and `consumer_contract`.

The same check is repeated when the operation snapshot is later consumed for direct completion, retry eligibility or reconciled completion. This prevents an adapter, stale pointer or malicious caller from changing only the operation object behind a previously stored ID.

PostgreSQL enforces the same invariant on every operation-bound inbox `INSERT` and `UPDATE`. The foreign key to `operation_id` proves existence only; a separate `SECURITY INVOKER` trigger validates exact tenant/owner scope before the row can become durable.

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

## Atomic operation authority observation

Any inbox decision that depends on a cross-authority operation consumes **one coherent operation snapshot** for the stable scoped operation.

The snapshot binds together at least:

```text
operation_id
tenant_id
owner_contract
state
attempt_generation
outcome
reconciliation_resolution
reconciliation_revision
```

A consumer SHALL NOT decide retry/completion by independently reading scope, state, outcome, resolution and revision and then assembling those values locally. Separate reads can cross a concurrent state transition and produce a tuple that never existed as durable authority.

The canonical snapshot type rejects internally impossible state/reconciliation combinations, and inbox consumption fails closed if the snapshot's tenant/owner scope differs from the stored receipt. The in-memory operation ledger creates the snapshot under one lock. The PostgreSQL transition/scope guards obtain corresponding operation/evidence fields in locked queries/joins.

## Direct cross-authority completion

Once a current processing receipt is bound to a scoped `operation_id`, the completion authority moves to that stable operation boundary for that effect.

A direct, non-ambiguous cross-authority completion requires:

1. the current inbox claim is still valid;
2. the supplied claim identity exactly equals the stored trusted receipt identity;
3. the receipt remains bound to the same stable `operation_id`;
4. the operation snapshot has the exact receipt `tenant_id + consumer_contract` authority scope;
5. one atomic operation snapshot is durably `completed`;
6. the current attempt has no reconciliation revision/resolution;
7. the snapshot outcome exactly matches the result linked by the inbox receipt.

`complete_cross_authority_effect()` models this path. `complete_local_effect()` SHALL reject an operation-bound receipt.

The PostgreSQL guards enforce the same distinction for `processing -> completed`: an operation-bound row must preserve exact tenant/owner scope in addition to satisfying the direct completed-operation outcome rules.

## Reconciliation exit

A receipt in `reconciliation_required` may become `completed` only when all of the following are established in one coherent authority observation:

1. the supplied receipt identity exactly matches the stored trusted identity;
2. the receipt is bound to a stable `operation_id`;
3. operation tenant/owner scope exactly matches the receipt tenant/consumer contract;
4. the operation authority is durably `completed`;
5. append-only reconciliation evidence records `effect_confirmed`;
6. the reconciliation revision is stable and valid;
7. that evidence is bound to the operation's exact current `attempt_generation`;
8. the confirmed durable outcome exactly matches the result linked by the inbox receipt.

The durable PostgreSQL contract enforces the same rule through `system.async_cross_authority_operation`, `system.async_cross_authority_reconciliation`, the guarded `system.async_consumer_inbox` transition, and the operation-scope guard added after migrations 001..005.

Absence of an `operation_id`, unavailable/incomplete operation authority, tenant/owner mismatch, missing reconciliation revision, attempt-generation mismatch, `still_unknown`, `effect_proven_absent`, or a mismatching outcome leaves completion fail-closed.

A reconciled operation cannot be laundered back through the ordinary `processing -> completed` path. It must use the `reconciliation_required -> completed` transition bound to the append-only reconciliation revision for the exact ambiguous attempt.

## Attempt-bound reconciliation evidence

Every append-only reconciliation row resolves one exact cross-authority effect attempt:

```text
operation_id
attempt_generation
reconciliation_revision
resolution
confirmed outcome when applicable
```

`attempt_generation` is authority context, not diagnostic metadata. The reconciler records evidence only while the operation is `reconciliation_required`, and the evidence generation must equal the operation's current ambiguous attempt generation at insertion time.

A reconciliation revision remains globally stable within the operation. Reusing the same revision in another attempt would change its immutable meaning and fails closed. Creating a successor attempt clears only the mutable current-resolution pointer; it does not erase the historical row or allow that row to answer a later ambiguity.

Therefore this sequence is prohibited:

```text
attempt 1 -> ambiguous
attempt 1 -> effect_proven_absent revision R1
attempt 2 -> ambiguous
reuse R1 -> attempt 3 eligible
```

Attempt 2 requires new accepted reconciliation evidence bound to attempt generation 2. Missing new evidence remains `reconciliation_required`.

## Successor-attempt handoff

`effect_proven_absent` may make the stable operation eligible for another attempt. The evidence proving the previous attempt absent remains immutable history in the append-only reconciliation record.

It is **not** the resolution of the successor attempt.

Before a new operation attempt becomes `attempting`:

- the previous reconciliation revision/resolution pointer is consumed from the mutable current-operation state;
- the historical evidence row remains retained and addressable with its original `attempt_generation`;
- `attempt_generation` advances exactly once;
- fresh current execution admission is required.

Likewise, when a reconciliation-re-admitted inbox receipt is claimed for the successor attempt, the prior receipt reconciliation pointer is consumed before `processing` begins. The bound operation tuple remains stable.

This permits a later direct success to be represented as direct success for the new attempt while preserving proof of why the earlier attempt was allowed to retry.

## Why no generic local reconciliation shortcut exists

Wave 2 does not invent a second local-result authority after ambiguity. A future owned local-effect reconciliation mechanism may be accepted only if it provides durable evidence equivalent to the accepted operation/reconciliation contract and is reviewed by the owning data/domain authority.

Until then:

```text
UNBOUND RECONCILIATION_REQUIRED -> COMPLETED = PROHIBITED
CROSS-TENANT/CROSS-OWNER OPERATION BINDING -> RECEIPT AUTHORITY = PROHIBITED
OPERATION-BOUND PROCESSING -> LOCAL COMPLETION = PROHIBITED
RECONCILED OPERATION -> DIRECT PROCESSING COMPLETION = PROHIBITED
PRIOR RECONCILIATION POINTER -> SUCCESSOR CURRENT ATTEMPT = PROHIBITED
PRIOR ATTEMPT RECONCILIATION EVIDENCE -> LATER AMBIGUOUS ATTEMPT = PROHIBITED
SPLIT SCOPE/STATE/OUTCOME/RESOLUTION/REVISION READS -> AUTHORITY DECISION = PROHIBITED
```

## Required falsification

Tests SHALL prove:

- a second identity with the same canonical inbox key but another trusted tenant cannot claim the stored receipt and does not reach current execution authority;
- binding an operation from another tenant fails and leaves the receipt unbound;
- binding an operation owned by another contract fails and leaves the receipt unbound;
- a valid operation binding requires exact `operation_id + tenant_id + owner_contract` scope;
- direct/reconciled completion rechecks the operation scope rather than trusting the previously stored ID;
- the SQL guard applies the same scope check on both INSERT and UPDATE without `SECURITY DEFINER` or runtime grants;
- an operation-bound processing receipt cannot use the local completion path;
- direct cross-authority completion requires a durable `completed` operation with the exact matching outcome;
- a mismatching direct operation outcome remains processing/blocked;
- an operation completed through reconciliation cannot use the direct processing-completion path;
- an unbound reconciliation-blocked receipt cannot be completed by caller-supplied `EffectResultLink`;
- exact append-only `effect_confirmed` operation evidence permits reconciliation completion only for the matching result identity and exact scope;
- a mismatching reconciled result remains reconciliation-blocked;
- `effect_proven_absent` evidence survives as append-only history while its mutable pointer is cleared before the successor attempt;
- historical reconciliation evidence records the exact attempt generation it resolved;
- after attempt 2 becomes ambiguous, a revision/evidence record from attempt 1 cannot make attempt 2 retry-eligible;
- a successor attempt can complete directly after a proven-absent predecessor without inheriting the predecessor resolution;
- impossible mixed operation snapshots are rejected;
- inbox cross-authority decisions consume one scoped snapshot and never fall back to split scope/state/outcome/reconciliation reads;
- SQL and Python reference semantics remain aligned on scope, attempt-generation binding and all other boundaries above.
