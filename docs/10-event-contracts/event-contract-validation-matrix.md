# Event Contract Validation Matrix

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This matrix defines permanent implementation/release evidence for Phase 10. A contract is not accepted merely because producer and consumer code compile or because a broker test passes.

The matrix must be satisfied by contract/profile where applicable. `N/A` requires an explicit reason.

## Core validation matrix

| Area | Required contract evidence | Minimum implementation/release evidence | Release-blocking failure |
|---|---|---|---|
| Contract identity | stable `contract_name`, version, message class, owner | manifest/schema/catalog agree | queue/topic/provider name is the only contract identity |
| Producer authority | allowed logical producer and scope | producer credential/ACL tests | unauthorized capability can publish protected contract |
| Tenant/global scope | explicit tenant/global policy | tenant isolation tests | payload can forge/override tenant or missing tenant treated as global |
| Message identity | stable message ID and trusted identity scope | redelivery/collision tests | same logical message gets new ID on ordinary retry or cross-source IDs collide |
| Message content equivalence | canonical immutable-content fingerprint/original/equivalent comparison authority retained for supported dedup/recovery horizon | same-ID equivalent/mismatch/minimization/PITR tests | same scoped ID with changed immutable meaning can be silently suppressed as a normal duplicate or comparison evidence expires while the ID remains replayable/redeliverable |
| Message-equivalence evidence security | comparison evidence uses the accepted canonical semantic profile, inherits source-data confidentiality risk, is scoped only after trusted consumer/message identity, and preserves historical verifier/profile authority or fails closed | low-entropy digest, cross-scope oracle, profile migration, key rotation/retirement, verifier-loss, restore and bounded-KMS/equality tests | evidence leaks confidential values/correlation, becomes an authority, historical equality cannot be proven yet duplicate/effect admission continues, or verifier/profile loss/rollback silently changes equivalence semantics |
| Envelope integrity | canonical bounded message profile | parser/duplicate/size tests | different parsers derive different protected envelope meaning |
| Payload schema | required/optional fields, bounds, enum policy | machine schema + fixtures | malformed/oversized payload reaches protected effect |
| Data classification | classification and secret policy | lint/redaction/log tests | credentials/secrets in ordinary payload/log/quarantine |
| Outbox publication | authoritative trigger and transaction boundary | commit/crash fault injection | mutation commits without required outbox or message publishes before fact commit |
| Immutable fact evidence | immutable semantic payload vs mutable attempt state | mutation/dispatcher role tests | retry worker can rewrite committed fact meaning |
| Publish ambiguity | stable identity across uncertain broker ack | publish-ack-loss test | timeout creates second semantic event ID |
| Delivery semantics | at-least-once or proven stronger contract | duplicate delivery tests | consumer assumes single delivery without proof |
| Ack boundary | durable responsibility before ack/checkpoint | crash-after-effect-before-ack test | ack can occur before durable effect/reconciliation responsibility |
| Retry classification | transient/throttled/permanent/ambiguous/etc. | error mapping tests | ambiguous external outcome becomes blind retry |
| Retry bounds | backoff/jitter/budgets/terminal path | load/failure tests | infinite/unbounded retry or one workload exhausts global capacity |
| Quarantine | durable governed terminal state | poison/redrive tests | malformed/poison message silently dropped or retried forever |
| Consumer identity | stable `consumer_contract` | manifest/catalog consistency | broker group name is sole consumer semantic identity |
| Inbox scope | trusted non-null identity scope | same-ID cross-source/tenant tests | one tenant/source suppresses another or payload chooses scope |
| Inbox/effect atomicity | local completion or cross-authority profile | crash injection | completed receipt can exist without effect or effect without discoverable result |
| Cross-authority effect | stable operation/result identity | external timeout/reconcile tests | redelivery can repeat uncertain irreversible effect |
| Current placement | worker re-resolves current tenant placement | relocation tests | stale cell route can mutate retired placement |
| Current authorization | delayed protected work re-evaluates required authority | revocation/session/permission tests | message creation-time authority persists indefinitely |
| Service principal scope | explicit machine authority class | least-privilege tests | generic worker has unrestricted cross-tenant/domain privilege |
| Ordering profile | unordered/causal/per-scope/custom | reorder/concurrency tests | consumer relies on undocumented global/order guarantee |
| Ordering key | trusted logical scope | partition/key tests | payload or physical partition defines authority incorrectly |
| Sequence semantics | source/scope/gap/stale behavior | stale/gap/reset tests | sequence is confused with dedup or source reset collides |
| Producer generation | required/optional generation policy | relocation/failover tests | retired current-source generation regains authority |
| Replay policy | purpose/range/identity/target | replay tests | replay disables dedup or repeats irreversible production effects |
| Projection rebuild | isolated generation/target | rebuild tests | rebuild erases production dedup or mutates production effects |
| Historical schema | old version reader/upcaster policy | retained fixture replay | supported old messages cannot be interpreted |
| Recovery continuity | `(R,F]` evidence and fail-closed rules | PITR/partial-loss tests | missing restored state treated as never published/processed/executed |
| Offset/checkpoint | transport progress vs business completion | rewind/forward tests | offset is sole proof of effect completion |
| Retention | publication/dedup/replay/schema horizons | retention policy checks | replay exceeds correctness/schema evidence horizon |
| Realtime Phase 09 authority | admission/subscription authority inherited | revocation/relocation tests | message protocol restores/extends revoked authority |
| Realtime protocol | protocol vs event contract versions separated | old/new protocol/contract tests | event version change forces accidental protocol semantics or vice versa |
| Realtime resync | snapshot/resync behavior | gap/loss/reconnect tests | client requires complete socket history for correctness |
| Realtime backpressure | bounded buffering/coalesce/drop/resync profile | slow-client tests | unbounded confidential message buffering |
| Outbound webhook Product gate | explicit approved external contract | catalog/authorization tests | internal event automatically becomes externally subscribable |
| Webhook delivery identity namespace | global uniqueness or explicit stable external scope | multi-tenant/multi-subscription collision tests | receiver can suppress a legitimate delivery because another subscription/tenant reused the same documented delivery identity |
| Webhook immutable delivery semantics | same delivery ID binds contract/version/source/scope/semantic payload | rolling-deploy/retry/current-state mutation tests | same delivery ID can authenticate a different contract version or semantic payload on retry |
| Webhook destination generation | delivery obligation binds exact authorized subscription/destination generation | config-change/revocation/in-flight ambiguity tests | same delivery ID can silently target a different destination generation or old revoked destination remains blindly retryable |
| Webhook configuration-change policy | cancel/fence, quarantine or deliberate reissue under new identity | reissue/causation tests | generation change silently retargets old obligation or reissue reuses old delivery ID |
| Webhook identity | event vs delivery identity | timeout/redelivery tests | timeout invents new event/delivery semantics |
| Webhook destination security | SSRF/redirect/timeout/size policy | egress security tests | subscriber URL reaches prohibited internal/control targets |
| Webhook authenticity | signing profile and bound freshness | verification vectors | unbound timestamp or ambiguous signed representation |
| Webhook tenant disclosure | trusted subscription/event scope | cross-tenant tests | subscriber receives another tenant's event |
| Compatibility manifest | semantic fields complete | manifest diff CI | schema-identical security/correctness change escapes review |
| Rolling deployment | producer/consumer skew policy | old/new compatibility fixtures | compatible release requires atomic deploy without migration plan |
| Deprecation | support/retirement criteria | usage/catalog/replay checks | old contract removed while supported producer/consumer/history still depends on it |
| Observability | IDs/classes/backlog/retry/reconcile signals | metrics/log tests | incidents cannot distinguish queued/published/processed/reconciled states |
| Audit | privileged replay/redrive/config actions | audit fault tests | sensitive admin action can occur without required audit evidence |
| Topology independence | logical IDs only | broker/service/cell replacement review | consumer contract exposes physical broker/cell/provider identity |

