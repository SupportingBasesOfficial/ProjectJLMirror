# System Design Validation Matrix

**Status:** proposed baseline

This matrix converts the design into evidence gates. Passing happy-path tests is not enough.

| Area | Required evidence before production |
|---|---|
| Tenant routing | Caller-supplied cell/schema/DB routing is ignored/rejected; authoritative placement controls routing |
| Tenant isolation | Known cross-tenant IDs leak zero protected rows through API, repository, reporting, realtime, export and workers |
| Placement cache | Stable active traffic can use bounded cache; migration/suspension invalidates or is rejected by destination admission/version |
| Relocation | Concurrent stale source writer is fenced; no source writes accepted after cutover; target becomes sole authority |
| Recovery-driven relocation pre-cutover | Revoke session/membership/permission/tenant access in `(R,F]`; target admission remains non-active until later deny/revocation generation plus reliability/audit/external-effect continuity is reconciled and validated; `VERIFYING` is only defense in depth |
| Authorization | UI omission cannot bypass server policy; cross-tenant privileged operations are distinct and audited |
| Browser/BFF | First-party browser never receives/persists long-lived platform access or refresh credentials; browser protected API flow remains behind confidential BFF session boundary |
| Browser realtime handshake | Untrusted/null Origin, ambient-cookie-only, expired/replayed/wrong-scope/wrong-tenant capability is rejected before `101 Switching Protocols`; no unauthorized protected socket is retained |
| Browser realtime authorization freshness | Mint a valid capability, then revoke/suspend session, membership, permission/scope or tenant access before presentation; handshake is rejected before `101` despite valid capability signature/expiry |
| Realtime authorization | Active protected subscription loses access after membership/permission/session/tenant revocation within accepted bound; missed invalidation is caught by bounded revalidation |
| Transactions | Mutation + required audit/audit-intent + outbox commit atomically; injected dispatcher failure loses no committed event/audit intent |
| API idempotency concurrency | Fire simultaneous requests with identical canonical scope/key/fingerprint; database uniqueness/atomic claim yields exactly one logical executor, contenders observe in-progress/completed claim and no duplicate effect occurs; same scope/key with different fingerprint conflicts before execution |
| API idempotency local completion | For a co-resident local mutation, crash after domain mutation statement but before transaction commit/claim finalization leaves no committed mutation; crash after commit but before response leaves domain result + completed claim/result linkage durable and retry replays without re-executing |
| API idempotency cross-authority result linkage | If claim and local effect are not co-resident, effect authority commits stable operation/result identity with the mutation; claim recovery discovers/finalizes that result and does not re-run the logical mutation |
| API idempotency ambiguous outcome | Crash/timeout after an external provider may have accepted the stable operation identity but before local claim completion; recovery keeps the original claim, reconciles provider truth and does not authorize blind duplicate execution from timeout/lease expiry |
| Transition signal atomicity | Crash immediately after successful conditional state advance cannot lose the required transition signal; replay discovers durable transition/outbox intent without re-advancing state |
| Audit intent integrity | During external audit-sink outage, normal app/dispatcher roles cannot update/delete immutable audit-intent evidence; only segregated delivery metadata is mutable and original evidence remains reproducible |
| Event delivery | Duplicate event causes no duplicate irreversible effect; poison message quarantines after bounded policy |
| Job delivery | Worker crash after external timeout does not duplicate accepted logical side effect beyond contract |
| Provider callback transport | Over-limit streamed/chunked callback is rejected before complete buffering/signature work; post-auth decompression/parser expansion is bounded |
| Provider callbacks | Valid-shape forged/invalid-signature callback is rejected; stale/replayed callback does not repeat protected side effects; tenant binding comes from trusted integration configuration |
| Delayed export | Authorization revoked after request but before execution/release prevents user-requested delayed artifact execution/release; capability is minted only after fresh authorization |
| SQL administration | Interactive caller-authored SQL cannot alter the tenant binding used by data policy via `SET`, `set_config`, `SET ROLE`, session authorization or equivalent; normal app/migration owner credentials are unavailable |
| Provider outage | One tenant/provider failure does not create global outage/retry storm |
| Cache outage | Behavior matches cache class; no cache loss becomes durable data loss |
| Realtime outage | Authoritative write/read continues; reconnect/resync restores client state |
| Control Plane outage | Stable admitted traffic behavior matches policy; topology-changing operations fail closed |
| Cell DB outage | Affected cell is removed/degraded; unrelated cells continue |
| Telemetry crash consistency | Crash at every durable-ingress/current-state/history/signal boundary leaves an accepted observation replayable/reconcilable; duplicate retry is idempotent; no uncoordinated dual-write success is acknowledged |
| Telemetry ordering | Deliver observation N+1 before N and replay partitions out of order; latest/current projection remains at N+1 (or newer ordering token), stale observation is retained historically but cannot regress current state or emit a false latest-state transition |
| Telemetry state/signal crash | Advance current projection, crash before normal post-update code, restart/replay; stable transition intent still causes the required signal exactly once logically under at-least-once transport |
| Telemetry outage | Buffer/backpressure remains bounded; transactional core protected from telemetry backlog |
| Secret authority outage | No plaintext fallback; only accepted lease/cache behavior continues |
| Cryptographic DR | Restored representative ciphertext/backups remain decryptable through approved KMS/key-recovery path after simulated loss of normal cryptographic authority |
| Tenant PITR continuity | Restore business state to R, create completed irreversible effects/audit/idempotency records in (R,F], fence at F, reconcile and cut over; target cannot repeat those effects and post-R immutable accountability evidence survives source cleanup |
| Tenant PITR authorization continuity | Create authority/capability before R, revoke/suspend session, membership, permission/scope or tenant access in (R,F], restore business state to R, reconcile and cut over; restored target preserves the later deny/revocation and rejects the stale authority before protected traffic resumes |
| Whole-cell PITR continuity | Across multiple tenants, create post-R revocations, idempotency receipts, audit evidence and completed/ambiguous external effects, restore the cell to R, and prove the cell remains quarantined until `(R,F]` continuity is reconciled; no stale grant or completed effect becomes eligible when admission resumes |
| Recovery scope uncertainty | If `F`/continuity cannot be completely established from the prior authority or surviving durable evidence, protected/effectful admission remains fail-closed and ambiguous work is quarantined rather than retried |
| Migration | Mixed-version rollout validated; destructive change follows expand/migrate/contract |
| Recovery | Control-plane/cell/tenant restore rehearsals applicable to their scope complete with tenant isolation intact, required protected data decryptable and safety/accountability/security-authority continuity reconciled before authority resumes |
| Observability | Request -> transaction -> outbox/job -> worker -> provider can be correlated without secret leakage |

