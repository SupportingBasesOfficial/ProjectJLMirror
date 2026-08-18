# Data Architecture Readiness Gates

**Status:** proposed baseline

A data model/table/storage change is not production-ready until applicable gates pass.

## Gate D1 — Ownership

- owning bounded context is named;
- one logical writer is defined;
- cross-domain reads/references are deliberate;
- no generic `shared` ownership ambiguity.

## Gate D2 — Tenant classification

Every persisted object is classified as:

- global/control-plane;
- tenant-scoped pooled;
- dedicated-cell but logically tenant-scoped;
- public projection;
- operational/system metadata.

A pooled tenant table cannot ship without non-null `tenant_id`, database isolation policy and isolation tests.

## Gate D3 — Relational integrity

- PK/identity stable across relocation;
- unique constraints use correct global/tenant scope;
- parent/child tenant-safe FK pattern used where applicable;
- impossible state protected by CHECK/NOT NULL/FK/unique constraints where database enforcement is appropriate;
- money/time/value types are semantically correct.

## Gate D4 — Access policy

- normal runtime role is least privilege;
- RLS/data policy tested under actual application role;
- migration owner is distinct from normal runtime;
- direct SQL/admin path cannot silently inherit stronger owner/superuser rights;
- read/write policy is explicit.

## Gate D5 — Query/index design

- primary read/write query patterns documented;
- indexes support required tenant/query dimensions;
- no unbounded scan in interactive path without explicit acceptance;
- current-state queries do not scale with full telemetry history;
- pagination strategy has deterministic indexed sort where needed.

## Gate D6 — Lifecycle

- create/update/delete/archive semantics defined;
- retention class defined;
- deletion/erasure/anonymization/pseudonymization/legal-retention behavior defined rather than merely noted;
- governed erasure/anonymization decisions retain durable tombstone/decision metadata sufficient to prevent accidental resurrection from backup without retaining the erased content itself unless policy requires otherwise;
- legal-retention/legal-hold placement/release state has an authoritative lifecycle and recovery behavior;
- destructive cleanup uses a monotonic governance/retention generation or equivalent fencing state; legal-hold placement/release and delete/crypto-erasure share a logical serialization authority, and a stale read-then-delete sequence is prohibited;
- immediately before an irreversible destructive boundary, cleanup proves its expected governance generation is still current, no effective legal hold prohibits deletion and its destructive authorization/fencing token is current; a governance mutation that wins serialization invalidates stale delete authority;
- if the selected storage/control mechanism cannot serialize governance changes with destructive cleanup strongly enough to reject stale deletion authority, destructive cleanup remains blocked/reconciliation-required rather than assuming permission;
- cryptographic-erasure/key-destruction intent is coordinated with backup/recovery semantics so PITR cannot silently revive a key path that current policy intentionally destroyed;
- artifact/telemetry separation used where appropriate;
- protected artifacts that span transactional metadata and object storage use a stable `artifact_id`/tenant identity plus an explicit staged lifecycle; bytes are not releasable until verified terminal-ready metadata exists;
- artifact upload attempts are bound to a non-null current lifecycle/upload generation or equivalent fencing token, and finalization proves that generation is still current;
- deletion/erasure advances or terminally fences the artifact publication generation **before** object cleanup so an already-started stale upload cannot later republish/finalize bytes as current;
- cancellation or worker lease expiry alone is not the artifact publication fence; stale attempts remain generation-identifiable and non-publishable even if transport I/O completes;
- artifact delivery/download capability authority is bound to a current delivery/lifecycle generation or equivalent revocable authority; governed deletion/erasure stops new capability minting and fences older capabilities before the artifact is treated as fully non-releasable/erased;
- capability redemption acquires a generation-bound active-delivery lease/stream record or equivalent stream-level fence before protected bytes are released; already-started older-generation deliveries are aborted/fenced or deterministically drained when erasure retires their delivery generation;
- capability revocation that only blocks future presentations is insufficient if an already-authorized stream can continue releasing protected bytes; active-stream terminal state must be observable before full non-releasability/confirmed erasure is claimed;
- a direct download capability that remains usable solely until expiry is not accepted where governance requires prompt erasure revocation; use application-mediated current-state/generation checks or an equivalent revocable storage/access generation;
- confirmed artifact deletion/erasure is recorded only after all prior-generation upload attempts are unable to publish/finalize, all prior-generation delivery capabilities are unable to start/restart release, all prior-generation active streams are unable to release further protected bytes, every destructive step observed current governance/hold authority at its irreversible boundary, and the relevant object/version inventory is reconciled under current governance; uncertainty leaves `ERASURE_FENCING`/`DELETING`/`RECONCILIATION_REQUIRED`, not optimistic confirmation;
- artifact creation/deletion has crash reconciliation for metadata-without-object, object-without-ready-metadata, stale-generation object attempts, stale delivery capabilities/active streams, missing/corrupt object, interrupted deletion/erasure, upload-vs-delete races and legal-hold-vs-delete races;
- controlled staging/orphan object inventory is discoverable and subject to bounded governed reconciliation/GC; legal hold/retention/erasure policy is consulted and serialized before destructive cleanup.