## Mandatory fault-injection suite

The following classes are permanent Phase 10 evidence where the affected feature exists.

### Publisher fault vectors

- crash before authoritative transaction commit;
- crash after commit before dispatcher claim;
- broker accepts publish, publisher loses acknowledgement;
- concurrent dispatchers claim same backlog;
- broker outage while authoritative mutations continue;
- restore to before publication while broker/consumer evidence survives;
- stale producer/source generation publishes after retirement;
- producer bug/recovery defect attempts to reuse an existing trusted scoped `message_id` with changed immutable contract content.

Expected invariant: one committed logical fact keeps one stable message identity; publication may duplicate but cannot disappear silently, become a new semantic fact under the old ID or have conflicting reuse accepted as ordinary redelivery.

### Consumer fault vectors

- simultaneous duplicate delivery;
- same raw message ID under different trusted source/tenant scope;
- same trusted scoped message ID with identical immutable semantic content is recognized as a normal duplicate;
- same trusted scoped message ID with changed contract version, trusted immutable scope/subject semantics or canonical payload fails closed as integrity/producer-contract failure;
- original payload is minimized/erased but retained fingerprint/equivalence evidence still detects conflicting reuse;
- comparison fingerprint/evidence is lost or rolled back while the same scoped ID can still redeliver/replay, and the consumer fails closed rather than declaring a safe duplicate;
- low-entropy confidential immutable content does not become recoverable through ordinary plain-digest logs, diagnostics, quarantine views or externally visible identifiers;
- identical semantic content under different trusted tenant/consumer/message-identity scopes cannot be correlated or deduplicated through an unrestricted fingerprint/equality lookup;
- canonicalization/comparison-profile upgrade preserves historical equality semantics or the affected identities remain fail-closed until an equivalence-preserving migration completes;
- keyed/authenticated comparison evidence remains verifiable across accepted key/profile rotation, or old duplicate-sensitive identities remain fail-closed when historical verifier authority is unavailable/retired;
- restore to before key/profile rotation does not resurrect obsolete verifier authority for unrelated messages;
- historical verifier/profile loss or outage never changes unknown equivalence into normal duplicate success or protected-effect eligibility;
- repeated crafted duplicate IDs cannot force unbounded KMS/secret-store/comparison work or expose an equality oracle;
- crash after receipt admission before effect;
- crash during local effect before transaction commit;
- crash after atomic local commit before broker acknowledgement;
- cross-authority/external effect succeeds before receipt completion;
- provider timeout after effect may have committed;
- worker lease expires while original executor may still be active.

