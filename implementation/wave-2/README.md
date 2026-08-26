# Wave 2 — Transactional Cell and Async Correctness

Wave 2 implements the correctness substrate authorized by the accepted Implementation Readiness sequencing:

- `impl.cell-data-runtime@1`
- `impl.async-core@1`

It does **not** create Product/domain endpoints, incident/customer workflow behavior, provider-specific behavior, realtime behavior or production readiness.

## Fixed semantics implemented here

- PostgreSQL remains the authoritative transactional business/authority truth where accepted by Data/System design.
- A mutation that requires publication persists its immutable outbox message in the same transaction as the authoritative mutation and required audit/accountability intent.
- Delivery remains at-least-once. Outbox claim exclusivity is not exactly-once delivery.
- An expired outbox dispatcher claim may be reclaimed only for delivery of the same immutable logical message; expiry does not prove that a prior broker publication was absent.
- Ambiguous publication retries reuse the same logical message identity.
- Duplicate-sensitive consumers use `(consumer_contract, message_identity_scope, message_id)` and an atomic create-or-observe inbox protocol.
- A benign duplicate additionally requires proven immutable semantic equivalence under a retained comparison profile/evidence authority.
- The canonical inbox key is a lookup key, not the whole trusted authority binding: every authority-bearing lookup revalidates the exact stored `ScopedMessageIdentity`, including tenant binding, before current execution authority is requested.
- The same canonical inbox key with a different trusted tenant binding is integrity failure and cannot claim, complete, reconcile or otherwise act on the stored receipt.
- Inbox identity, trusted tenant binding and retained equivalence evidence are immutable after admission.
- Same scoped identity with conflicting content is integrity failure and enters quarantine/reconciliation; it is never first-wins/last-wins.
- Unknown/lost comparison authority is reconciliation-blocked, not duplicate success and not new effect eligibility.
- Co-resident inbox + protected effect complete atomically where they share one transaction authority.
- Cross-authority effects use a stable immutable `operation_id` **plus exact owner/tenant scope**; the ID alone is not binding, completion or reconciliation authority.
- Every inbox-to-operation binding and every later operation snapshot consumption revalidates `operation_id + tenant_id + owner_contract` against the receipt's immutable trusted scope.
- PostgreSQL applies the same rule to operation-bound inbox rows on both INSERT and UPDATE, so a foreign-key hit cannot prebind a receipt to another tenant/owner operation.
- Ambiguous outcome blocks blind retry until reconciliation proves completion or proves a new attempt eligible.
- Reconciliation evidence is append-only by `(operation_id, reconciliation_revision)` **and bound to the exact `attempt_generation` whose ambiguity it resolves**. Historical proof for attempt N cannot authorize a later ambiguous attempt N+1.
- A reconciliation revision can be created only while that operation is reconciliation-blocked; it cannot be pre-seeded, rewritten or deleted to manufacture later retry authority.
- Canonical cross-authority snapshots carry immutable tenant/owner scope, `attempt_generation` plus `reconciliation_attempt_generation`; a snapshot that mismatches the receipt scope or pairs a later operation attempt with earlier reconciliation evidence is rejected.
- Inbox processing-lease expiry and cross-authority attempt-lease expiry are uncertainty: they transition to reconciliation and never manufacture safe retry/effect absence.
- Every new protected consumer effect/cross-authority attempt requires a revision-bound current execution admission for the exact consumer/operation, tenant scope and accepted API/worker runtime profile.
- Tenant-scoped execution admission carries a trusted Wave 1 `TenantContext`; stale/missing principal generation, placement, runtime generation, environment or authorization evidence fails closed at the adapter boundary.
- Tenant-scoped work re-establishes current placement/TenantContext before protected execution. Message, broker, topic and route metadata do not pin historical placement.
- Delayed work does not preserve old human authorization unless a separately accepted delegation/capability contract says so.
- Critical Wave 2 correctness tables are created fail-closed without `IF NOT EXISTS`; a preexisting same-name object requires reviewed shape/authority revalidation rather than silent reuse.
- Every committed outbox message creates its dispatch bookkeeping row in the same transaction through a `SECURITY INVOKER` trigger; a committed message cannot be stranded merely because a second insert was forgotten.
- SQL transition guards prevent ordinary direct UPDATE from rebinding inbox/operation scope, stealing same-state claims, resurrecting terminal state, resetting published/quarantined dispatch, or converting reconciliation uncertainty directly into retry authority.
- Quarantine/redrive is exposed only through a **current privileged authority hook**. A redrive request is bound to the exact message scope, tenant, requested quarantine generation, reason class, operation identity, correlation context and accepted reliability profile.
- The request is only the scope to verify; it is **not proof that the subject is currently quarantined**. The trusted redrive authority must independently re-resolve durable current quarantine state and return a non-empty `quarantine_state_revision` before eligibility can be accepted.
- Redrive admission requires current privileged authorization, owning-contract compatibility/eligibility, effect-safety evidence, capacity admission, audit responsibility and current tenant placement where applicable. Queue age, operator desire, broker DLQ state and time in quarantine are not authority.
- Wave 2 does not implement the Phase 15 `ops.redrive-operation@1` store/workflow; it exposes the correctness boundary that future operations tooling must satisfy.

