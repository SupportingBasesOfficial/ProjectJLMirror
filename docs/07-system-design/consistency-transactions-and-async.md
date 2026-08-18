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

## Idempotent request admission

When an API/application operation exposes an idempotency key to prevent duplicate logical effects, the request MUST acquire or observe a durable single-winner idempotency claim **before effectful processing begins**.

The effective claim identity is server-derived and includes the operation's canonical idempotency scope plus the caller-provided key. The durable store enforces uniqueness on that identity. Application code MUST NOT implement exclusivity with an unprotected read-then-create sequence.

Conceptual flow:

```text
request
  -> derive canonical idempotency scope
  -> atomic create-or-observe claim
       |
       +-- new claim + matching fingerprint -> this request owns execution
       +-- existing claim + different fingerprint -> conflict; no execution
       +-- existing in-progress claim + same fingerprint -> join/retry contract; no second execution
       +-- existing completed claim + same fingerprint -> replay logical result
```

Only the request that atomically acquires executable ownership may start the logical effect.

### Local completion and replay

For an idempotent authoritative mutation that is co-resident with its claim in the same cell database, the operation is not considered durably complete until the domain effect and replay state are committed together.

Preferred flow:

```text
BEGIN
  lock/CAS executable claim
  perform local domain mutation
  persist required audit/outbox
  persist stable result reference / replay metadata
  mark claim completed
COMMIT
```

This creates two safe crash classes:

- before commit: no committed domain mutation and no completed claim;
- after commit: committed mutation plus completed/replayable claim, even if the HTTP response is lost.

A retry therefore observes durable truth rather than deciding whether to re-run based on process liveness. A committed local mutation with only an unrecoverable `in_progress` claim and no stable result linkage is forbidden.

If claim and local effect are in different persistence authorities, the authoritative effect MUST atomically record a stable `operation_id`/result identity with the mutation. Claim recovery reconciles that record and finalizes the claim idempotently; it does not blindly execute the mutation again.

For externally irreversible work, the claim carries or derives a stable `operation_id`; a crash/timeout with ambiguous external outcome enters reconciliation rather than allowing another contender to execute blindly.

The exact HTTP header/status representation is defined later in API-contract design. The unique-scope, atomic-claim, single-executor and crash-consistent result-linkage semantics are system-design invariants.

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

An expired local idempotency lease/timeout, if a later implementation uses leases, is not by itself proof that an effect did not occur. Local retries first reconcile durable domain/result state; externally ambiguous outcomes reconcile by stable operation identity before a new attempt becomes eligible.

## Process managers

Long-running workflows such as tenant provisioning, tenant relocation, large export, payment reconciliation or complex automation use persisted process state with explicit stages. Process progress is observable and resumable; it is not held only in memory or a single request.
