# Consistency, Transactions and Asynchronous Processing

**Status:** proposed baseline  
**Primary ADRs:** ADR-001, ADR-008, ADR-009, ADR-010

## Transaction ownership

The **application use case** owns the transaction boundary for authoritative mutations. Transport controllers do not perform ad-hoc persistence sequences.

A normal same-cell mutation follows:

```text
BEGIN
  establish transaction-local tenant context
  validate invariant/current state
  mutate owning-domain state
  write required audit accountability record
  append outbox records for committed integration/domain publication
COMMIT
```

The transaction does not include calls to external providers, email, WebSocket, payment networks, webhook destinations or another cell.

## Cross-domain synchronous work

Within the modular monolith, an application use case MAY invoke another domain's explicit application contract synchronously when an invariant truly requires immediate co-transactional behavior and both owners are in the same cell database boundary.

This does not permit direct mutation of another domain's tables. If no strong-consistency invariant requires synchronous coupling, prefer an event/process flow.

## Cross-cell/external consistency

JLMIRROR does not assume distributed ACID transactions across cells or external systems. Multi-step cross-boundary workflows use persisted process state, outbox/inbox, reconciliation and compensating/forward-recovery actions as appropriate.

## Outbox

A durable outbox entry is inserted in the same transaction as the authoritative mutation. Publication occurs after commit.

Required logical fields:

```text
event_id
contract_name
contract_version
tenant_id (nullable only for global events)
aggregate_type
aggregate_id
occurred_at
correlation_id
causation_id
payload
publish_state / attempt metadata
```

Secrets are forbidden in payloads.

## Delivery semantics

Default integration/event/job semantics are **at least once**. Exactly-once claims require proof at the business side-effect level and are not inferred from broker semantics.

Consumers therefore implement one or more of:

- inbox receipt/deduplication;
- idempotency key;
- natural unique business constraint;
- compare-and-set/version transition;
- reconciliation against authoritative provider state.

## Inbox

A consumer records `(consumer_id, message/event_id)` or equivalent durable deduplication identity before/with effectful processing in the appropriate transaction. Duplicate messages produce the already-known logical result or no-op rather than duplicate irreversible effects.

## Jobs

A job is a command to perform work, not a statement that work occurred.

A durable job contract includes:

```text
job_id
job_type
contract_version
tenant_id (when tenant-scoped)
operation_id (for side effects)
correlation_id
causation_id
created_at
not_before / deadline when relevant
payload (validated, secret-free)
```

The worker re-resolves tenant placement and establishes its own TenantContext.

## Retry classification

Errors are classified:

- transient/retriable;
- throttled/retriable with server/provider hint;
- permanent contract/validation failure;
- authorization/policy denial;
- poison/unknown requiring bounded retry then quarantine;
- stale placement requiring re-resolution rather than blind retry.

Retry uses bounded attempts, backoff/jitter and workload-specific concurrency budgets.

## Process managers

Long-running workflows such as tenant provisioning, tenant relocation, large export, payment reconciliation or complex automation use persisted process state with explicit stages. Process progress is observable and resumable; it is not held only in memory or a single request.
