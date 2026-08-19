# Reliability Records, Idempotency and Audit

**Status:** accepted  
**Primary ADRs:** ADR-008, ADR-009, ADR-010, ADR-018

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

A raw `message_id` is not assumed globally unique across all tenants, integrations, providers or producers. Every inbox contract defines a **non-null authoritative message identity scope** that namespaces the producer/source domain in which `message_id` is unique.

Conceptual fields include:

```text
consumer_contract
message_identity_scope   non-null canonical trusted namespace
message_id
source/producer metadata when required for audit/reconciliation
tenant_id when tenant-scoped
status / result linkage
```

Conceptual uniqueness:

```text
UNIQUE(consumer_contract, message_identity_scope, message_id)
```

`message_identity_scope` is server-derived from trusted envelope/integration/producer context and includes every dimension required to prevent collisions, such as tenant/global boundary, provider/integration/source identity and source generation/stream when applicable. Caller-controlled payload text does not get to choose a namespace that weakens isolation.

A consumer MAY use a constant/global scope only when its contract explicitly guarantees `message_id` uniqueness across every producer/source capable of feeding that consumer for the full deduplication retention window. Otherwise the authoritative source namespace is mandatory.

This prevents, for example, Tenant A's provider event `42` from suppressing Tenant B's unrelated provider event `42`, while still allowing an exact redelivery of the same trusted scoped message to deduplicate.

Inbox deduplication is not merely a pre-processing lookup. The receipt and the logical effect it protects require a crash-safe completion protocol.

### Co-resident inbox effect completion

When the inbox receipt and the authoritative consumer effect are co-resident in the same transactional database boundary, they SHALL commit atomically. A representative pattern is:

```text
BEGIN
  derive trusted message_identity_scope
  create/lock inbox receipt for (consumer_contract, message_identity_scope, message_id)
  verify not already completed
  perform authoritative local consumer effect
  persist required audit/outbox/result linkage
  mark inbox receipt completed with stable effect/result reference
COMMIT
```

The consumer MUST NOT durably mark a message processed before the protected local effect is durable, and MUST NOT commit the local effect while leaving no durable completed receipt/result linkage from which redelivery can deterministically no-op or replay the established result.

Therefore:

- crash before commit leaves neither a completed receipt nor committed local effect;
- crash after commit leaves both the local effect and completed receipt/result linkage durable;
- redelivery after response/ack loss observes the completed receipt and MUST NOT execute the logical effect again;
- the same raw `message_id` in a different trusted tenant/source namespace remains independently processable and MUST NOT be suppressed by another scope's receipt.

### Cross-authority inbox effects

When the inbox authority and protected effect cannot share one transaction, neither unsafe ordering is acceptable:

- **receipt first, effect later** without durable linkage can lose the effect after a crash because redelivery sees the message as processed;
- **effect first, receipt later** without durable linkage can duplicate the effect after a crash because redelivery sees no receipt.

The effect authority therefore SHALL persist a stable `operation_id` / effect-result record atomically with the effect, or use an equivalent protocol that makes effect outcome durably discoverable. The inbox record references that stable identity and completion/retry reconciles authoritative effect state before deciding whether execution is still eligible.

For an externally irreversible or otherwise ambiguous effect, the existing operation identity is reconciled against provider/domain truth. Timeout, lease expiry or missing inbox completion alone MUST NOT authorize blind re-execution.

The exact broker acknowledgement ordering is transport-specific and belongs to later async-contract/implementation design; the baseline invariant is that a crash cannot convert an already-completed effect into retry eligibility or a pre-recorded receipt into silent effect loss.

## HTTP/API idempotency

For operations exposing idempotency keys, the platform persists a durable claim record before effectful processing begins.

Conceptual fields:

```text
idempotency_claim_id
idempotency_scope        non-null canonical server-derived scope
tenant_id                when tenant-scoped
principal/credential scope metadata when relevant
operation/route contract
idempotency_key
request_fingerprint
operation_id             stable logical operation/result identity
status                    claimed | in_progress | completed | failed_terminal | reconciliation_required
result_reference / replayable response metadata
claim_version / lease metadata when recovery policy requires it
created_at
updated_at
expires_at
```

The effective scope is defined by the operation contract and includes the tenant/global boundary, operation identity and principal/credential dimension where that dimension is semantically required. Optional/null dimensions are normalized into the non-null canonical `idempotency_scope`; implementations MUST NOT rely on nullable unique-column behavior to provide exclusivity.

The durable store enforces one claim per effective scope and key, conceptually:

```text
UNIQUE(idempotency_scope, idempotency_key)
```

### Atomic claim protocol

Idempotency is an admission/serialization primitive, not a post-execution lookup.

Before any protected/effectful use-case processing that the key is intended to deduplicate, the request MUST atomically create-or-observe the durable claim using a database uniqueness/compare-and-set operation such as `INSERT ... ON CONFLICT` or an equivalent mechanism. A `SELECT` followed by an unprotected `INSERT` is not sufficient.

For concurrent requests with the same effective scope and key:

1. exactly one request can create/own the initial executable claim;
2. the owner may proceed with the logical operation;
3. another request with a different `request_fingerprint` receives an idempotency conflict and MUST NOT execute the operation;
4. another request with the same fingerprint observes the existing claim and MUST NOT execute a second logical operation;
5. if the claim is complete, the existing logical result is replayed according to the API contract;
6. if the claim is still in progress, the caller receives/joins a deterministic in-progress/retry contract rather than becoming a second executor.

The exact HTTP header/status/response representation belongs to API-contract design, but the single-winner durable claim semantics are baseline invariants.

### Local mutation completion atomicity

Acquiring the claim serializes admission; it does not by itself prove that the resulting local mutation and replay result were durably finalized.