## Gate D7 — Async/reliability

If mutation emits work/events/signals, consumes at-least-once messages, or exposes idempotency semantics:

- outbox or accepted equivalent atomicity exists;
- conditional state transitions that require signals persist the transition/signal obligation atomically or through an equivalent durable advancement record;
- event/job versioning defined;
- consumer duplicate semantics defined;
- inbox/dedup identity is durable where duplicate effect would be unsafe;
- inbox uniqueness includes a non-null canonical `message_identity_scope` derived from trusted tenant/source/producer context unless the consumer contract explicitly proves `message_id` is globally unique across every producer for the full deduplication window;
- the same raw `message_id` from different authoritative scopes cannot suppress another tenant/source message, while exact redelivery in the same scope deduplicates;
- accepted telemetry observation deduplication uses a non-null canonical trusted `observation_identity_scope` plus stable observation identity unless the producer contract explicitly proves global uniqueness across all producers for the full deduplication window;
- the same raw provider-local telemetry observation/event ID from different tenant/integration/source/generation scopes cannot suppress another legitimate observation, while exact replay in the same trusted scope deduplicates;
- co-resident inbox receipt completion and protected consumer effect share one transaction/atomic boundary;
- receipt-first without durable effect completion is prohibited because it can suppress an effect that never committed;
- effect-first without durable receipt/result linkage is prohibited because redelivery can duplicate the effect;
- cross-authority inbox effects persist a stable operation/result identity atomically with the effect and reconcile that authority before retry eligibility;
- ambiguous external consumer effect is reconciled/quarantined; timeout, lease expiry or missing receipt completion alone does not authorize blind re-execution;
- idempotency record is durable when losing it could duplicate irreversible effects;
- API/application idempotency uses a non-null canonical effective scope plus database-enforced unique claim identity;
- claim acquisition is atomic create-or-observe/compare-and-set before effectful processing; read-then-create without uniqueness/serialization is prohibited;
- same-scope/key/fingerprint concurrency has one logical executor and deterministic in-progress/completed replay semantics;
- same-scope/key with a different fingerprint conflicts before effectful execution;
- co-resident local idempotent mutation, required audit/outbox, stable result linkage and claim completion share one transaction or equivalent atomic boundary;
- crash after a local mutation statement but before commit cannot leave a committed effect detached from a completed/replayable claim;
- crash after commit but before response delivery leaves a replayable completed claim/result and does not require re-executing the mutation;
- if claim and local effect use different authorities, the effect authority atomically persists a stable operation/result record and claim recovery reconciles that record before retry eligibility;
- ambiguous external outcome retains the existing claim/stable operation identity and reconciles before retry eligibility; timeout/lease expiry alone does not authorize blind re-execution;
- delayed user-authored imports re-establish current tenant context and current authorization before protected mutation; queued request-time authority is not durable execution authority;
- replay after crash does not depend on an in-memory "transition happened", "claim owner probably died" or "receipt exists so effect must have happened" assumption.