## Reliability profile joins

The implementation binds the logical reliability profiles required by the accepted slice/readiness baseline:

- `rel.cell-transactional-store@1`
- `rel.outbox-publication@1`
- `rel.broker-job-transport@1`
- `rel.consumer-inbox-effect@1`
- `rel.replay-consume-state@1`

These are **vendor-neutral correctness profiles**, not product selections. In particular, binding `rel.broker-job-transport@1` does not select a broker, queue, cloud service or topology.

## Replaceable C2 boundaries

This wave deliberately does not select a broker, schema registry/serializer, cache/replay product, KMS/historical-verifier backend, database HA/pooler runtime mapping, exact claim/lease duration or reconciliation UI/tool.

The Python package is a portable correctness/reference core using only the standard library. The SQL package is the PostgreSQL durable-record contract for the accepted transactional substrate; it is not a broker selection and it does not claim production topology. `CurrentAsyncExecutionAuthorityPort` is an adapter boundary over accepted current principal/placement/authorization/runtime/fence authorities; it is not a second authorization system. `CurrentRedriveAuthorityPort` is a privileged eligibility boundary for a future operations redrive workflow; it does not select or implement that workflow. Concrete reconciliation/redrive tooling remains C2/operations scope, but any selected tool must preserve the fixed operation-scoped evidence and exact current-authority semantics.

## Product/operations clarification boundary

If implementation later requires a decision such as what a customer sees during an incident, whether an operation cancels/waits/compensates after authorization revocation, notification/escalation behavior, or any other business/operational policy not already accepted, that decision remains blocked until explicit Product/operations clarification. Wave 2 must not manufacture that policy through defaults.

## Correctness laws

```text
LEASE EXPIRY != EFFECT ABSENCE
CURRENT EXECUTION ADMISSION != MESSAGE PAYLOAD AUTHORITY
CANONICAL INBOX LOOKUP KEY != COMPLETE TRUSTED RECEIPT IDENTITY
SAME INBOX KEY != BENIGN DUPLICATE WHEN TRUSTED BINDING DIFFERS
OPERATION ID != OPERATION AUTHORITY SCOPE
OPERATION BINDING/COMPLETION/RECONCILIATION -> EXACT OPERATION ID + TENANT + OWNER
RECONCILIATION_REQUIRED != RETRY ELIGIBLE
RECONCILIATION REVISION STRING != EVIDENCE WITHOUT APPEND-ONLY RECORD
RECONCILIATION REVISION != ATTEMPT-GENERATION-AGNOSTIC CAPABILITY
PRIOR ATTEMPT RECONCILIATION EVIDENCE != LATER ATTEMPT RETRY AUTHORITY
PRESEEDED/MUTATED RECONCILIATION EVIDENCE != AUTHORITY
DIRECT STATE UPDATE != RECONCILIATION AUTHORITY
PREEXISTING TABLE NAME != CORRECTNESS SCHEMA CONFORMANCE
OUTBOX CLAIM RECOVERY -> SAME LOGICAL MESSAGE IDENTITY
INBOX/EXTERNAL ATTEMPT LEASE LOSS -> RECONCILIATION, NOT BLIND RETRY
QUARANTINE != REDRIVE ELIGIBILITY
REDRIVE REQUEST != QUARANTINE STATE AUTHORITY
QUEUE AGE / OPERATOR DESIRE / VENDOR DLQ STATE != REDRIVE AUTHORITY
RELIABILITY PROFILE != TRANSPORT PRODUCT SELECTION
WAVE 2 AUTHORIZED != WAVE 3 AUTHORIZED
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