When the idempotency claim and the authoritative local domain mutation are co-resident in the same transactional database boundary, successful completion SHALL atomically commit all state required to make the retry result unambiguous:

```text
BEGIN
  lock / CAS the existing executable claim and verify fingerprint/ownership
  perform the authoritative local domain mutation
  persist required audit and outbox records
  persist stable operation/result reference or replayable response metadata
  transition the idempotency claim to completed
COMMIT
```

The claim MUST NOT be marked `completed` before the protected local mutation is durable, and the local mutation MUST NOT commit successfully while the only durable claim remains indefinitely `in_progress` with no deterministic linkage to the committed result.

The replayable result does not require storing every transport byte. It may be a stable domain/result reference plus response metadata sufficient to reconstruct the contractually equivalent logical response. What is mandatory is durable linkage from the claim to the already-committed logical result.

Therefore:

- crash before the transaction commits leaves neither the local mutation nor a completed claim;
- crash after commit but before the HTTP response leaves both the local result and completed claim durable, so retry replays/reconstructs the established result;
- a same-key retry MUST NOT re-run a local mutation merely because the original response was lost;
- recovery of an `in_progress` claim MUST inspect authoritative operation/result state before transferring execution eligibility.

If the claim authority and local effect authority cannot share one transaction, the effect authority MUST persist an equivalent stable `operation_id` / result record atomically with the mutation. The claim recovery path then reconciles that record and finalizes/replays the claim idempotently. An unlinked cross-authority local mutation plus later best-effort claim completion is prohibited for operations whose duplication would violate the idempotency contract.

### Crash and external-effect recovery

A process crash MUST NOT make claim ownership silently transferable while the original effect may still be in flight.

For an irreversible or externally committed operation, the claim carries or deterministically derives a stable `operation_id` used for provider-side idempotency/reconciliation where the external contract permits it. If the platform cannot know whether the external effect completed, the claim moves to an explicit reconciliation/ambiguous state; recovery verifies provider/domain truth before retry eligibility is restored.

Lease/timeout-based claim recovery, if used, MUST distinguish an abandoned local executor from an external effect whose outcome is unknown. Expiration alone MUST NOT authorize blind re-execution of a payment, destructive automation or other irreversible effect.

Reusing the same key with a different request fingerprint returns conflict rather than silently executing a different operation. Idempotency retention is long enough to cover the accepted retry/replay window for the operation and applicable recovery window.

## Business process records

Long-running operations such as tenant provisioning/relocation, large exports, reconciliation and complex automation have owner-domain process records with stage/progress/error/resume state. Queue state alone is not the authoritative process history.

## Recovery-surviving reliability evidence

Point-in-time business-state recovery MUST NOT blindly roll back the evidence that prevents already-completed external effects from being repeated.

For recovery point `R` and later write fence `F`, the recovery reconciliation interval `(R, F]` inventories reliability records including:

- inbox/deduplication receipts with their trusted `message_identity_scope` and stable effect/result identities;
- API/job idempotency claims and outcomes;
- stable external operation/provider/payment identities;
- process/execution final or externally committed outcomes;
- pending/committed outbox state needed to distinguish delivered from undelivered effects;
- compensation/reconciliation records;
- immutable audit evidence.

Owning domains define which business mutations are intentionally rolled back versus which reliability/accountability records are carried forward, reconstructed from an external authority, compensated or quarantined. The target cannot start effectful retry processing until required deduplication and irreversible-operation outcomes for the interval are present and validated.

A recovery procedure SHALL NOT infer "operation did not happen" merely because the restored business database predates the local completion record; external systems and protected audit/reliability sources are reconciled before retry eligibility is established.

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

Point-in-time restoration of domain state does not authorize silent deletion of later immutable audit evidence. If the primary audit persistence is part of the restored scope, evidence in the recovery reconciliation interval must be recovered/reintroduced from its protected source or external sink before old authoritative copies may be cleaned up.

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

Inbox namespace tests feed the same raw `message_id` through the same `consumer_contract` from two different authoritative tenant/source scopes and prove both legitimate messages can execute independently. Exact redelivery within the same trusted scope MUST deduplicate. Tests also prove untrusted payload fields cannot forge a different scope to collide with or bypass another tenant/source receipt.

Inbox fault-injection tests crash before effect, after local effect statements but before commit, after atomic commit but before broker acknowledgement, and around cross-authority effect completion. Co-resident effects MUST prove receipt/effect atomicity. Cross-authority effects MUST prove stable operation/result discovery and reconciliation so redelivery neither loses nor duplicates the logical effect.

Concurrency tests issue multiple simultaneous requests with the same effective idempotency scope/key. Exactly one may acquire executable ownership. Same-fingerprint contenders must not execute a second logical effect; different-fingerprint contenders must conflict. Tests MUST prove the uniqueness constraint/atomic claim, not merely application-level pre-check behavior.

Fault injection crashes the claim owner before domain mutation, after local mutation, during external calls and after a provider may have accepted the stable `operation_id` but before the claim is marked complete. Recovery MUST replay/reconcile the existing claim and MUST NOT blindly create a second irreversible effect.

Fault injection also covers crash before mutation commit, immediately after commit, before external audit delivery and during audit-sink outage. Required mutation success is accepted only if local audit evidence or durable audit intent survives and can be reconciled.

Authorization tests prove normal application and dispatcher roles cannot update/delete committed audit evidence payloads. Delivery workers may mutate only explicitly separated delivery metadata. An external audit outage followed by dispatcher compromise/fault simulation must leave the original committed audit evidence intact and reproducible.

Recovery tests restore domain state to before a completed irreversible effect and prove post-point idempotency/deduplication/process/audit evidence is reconciled so the effect cannot be repeated merely because its original local business state was rolled back.
