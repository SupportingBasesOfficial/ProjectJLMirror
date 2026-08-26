# Wave 2 — Transactional Cell and Async Correctness

Wave 2 implements the correctness substrate authorized by the accepted Implementation Readiness sequencing:

- `impl.cell-data-runtime@1`
- `impl.async-core@1`

It does **not** create Product/domain endpoints, incident/customer workflow behavior, provider-specific behavior, realtime behavior or production readiness.

## Fixed semantics implemented here

- PostgreSQL remains the authoritative transactional business/authority truth where accepted by Data/System design.
- A mutation that requires publication persists its immutable outbox message in the same transaction as the authoritative mutation and required audit/accountability intent.
- Delivery remains at-least-once. Outbox claim exclusivity is not exactly-once delivery.
- Ambiguous publication retries reuse the same logical message identity.
- Duplicate-sensitive consumers use `(consumer_contract, message_identity_scope, message_id)` and an atomic create-or-observe inbox protocol.
- A benign duplicate additionally requires proven immutable semantic equivalence under a retained comparison profile/evidence authority.
- Same scoped identity with conflicting content is integrity failure and enters quarantine/reconciliation; it is never first-wins/last-wins.
- Unknown/lost comparison authority is reconciliation-blocked, not duplicate success and not new effect eligibility.
- Co-resident inbox + protected effect complete atomically where they share one transaction authority.
- Cross-authority effects use a stable `operation_id`; ambiguous outcome blocks blind retry until reconciliation proves completion or proves a new attempt eligible.
- Tenant-scoped work re-establishes current placement/TenantContext before protected execution. Message, broker, topic and route metadata do not pin historical placement.
- Delayed work does not preserve old human authorization unless a separately accepted delegation/capability contract says so.

## Replaceable C2 boundaries

This wave deliberately does not select a broker, schema registry/serializer, cache/replay product, KMS/historical-verifier backend, database HA/pooler runtime mapping or reconciliation UI/tool.

The Python package is a portable correctness/reference core using only the standard library. The SQL package is the PostgreSQL durable-record contract for the accepted transactional substrate; it is not a broker selection and it does not claim production topology.

## Product/operations clarification boundary

If implementation later requires a decision such as what a customer sees during an incident, whether an operation cancels/waits/compensates after authorization revocation, notification/escalation behavior, or any other business/operational policy not already accepted, that decision remains blocked until explicit Product/operations clarification. Wave 2 must not manufacture that policy through defaults.
