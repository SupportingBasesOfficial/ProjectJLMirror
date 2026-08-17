# Reliability Records, Idempotency and Audit

**Status:** proposed baseline  
**Primary ADRs:** ADR-008, ADR-009, ADR-010

## Outbox

Each authoritative transactional boundary provides durable outbox storage for events that must be published after commit.

Conceptual fields:

```text
id / event_id
contract_name
contract_version
tenant_id nullable only for global event
aggregate_type
aggregate_id
occurred_at
correlation_id
causation_id
payload
state
attempt_count
next_attempt_at
published_at
last_error_class
```

Dispatchers may claim rows concurrently using PostgreSQL-safe claiming/locking semantics. Global ordering is not promised. Per-aggregate ordering is implemented only where a consumer contract requires it.

## Inbox/deduplication

Consumers of at-least-once events maintain durable processed-message identity when duplicate effects would be unsafe.

Conceptual uniqueness:

```text
UNIQUE(consumer_contract, message_id)
```

The receipt/effect is committed atomically where feasible.

## HTTP/API idempotency

For operations exposing idempotency keys:

```text
tenant_id
principal/credential scope when relevant
operation/route contract
idempotency_key
request_fingerprint
status
result_reference / response metadata
created_at
expires_at
```

Reusing the same key with a different request fingerprint returns conflict rather than silently executing a different operation.

Idempotency retention is long enough to cover the accepted retry/replay window for the operation.

## Business process records

Long-running operations such as tenant provisioning/relocation, large exports, reconciliation and complex automation have owner-domain process records with stage/progress/error/resume state. Queue state alone is not the authoritative process history.

## Audit

Audit is accountability, not debug logging.

Conceptual audit fields:

```text
audit_id
tenant_id nullable for global action
actor_principal_id
actor_type
action
resource_type
resource_id
occurred_at
request_id
correlation_id
source/ip/client metadata when policy allows
result
safe before/after or change summary
policy/permission reference
metadata
```

Secrets, credential hashes/tokens and unnecessary regulated data are redacted before persistence.

## Immutability

Normal application runtime may append permitted audit entries but cannot update/delete accepted immutable audit records. Retention/deletion required by law or policy is executed through governed administrative mechanisms, not normal application writes.

High-assurance future requirements MAY replicate/seal audit evidence to an external immutable/WORM sink through a dedicated ADR.

## Audit transactionality

Where an audit record is required for a local authoritative mutation, the audit append SHOULD commit in the same transaction so a successful privileged mutation cannot exist without its accountability record.

External side-effect audit/reconciliation may require subsequent records representing attempts and final provider outcome.
