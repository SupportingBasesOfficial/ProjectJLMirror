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

When audit evidence is required for a local authoritative mutation, one of the following MUST commit atomically with the mutation:

1. the required audit record itself, when audit storage is inside the same transactional boundary; or
2. a durable audit intent sufficient to deterministically produce the required external audit evidence, when the final audit sink is outside that boundary.

A successful required-audit mutation may not exist in a state where neither the audit record nor its durable atomic intent exists. Post-commit best-effort logging/audit is not sufficient.

## Tamper-resistant external audit intent

An external-sink audit intent is accountability evidence, not a generic mutable delivery job. Its evidence payload MUST receive the same protection class as a local immutable audit record from the moment the business mutation commits.

The committed evidence portion includes the stable audit identity, actor/tenant/action/resource context, safe change/outcome summary, policy/correlation metadata and destination/contract identity required to reproduce the external evidence deterministically. Normal application runtime and ordinary dispatchers MUST NOT be able to rewrite or delete that committed evidence payload.

Mutable delivery state is segregated from immutable evidence. A representative model is:

```text
audit_intent_evidence (append-only / protected)
  audit_intent_id
  immutable evidence payload
  created_at

 audit_delivery_state (mutable by narrow dispatcher role)
  audit_intent_id
  delivery_status
  attempt_count
  next_attempt_at
  last_error_class
  delivered_at / receipt reference
```

Exact table names are implementation details. The normative rule is that retry bookkeeping may change while the accountability statement it is trying to deliver may not be rewritten by normal runtime.

Deletion/retention of audit evidence uses governed administrative policy and separate privilege; an audit-sink outage MUST NOT create a window in which a buggy or compromised dispatcher can erase the only durable evidence of a committed privileged mutation.

External side-effect audit/reconciliation may add subsequent immutable records representing attempts, provider acknowledgements and final outcome; those records do not replace the atomic accountability record/intent for the originating privileged mutation.

## Validation

Fault injection covers crash before mutation commit, immediately after commit, before external audit delivery and during audit-sink outage. Required mutation success is accepted only if local audit evidence or durable audit intent survives and can be reconciled.

Authorization tests prove normal application and dispatcher roles cannot update/delete committed audit evidence payloads. Delivery workers may mutate only explicitly separated delivery metadata. An external audit outage followed by dispatcher compromise/fault simulation must leave the original committed audit evidence intact and reproducible.