## Gate D8 — Migration

- migration is versioned;
- backward/forward compatibility window defined;
- large backfill is resumable/observable and not a blocking schema transaction;
- rollback/forward-recovery considered;
- RLS/privileges/indexes included in migration acceptance.

## Gate D9 — Recovery

For any PITR scope that can roll back protected authority/reliability/governance state:

- backup/reconstruction source identified;
- tenant/cell/control-plane recovery impact understood for the restored authority;
- encryption/key dependency documented;
- recovery validation exists for critical data;
- recovery defines point `R` and a later authoritative reconciliation boundary `F` appropriate to the scope;
- if the old authority is unavailable, `F` and continuity are reconstructed from surviving durable authorities/watermarks and uncertainty is explicitly classified rather than assumed absent;
- the `(R,F]` interval is classified into rollback-subject state versus safety/accountability/security-authority/governance continuity state;
- deduplication/idempotency/process/external-operation outcomes needed to suppress duplicate irreversible effects survive or are reconciled before protected/effectful authority resumes;
- immutable audit evidence required from `(R,F]` survives restore and source cleanup;
- session/credential revocations, membership disablement/revocation, permission/scope removal, tenant suspension/access denial and authorization/session generation or equivalent freshness state from `(R,F]` survive or are reconciled before protected traffic resumes;
- a restored positive grant at `R` cannot silently override a later deny/revocation from `(R,F]`;
- governed deletion/erasure, anonymization/pseudonymization and approved cryptographic-erasure decisions from `(R,F]` survive or are reconciled before restored protected data becomes authoritative or visible;
- durable tombstone/decision evidence prevents backup contents from silently resurrecting data removed or de-identified after `R`;
- current legal-retention/legal-hold placement/release state is reconciled before destructive lifecycle actions resume;
- unresolved erasure/anonymization status keeps affected protected data unavailable, while unresolved legal-retention status blocks destructive deletion;
- artifact metadata/object state is reconciled across PITR so restored metadata cannot falsely expose absent/wrong bytes, restored lifecycle/delivery/governance generation cannot reopen a stale publisher/download/stream or stale destructive authorization, and surviving object bytes cannot remain indefinitely untracked or bypass current governance;
- whole-cell recovery remains quarantined/non-authoritative until continuity for all affected tenants required for protected/effectful admission is reconciled;
- unresolved external-effect outcomes are quarantined/reconciled rather than retried blindly;
- intentionally reversing a preserved security revocation or governance decision is modeled as a separate authorized/audited recovery action rather than an implicit PITR effect.

## Gate D10 — Observability/security

- slow/error path observable with tenant-safe correlation;
- secret/PII logging policy defined;
- audit class defined for privileged mutation;
- no raw provider payload becomes trusted domain state without validation;
- replay-consumption authority for protected capabilities treats state loss/restart as a security event requiring state continuity/reconciliation or epoch invalidation; missing replay state never authorizes redemption.

## Gate D11 — Capacity

For high-volume tables/streams:

- expected cardinality/ingest/retention dimensions are modeled;
- partition/specialization threshold has a benchmark plan;
- backlog/storage growth cannot become unbounded silently.

## Gate D12 — Relocation compatibility

Tenant-scoped state can be selected, copied, validated and fenced by immutable `tenant_id`. Physical location/schema/server identifiers are not embedded as business identity.

For recovery-driven relocation, the target can receive/reconcile required safety/accountability/security-authority/governance continuity state without reapplying all business mutations that the recovery intentionally rolls back. Target admission remains inactive until that continuity is validated; post-cutover verification is defense in depth, not the first security/governance gate.

Long-lived protected realtime subscriptions are placement/admission-generation-bound. A relocation cannot complete while the old source generation can indefinitely retain the relocated tenant's subscription as current: affected source subscriptions are invalidated/removed or their connection is terminated within the accepted bound, and fresh target subscription/resync resolves the new placement generation.