## Release-blocking invariant tests

The following failures block release regardless of other test success:

- cross-tenant protected data disclosure or write;
- application runtime can bypass tenant RLS/data policy unexpectedly;
- interactive SQL principal can alter the tenant authority trusted by pooled data policy;
- stale placement can write after relocation fence/cutover;
- recovery-driven relocation activates target admission or routes protected/effectful traffic before required `(R,F]` security-authority, reliability, audit and external-effect continuity is reconciled;
- two concurrent requests with the same effective idempotency scope/key can both become logical executors because claim uniqueness/atomic acquisition is absent or bypassed;
- same idempotency scope/key with a different request fingerprint can execute instead of conflicting;
- a co-resident local idempotent mutation can commit while claim completion/result linkage remains non-atomic or unrecoverably `in_progress`, making retry ambiguous or re-executable;
- response loss after a committed local idempotent mutation can cause the same logical mutation to execute again instead of replaying/reconstructing the completed result;
- a cross-authority local idempotent effect can commit without stable operation/result linkage that claim recovery can reconcile before retry;
- an in-progress/ambiguous idempotency claim can be stolen or blindly retried solely because a timeout/lease expired while an irreversible external outcome remains unknown;
- required privileged audit record or durable atomic audit intent can be omitted on successful mutation;
- normal runtime/dispatcher can rewrite or delete the only committed required-audit evidence payload before external delivery;
- a committed current-state transition can lose its required signal because a crash occurred after state update but before signal intent durability;
- duplicate delivery can repeat an irreversible payment/destructive execution without contract protection;
- first-party browser JavaScript is intentionally given long-lived platform access/refresh credentials;
- protected first-party browser WebSocket with untrusted/null Origin or invalid/absent capability can receive `101 Switching Protocols` or remain as an upgraded protected connection;
- capability minted while authorized can still obtain protected `101` after the underlying session/membership/permission/tenant authority has been revoked or suspended before presentation;
- known-revoked realtime subscription continues receiving protected events beyond the accepted revocation/revalidation bound;
- oversized unauthenticated callback reaches complete-body/signature processing without transport enforcement;
- forged/invalid-authentication provider callback can mutate protected domain state;
- replayed provider callback can repeat an irreversible logical side effect;
- delayed user-requested export can execute/release after required authorization has been revoked;
- telemetry ingestion acknowledges an observation while neither a durable replayable acceptance record nor an equivalent recoverable authority exists for downstream projections;
- out-of-order/replayed telemetry can replace a newer current/latest state or produce a stale latest-state transition;
- tenant point-in-time recovery makes an already-completed post-recovery-point irreversible effect eligible to execute again because dedup/idempotency/process outcome evidence was rolled back;
- tenant point-in-time recovery/source cleanup erases required immutable audit evidence from the recovery-to-fence interval;
- tenant point-in-time recovery reactivates a session, membership, permission/scope, credential or tenant access that was revoked/suspended in `(R,F]`, or rolls back the freshness/generation state used to reject stale authority;
- whole-cell PITR resumes protected traffic, schedulers or effectful workers before all applicable tenant continuity state is reconciled;
- whole-cell PITR reactivates a later-revoked membership/permission/tenant access or makes an already-completed post-R external effect retry-eligible;
- protected/effectful traffic resumes after recovery while required post-`R` authorization revocation/deny state or irreversible-effect outcome remains materially unknown;
- secrets appear in logs/traces/events/queue payload/audit/client error;
- migration makes active supported runtime versions access incompatible schema;
- restore cannot re-establish verified tenant isolation;
- restored required ciphertext is unusable because its approved cryptographic recovery authority/key version is unavailable.

## Evidence traceability

Automated tests SHOULD reference `INV-*`, `QA-*`, `SEC-*` and `TM-*` identifiers. Architecture-specific tests additionally reference the ADR/design section they validate.