Expected invariant: no lost completed effect, no duplicate protected logical effect, no silent suppression of conflicting immutable content, and no confidentiality/authority regression caused by the evidence used to prove equivalence.

### Delayed-authority vectors

- session/logout revoked after message creation;
- membership disabled/revoked;
- permission/scope removed;
- tenant suspended;
- plan/policy changes;
- tenant relocates before worker execution.

Expected invariant: delayed message does not preserve stale authority or placement.

### Retry/quarantine vectors

- transient dependency failure recovers after bounded retry;
- throttling hint honored within bounds;
- poison message reaches quarantine;
- malformed unsupported version does not retry forever;
- redrive requires current authorized remediation and preserves dedup/reconciliation;
- one failing tenant/provider cannot starve unrelated critical work.

### Ordering/replay vectors

- messages reordered within unordered contract;
- two independent subjects process concurrently;
- duplicate message does not advance state twice;
- stale/lower sequence cannot regress projection;
- sequence gap invokes documented behavior;
- source sequence resets under new generation;
- delayed old-generation historical fact remains valid where contracted;
- stale current-source command is rejected;
- replay preserves original message identity;
- replay of same ID with content differing from retained immutable-equivalence evidence is rejected/quarantined;
- replay requiring a retired/unavailable historical comparison verifier remains blocked/reconciliation-required rather than trusting identity alone;
- projection rebuild uses isolated generation;
- replay cannot invoke irreversible production side effect twice.

### Recovery vectors

- inbox state restored before surviving business/provider effect;
- message-content fingerprint/equivalence evidence restored older than surviving/redelivered message content;
- comparison evidence bytes survive but the historical canonicalization/profile/verifier authority needed to interpret them is missing or older;
- restore predates comparison key/profile rotation while post-restore evidence references the newer historical verifier generation;
- outbox state restored before surviving broker publication;
- broker offset rewound after completed effects;
- old producer generation restored as apparently current;
- process state restored before external success;
- quarantine/reconciliation state partially lost;
- old schema/version required after restore/replay;
- revoked authorization/security generation predates restore point.

Expected invariant: recovery uncertainty blocks unsafe effectful admission and unsafe duplicate classification until `(R,F]` reconciliation proves eligibility, message-content equivalence and the authority needed to interpret historical comparison evidence.

### Realtime vectors

- malformed/duplicate JSON fields;
- unsupported protocol version;
- subscribe to unauthorized tenant/resource;
- logout/session revocation after active subscription;
- membership/permission removal after active subscription;
- placement generation retirement while socket remains open;
- resume token after authorization change;
- replay retention gap -> resync;
- gateway/fanout state loss -> resync/fail closed according to channel profile;
- slow client -> bounded drop/coalesce/resync/close;
- reconnect requires fresh Phase 09 admission.

### Outbound webhook vectors

- SSRF/private-network destination;
- redirect escape;
- signature timestamp/body tamper;
- one external endpoint receives multiple tenants/subscriptions whose local generators would otherwise collide;
- subscriber receives request but response is lost;
- repeated retry preserves delivery/source identity;
- retry after projection mapper/dispatcher rolling upgrade preserves same webhook contract version and semantic payload for the same delivery ID;
- mutable current domain state changes after delivery obligation creation and retry still preserves original semantic payload;
- destination URL/configuration generation changes while a delivery is pending and the old delivery is never silently retargeted;
- destination is revoked while an in-flight attempt has ambiguous outcome and no further old-generation retry is admitted automatically;
- deliberate reissue to a new destination generation receives a new delivery ID with causation to the original;
- cross-tenant subscription/filter attack;
- signing secret rotation/revocation;
- permanent 4xx/profile failure -> terminal/quarantine;
- one slow endpoint cannot exhaust all delivery workers;
- restore before local success/config-generation evidence while subscriber may already have received request;
- restore cannot resurrect a retired destination generation or reconstruct an existing delivery ID with changed semantic payload.

