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
- stale producer/source generation publishes after retirement.

Expected invariant: one committed logical fact keeps one stable message identity; publication may duplicate but cannot disappear silently or become a new semantic fact.

### Consumer fault vectors

- simultaneous duplicate delivery;
- same raw message ID under different trusted source/tenant scope;
- crash after receipt admission before effect;
- crash during local effect before transaction commit;
- crash after atomic local commit before broker acknowledgement;
- cross-authority/external effect succeeds before receipt completion;
- provider timeout after effect may have committed;
- worker lease expires while original executor may still be active.

Expected invariant: no lost completed effect and no duplicate protected logical effect.

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
- projection rebuild uses isolated generation;
- replay cannot invoke irreversible production side effect twice.

### Recovery vectors

- inbox state restored before surviving business/provider effect;
- outbox state restored before surviving broker publication;
- broker offset rewound after completed effects;
- old producer generation restored as apparently current;
- process state restored before external success;
- quarantine/reconciliation state partially lost;
- old schema/version required after restore/replay;
- revoked authorization/security generation predates restore point.

Expected invariant: recovery uncertainty blocks unsafe effectful admission until `(R,F]` reconciliation proves eligibility.

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
- subscriber receives request but response is lost;
- repeated retry preserves delivery/source identity;
- cross-tenant subscription/filter attack;
- signing secret rotation/revocation;
- permanent 4xx/profile failure -> terminal/quarantine;
- one slow endpoint cannot exhaust all delivery workers;
- restore before local success evidence while subscriber may already have received request.

## Compatibility acceptance tests

CI/review shall eventually compare more than schemas.

At minimum, detect changes to:

```text
contract/version/message_class
producer authority
tenant scope
message identity/scope
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

## Release blockers

Phase 10 implementation/release is blocked if any applicable condition exists:

- authoritative mutation can commit without required outbox evidence;
- uncommitted message can publish as committed fact;
- same logical publication retry invents a new message identity;
- producer/payload can forge another tenant/contract namespace;
- consumer acks before durable responsibility;
- inbox/dedup is read-then-write or crash-inconsistent for protected effects;
- ambiguous external effect becomes blind retry;
- delayed message preserves stale human/tenant/placement authority;
- ordering assumption is stronger than the contract;
- replay can repeat irreversible effects or bypass production dedup truth;
- restored missing state is treated as absence/no prior effect;
- supported replay outlives schema/dedup evidence needed for safety;
- realtime protocol can keep revoked/retired subscription delivering protected data;
- realtime correctness requires never missing a message;
- external webhook can SSRF prohibited targets, leak cross-tenant data or sign ambiguous/unbound content;
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
