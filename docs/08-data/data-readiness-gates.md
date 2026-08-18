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
- deletion/anonymization/legal-retention behavior considered;
- artifact/telemetry separation used where appropriate.

## Gate D7 — Async/reliability

If mutation emits work/events/signals, consumes at-least-once messages, or exposes idempotency semantics:

- outbox or accepted equivalent atomicity exists;
- conditional state transitions that require signals persist the transition/signal obligation atomically or through an equivalent durable advancement record;
- event/job versioning defined;
- consumer duplicate semantics defined;
- inbox/dedup identity is durable where duplicate effect would be unsafe;
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
- replay after crash does not depend on an in-memory "transition happened", "claim owner probably died" or "receipt exists so effect must have happened" assumption.

## Gate D8 — Migration

- migration is versioned;
- backward/forward compatibility window defined;
- large backfill is resumable/observable and not a blocking schema transaction;
- rollback/forward-recovery considered;
- RLS/privileges/indexes included in migration acceptance.

## Gate D9 — Recovery

For any PITR scope that can roll back protected authority/reliability state:

- backup/reconstruction source identified;
- tenant/cell/control-plane recovery impact understood for the restored authority;
- encryption/key dependency documented;
- recovery validation exists for critical data;
- recovery defines point `R` and a later authoritative reconciliation boundary `F` appropriate to the scope;
- if the old authority is unavailable, `F` and continuity are reconstructed from surviving durable authorities/watermarks and uncertainty is explicitly classified rather than assumed absent;
- the `(R,F]` interval is classified into rollback-subject state versus safety/accountability/security-authority continuity state;
- deduplication/idempotency/process/external-operation outcomes needed to suppress duplicate irreversible effects survive or are reconciled before protected/effectful authority resumes;
- immutable audit evidence required from `(R,F]` survives restore and source cleanup;
- session/credential revocations, membership disablement/revocation, permission/scope removal, tenant suspension/access denial and authorization/session generation or equivalent freshness state from `(R,F]` survive or are reconciled before protected traffic resumes;
- a restored positive grant at `R` cannot silently override a later deny/revocation from `(R,F]`;
- whole-cell recovery remains quarantined/non-authoritative until continuity for all affected tenants required for protected/effectful admission is reconciled;
- unresolved external-effect outcomes are quarantined/reconciled rather than retried blindly;
- intentionally reversing a preserved security revocation is modeled as a separate authorized/audited security-recovery action rather than an implicit PITR effect.

## Gate D10 — Observability/security

- slow/error path observable with tenant-safe correlation;
- secret/PII logging policy defined;
- audit class defined for privileged mutation;
- no raw provider payload becomes trusted domain state without validation.

## Gate D11 — Capacity

For high-volume tables/streams:

- expected cardinality/ingest/retention dimensions are modeled;
- partition/specialization threshold has a benchmark plan;
- backlog/storage growth cannot become unbounded silently.

## Gate D12 — Relocation compatibility

Tenant-scoped state can be selected, copied, validated and fenced by immutable `tenant_id`. Physical location/schema/server identifiers are not embedded as business identity.

For recovery-driven relocation, the target can receive/reconcile required safety/accountability/security-authority continuity state without reapplying all business mutations that the recovery intentionally rolls back. Target admission remains inactive until that continuity is validated; post-cutover verification is defense in depth, not the first security gate.