Expected invariant: one webhook delivery identity maps to one immutable semantic disclosure obligation and one authorized destination generation; retries may repeat transport attempts but cannot mutate meaning or retarget silently.

## Compatibility acceptance tests

CI/review shall eventually compare more than schemas.

At minimum, detect changes to:

```text
contract/version/message_class
producer authority
tenant scope
message identity/scope
message-content equivalence/fingerprint policy
message-equivalence evidence confidentiality/oracle policy
message-equivalence comparison-profile/verifier lifecycle policy
producer generation
payload field semantics/data classification
outbox publication boundary
delivery/ack semantics
retry/quarantine policy
consumer effect completion
ordering/sequence/gap behavior
replay identity/target
retention/recovery continuity
current authorization/placement requirements
realtime protocol/projection behavior
webhook disclosure/signing/destination semantics
webhook delivery identity namespace
webhook immutable delivery semantic snapshot/reproduction policy
webhook destination configuration generation binding
webhook cancel/quarantine/reissue policy
webhook attempt-scoped authentication metadata policy
```

A security/correctness change cannot hide behind an unchanged payload schema.

## Parser and schema tests

All structured message profiles test:

- duplicate protected members;
- aliases after accepted normalization;
- malformed encoding;
- oversized/deep structures;
- unknown fields according to extensibility profile;
- open/closed enum behavior;
- unsupported versions;
- compression/decompression bounds where used;
- active XML/external resolution disabled where any XML profile exists;
- dangerous polymorphic deserialization/code-loading disabled.

Message-equivalence comparison additionally uses the accepted canonical structured interpretation/profile; an implementation cannot hash one parser representation while protected contract validation uses another semantic interpretation.

## Release blockers

Phase 10 implementation/release is blocked if any applicable condition exists:

- authoritative mutation can commit without required outbox evidence;
- uncommitted message can publish as committed fact;
- same logical publication retry invents a new message identity;
- producer/payload can forge another tenant/contract namespace;
- same trusted scoped `message_id` with changed immutable content can be acknowledged/suppressed as a normal duplicate;
- message-content equivalence fingerprint/original/equivalent evidence can expire, be erased or be lost in recovery while the same scoped ID remains legitimately redeliverable/replayable and duplicate classification still proceeds;
- message-equivalence evidence can expose low-entropy confidential content, provide unrestricted cross-tenant/cross-consumer equality/correlation, or be logged/exported as harmless metadata contrary to classification;
- equivalence comparison can proceed under a different/unversioned canonicalization profile from protected contract validation;
- historical comparison profile/verifier authority can be lost, retired or rolled back while affected identities continue duplicate/effect admission without fail-closed reconciliation;
- a comparison fingerprint/MAC/profile reference can be used as authorization, routing, ordering authority, external identity or bearer capability;
- crafted duplicate/equality requests can create unbounded KMS/secret-store/comparison work or an unrestricted oracle;
- consumer acks before durable responsibility;
- inbox/dedup is read-then-write or crash-inconsistent for protected effects;
- ambiguous external effect becomes blind retry;
- delayed message preserves stale human/tenant/placement authority;
- ordering assumption is stronger than the contract;
- replay can repeat irreversible effects or bypass production dedup truth;
- restored missing state is treated as absence/no prior effect;
- supported replay outlives schema/dedup/equivalence evidence needed for safety;
- realtime protocol can keep revoked/retired subscription delivering protected data;
- realtime correctness requires never missing a message;
- external webhook can SSRF prohibited targets, leak cross-tenant data or sign ambiguous/unbound content;
- webhook delivery ID namespace can collide across the receiver's supported tenant/subscription space;
- the same webhook delivery ID can change contract version, tenant/subscription scope or semantic payload across retry/recovery/rolling deployment;
- an existing webhook delivery can silently retarget a changed destination configuration generation;
- a revoked/retired webhook destination generation can continue blind retries or be resurrected by restore;
- a deliberate webhook reissue under new destination authority reuses the old delivery ID instead of creating a causally linked new obligation;
- secrets/credentials enter ordinary payload/log/quarantine;
- schema-identical semantic changes escape compatibility review;
- service/broker/provider/cell physical identity leaks into canonical async contract.

## Acceptance gate

Before Phase 10 is accepted as a baseline:

- every proposed normative document is mutually consistent;
- no Phase 10 rule contradicts accepted Phases 07–09;
- OPEN items separate mechanism from fixed property;
- no Product event/webhook capability is invented merely by architecture;
- broker/provider/topology replacements do not require semantic rewrite;
- recovery/replay paths remain safe at maximum intended scale;
- a fresh independent review reports no material P0/P1/P2 foundation issue.
