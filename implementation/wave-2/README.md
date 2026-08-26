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
- The canonical inbox key is not permission to ignore conflicting supplemental trusted scope: the same key with a different trusted tenant binding is integrity failure.
- Inbox identity, trusted tenant binding and retained equivalence evidence are immutable after admission.
- Same scoped identity with conflicting content is integrity failure and enters quarantine/reconciliation; it is never first-wins/last-wins.
- Unknown/lost comparison authority is reconciliation-blocked, not duplicate success and not new effect eligibility.
- Co-resident inbox + protected effect complete atomically where they share one transaction authority.
- Cross-authority effects use a stable immutable `operation_id` + owner/tenant scope; ambiguous outcome blocks blind retry until reconciliation proves completion or proves a new attempt eligible.
- Reconciliation stores a stable `reconciliation_revision` plus canonical `still_unknown`, `effect_confirmed` or `effect_proven_absent` disposition. Retry/completion cannot be manufactured by state mutation without that evidence.
- Inbox processing-lease expiry and cross-authority attempt-lease expiry are uncertainty: they transition to reconciliation and never manufacture safe retry/effect absence.
- Every new protected consumer effect/cross-authority attempt requires a revision-bound current execution admission for the exact consumer/operation, tenant scope and accepted API/worker runtime profile.
- Tenant-scoped execution admission carries a trusted Wave 1 `TenantContext`; stale/missing principal generation, placement, runtime generation, environment or authorization evidence fails closed at the adapter boundary.
- Tenant-scoped work re-establishes current placement/TenantContext before protected execution. Message, broker, topic and route metadata do not pin historical placement.
- Delayed work does not preserve old human authorization unless a separately accepted delegation/capability contract says so.
- Critical Wave 2 correctness tables are created fail-closed without `IF NOT EXISTS`; a preexisting same-name object requires reviewed shape/authority revalidation rather than silent reuse.
- Every committed outbox message creates its dispatch bookkeeping row in the same transaction through a `SECURITY INVOKER` trigger; a committed message cannot be stranded merely because a second insert was forgotten.
- SQL transition guards prevent ordinary direct UPDATE from rebinding inbox/operation scope, resurrecting terminal state, resetting published/quarantined dispatch, or converting reconciliation uncertainty directly into retry authority.

## Replaceable C2 boundaries

This wave deliberately does not select a broker, schema registry/serializer, cache/replay product, KMS/historical-verifier backend, database HA/pooler runtime mapping, exact claim/lease duration or reconciliation UI/tool.

The Python package is a portable correctness/reference core using only the standard library. The SQL package is the PostgreSQL durable-record contract for the accepted transactional substrate; it is not a broker selection and it does not claim production topology. `CurrentAsyncExecutionAuthorityPort` is an adapter boundary over accepted current principal/placement/authorization/runtime/fence authorities; it is not a second authorization system. Concrete reconciliation tooling remains C2, but any selected tool must persist the fixed revision/resolution evidence before retry eligibility changes.

## Product/operations clarification boundary

If implementation later requires a decision such as what a customer sees during an incident, whether an operation cancels/waits/compensates after authorization revocation, notification/escalation behavior, or any other business/operational policy not already accepted, that decision remains blocked until explicit Product/operations clarification. Wave 2 must not manufacture that policy through defaults.

## Correctness laws

```text
LEASE EXPIRY != EFFECT ABSENCE
CURRENT EXECUTION ADMISSION != MESSAGE PAYLOAD AUTHORITY
SAME INBOX KEY != BENIGN DUPLICATE WHEN TRUSTED BINDING DIFFERS
RECONCILIATION_REQUIRED != RETRY ELIGIBLE
RECONCILIATION RESOLUTION WITHOUT DURABLE REVISION != AUTHORITY
DIRECT STATE UPDATE != RECONCILIATION AUTHORITY
PREEXISTING TABLE NAME != CORRECTNESS SCHEMA CONFORMANCE
OUTBOX CLAIM RECOVERY -> SAME LOGICAL MESSAGE IDENTITY
INBOX/EXTERNAL ATTEMPT LEASE LOSS -> RECONCILIATION, NOT BLIND RETRY
WAVE 2 AUTHORIZED != WAVE 3 AUTHORIZED
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
