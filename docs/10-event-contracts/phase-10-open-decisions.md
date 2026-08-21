# Phase 10 — OPEN Decisions

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This file records intentionally unresolved Phase 10 implementation/profile choices so they cannot be mistaken for omissions or silently fixed by a framework, broker SDK or deployment default.

An OPEN decision may be prototyped, benchmarked or compared, but it becomes canonical only through the accepted governance process.

## OPEN-EVT-001 — Broker / queue / pub-sub technology

**Question:** Which concrete transport products satisfy each workload class?

Candidates may include managed queues, log-based brokers, pub/sub systems or specialized fanout products.

**Already fixed:**

- logical contracts are broker-neutral;
- default delivery is at least once;
- broker semantics alone do not prove exactly-once business effects;
- tenant/producer/consumer/message identity does not depend on physical topic/partition IDs;
- outbox/inbox/reconciliation invariants survive product replacement;
- high-volume raw telemetry is not forced through the general event broker.

## OPEN-EVT-002 — Wire serialization and schema language

**Question:** Which concrete serialization/schema formats are used for internal broker messages and external webhook contracts?

Candidates may include JSON Schema, Protobuf, Avro or equivalent reviewed profiles.

**Already fixed:**

- one canonical bounded structured interpretation;
- duplicate/alias protected fields fail closed;
- explicit required/optional/null/enum semantics;
- payload/envelope authority cannot be overridden by parser ambiguity;
- historical contract meaning is preserved;
- duplicate-sensitive consumers have one deterministic immutable-content equivalence profile for a scoped message identity;
- the canonical comparison profile/version used for historical message-equivalence evidence remains reproducible or is migrated with equality-preserving evidence before retirement;
- no dynamic untrusted schema/code loading.

The first-party Phase 10 realtime protocol baseline uses bounded canonical JSON; future protocol revisions may choose another explicitly versioned representation.

## OPEN-EVT-003 — Schema registry / contract catalog tooling

**Question:** Which registry/catalog/code-generation/diff tooling stores machine-readable contracts and supports compatibility CI?

**Already fixed:**

- reviewed contract is canonical;
- version provenance/history is retained;
- semantic manifest is compared in addition to payload schema;
- supported historical replay retains the schema/reader/upcaster and comparison-profile metadata required to interpret messages and preserve content-equivalence evidence;
- registry access is authenticated/authorized.

## OPEN-EVT-004 — Contract-version syntax

**Question:** Exact string/number representation for async `contract_version`.

**Already fixed:**

- it is distinct from deployment/API/provider/realtime-protocol/schema-registry versions;
- breaking semantic changes require a new incompatible contract version/family or accepted migration;
- historical messages retain original version semantics.

## OPEN-EVT-005 — Topic/queue/subject naming and topology

**Question:** Physical naming, routing, exchanges/topics/subjects, consumer groups and per-cell/global topology.

**Already fixed:**

- topology is not canonical contract identity;
- no physical cell/database/provider/broker identity leaks into logical message semantics;
- tenant isolation and producer authorization remain enforceable;
- service extraction/broker replacement must not require consumer semantic rewrite.

## OPEN-EVT-006 — Partition count and partition-key implementation

**Question:** Concrete partition counts and transport mapping for ordered/scaled workloads.

**Already fixed:**

- no global ordering promise;
- ordering is contract-specific and scoped to the smallest required logical boundary;
- ordering key derives from trusted logical identity;
- physical partition ID is not public/canonical ordering identity;
- dedup identity and ordering sequence are separate.

## OPEN-EVT-007 — Retry/backoff/jitter numeric profiles

**Question:** Attempts, durations, backoff curves, jitter, dependency/tenant concurrency budgets and emergency throttling values.

**Already fixed:**

- retries are bounded;
- transient/throttled/permanent/ambiguous/recovery-blocked classes are distinct;
- external ambiguity never becomes blind retry;
- retry storms are isolated/budgeted;
- poison/unknown reaches governed quarantine.

## OPEN-EVT-008 — Broker acknowledgement / visibility / lease primitives

**Question:** Concrete ack mode, visibility timeout, lease/claim mechanism and checkpoint implementation.

**Already fixed:**

- ack/checkpoint does not precede durable consumer responsibility;
- lease/timeout expiry does not prove effect absence;
- broker progress is not business-effect truth;
- offset rewind remains safe through inbox/effect idempotency and scoped-ID content-equivalence checks.

## OPEN-EVT-009 — Quarantine / DLQ implementation

**Question:** Storage/UI/workflow for quarantined messages and mapping to broker-native DLQs.

**Already fixed:**

- quarantine is the canonical platform meaning;
- broker DLQ alone is not process/reconciliation truth;
- retry is bounded;
- redrive is privileged/audited/currently authorized;
- redrive cannot bypass dedup/reconciliation;
- conflicting same-ID/different-content arrivals fail closed into governed integrity/quarantine handling;
- payload and derived equivalence evidence retention obey data classification and do not grant ordinary operators unrestricted confidential comparison material.

## OPEN-EVT-010 — Message/payload/batch limits

**Question:** Exact bytes, nesting, string/list/count, batch and compression/decompression limits by contract/workload.

**Already fixed:**

- unlimited input is not accepted;
- parsing/decompression is bounded;
- large artifacts/telemetry are referenced/routed to appropriate specialized planes rather than embedded without bound.

## OPEN-EVT-011 — Inbox/dedup storage, content-equivalence evidence and retention durations

**Question:** Concrete store/table design, canonical fingerprint/hash/MAC or equivalent comparison representation, comparison-profile/version encoding, historical verifier reference representation, and per-contract retention horizon.

**Already fixed:**

- identity is `(consumer_contract, trusted message_identity_scope, message_id)` or equivalent;
- a repeated scoped identity is a normal duplicate only when durable evidence proves equivalent immutable contract/envelope/payload semantics;
- same scoped ID with different immutable semantic content is integrity/producer-contract failure, not successful duplicate suppression;
- accepted comparison evidence may be a canonical collision-resistant fingerprint, authenticated digest/MAC, protected retained immutable original, or equivalent durable authority;
- the equivalence profile covers every immutable field whose change would make the same scoped ID denote a different logical message;
- comparison evidence uses the same canonical structured interpretation as protected contract validation and carries/inherits a stable comparison-profile version;
- evidence is compared only after trusted scoped message identity is derived and cannot become a cross-tenant/cross-consumer reverse lookup or equality/correlation oracle;
- low-entropy confidential source values are not automatically safe behind an ordinary plain digest; the accepted profile uses a protected comparison form when disclosure/dictionary risk requires it;
- equivalence evidence is correctness/recovery evidence only, never authorization, routing, ordering authority, external identity or bearer capability;
- local inbox/effect completion is atomic when co-resident;
- cross-authority effects use stable operation/result reconciliation;
- comparison evidence and any profile/verifier authority required to interpret it remain available for the supported redelivery/replay/recovery horizon, or a governed migration/equivalent authority proves historical equality;
- payload minimization/erasure cannot remove the last usable comparison authority while the ID can still legitimately reappear and remain effect-eligible;
- restore missing receipt, comparison evidence or historical comparison authority is not `never processed` or `safe duplicate`;
- comparison/KMS/secret-store verification work is bounded and cannot be exposed as an unrestricted equality oracle or amplification path.

The exact hash/MAC algorithm, domain-separation encoding, store/schema, comparison-profile representation and implementation product remain OPEN; the durable, confidentiality-safe, scoped and fail-closed equivalence properties are not OPEN.

## OPEN-EVT-012 — Outbox dispatcher implementation and retention

**Question:** Claim primitive, dispatcher topology, polling/notification mechanism, cleanup and retention duration.

**Already fixed:**

- required outbox is committed with authoritative mutation;
- immutable fact evidence is not rewritten by retry workers;
- broker-ack ambiguity retries the same message identity and immutable message meaning;
- broker outage preserves committed backlog;
- recovery preserves/reconstructs stable message identity and semantic content.

## OPEN-EVT-013 — Producer/source generation encoding

**Question:** Concrete representation/storage/validation for source/producer generation across relocation, failover, recovery and provider cutover.

**Already fixed:**

- retired current-source generation cannot regain authority;
- historical facts and current-source commands/signals are distinguished;
- tenant logical identity does not change with placement;
- restore cannot resurrect retired source authority.

## OPEN-EVT-014 — Replay/event-history storage and retention

**Question:** Which durable history source supports replay, how far back, and through which administrative execution model.

**Already fixed:**

- replay is privileged/audited/bounded;
- same historical message preserves original message identity and immutable semantic meaning;
- duplicate-sensitive replay retains or reconstructs the content-equivalence evidence and historical comparison authority needed to reject conflicting same-ID reuse;
- unavailable historical comparison authority blocks/reconciles duplicate-sensitive effects rather than trusting identity alone;
- irreversible production side effects cannot be repeated by disabling dedup;
- projection rebuild uses isolated generation/target;
- supported replay never exceeds safe schema/data/dedup/equivalence/recovery evidence.

## OPEN-EVT-015 — Upcaster / historical reader implementation

**Question:** Tooling/runtime for reading retained old versions and deterministic representation adaptation.

**Already fixed:**

- historical semantic meaning is immutable;
- upcasting cannot fabricate newer historical facts;
- source message identity/tenant/occurrence semantics remain traceable;
- supported retained history remains interpretable;
- upcasting preserves or deterministically maps any message-content equivalence evidence and comparison-profile semantics required by duplicate-sensitive consumers.

## OPEN-EVT-016 — Service-to-broker authentication/authorization

**Question:** mTLS, workload identity/OIDC, broker-native credentials/ACLs or another service identity mechanism.

**Already fixed:**

- producer authorization is least-privilege and contract-scoped;
- consumer service identities are tenant/domain constrained;
- internal network/broker presence alone is not trust;
- secrets are referenced, not embedded in messages.

## OPEN-EVT-017 — Message encryption / KMS and historical verifier profile

**Question:** Concrete encryption-at-rest/in-transit, key management, and historical verifier/key-generation storage/access profile for broker/history/quarantine and keyed message-equivalence evidence.

**Already fixed:**

- data classification controls storage/delivery/logging/retention;
- encryption does not replace minimization/authorization;
- secret/credential payloads are prohibited in ordinary messages;
- when keyed/authenticated equivalence evidence is used, key material remains behind the accepted secret/KMS authority and is never copied into ordinary messages, inbox payloads, logs or quarantine records;
- retained receipts/evidence carry only non-secret profile/key-generation references sufficient to locate the historical verification authority under narrow authorization;
- key/profile rotation preserves historical comparison ability for the supported equivalence horizon or completes a governed equality-preserving migration before old verifier retirement;
- temporary loss or retirement of historical verifier authority does not turn unknown equivalence into duplicate success or protected-effect eligibility;
- restoring an old verifier/profile does not make it current authority for unrelated messages or scopes.

The KMS/vendor, key type, crypto algorithm, rotation interval and verifier-storage product remain OPEN; historical verifiability, secret-boundary isolation and fail-closed verifier loss are fixed.

## OPEN-EVT-018 — Trace-context propagation

**Question:** Exact distributed tracing headers/fields/profile propagated across async boundaries.

**Already fixed:**

- trace context is observability only;
- never tenant, authorization, idempotency or ordering authority;
- bounded/validated/redacted according to policy.

## OPEN-EVT-019 — Realtime numeric and transport tuning

**Question:** Message/frame bounds, compression/binary support, heartbeat, slow-client buffer policy values, fanout product and exact close codes.

**Already fixed:**

- Phase 09 owns current connection/subscription authority lifecycle;
- Phase 10 protocol major 1 is distinct from event/API/admission versions;
- messages are non-authoritative projections;
- slow clients are bounded and may be dropped/coalesced/resynced/closed according to contract;
- gaps/state loss lead to authoritative resync;
- reconnect requires fresh Phase 09 admission.

## OPEN-EVT-020 — Realtime resume/cursor profile

**Question:** Which subscriptions support resume, token encoding, retention window and sequence/cursor source.

**Already fixed:**

- resume is not authorization or placement authority;
- current subscription authorization always applies;
- gap/expiry/relocation/recovery uncertainty may force resync;
- sensitive tokens are not logged casually;
- clients can recover through authoritative snapshot/API state.

## OPEN-EVT-021 — Outbound webhook Product scope

**Question:** Whether/which event families are exposed externally and to which customer/integration use cases.

**Already fixed:**

- internal event existence does not automatically create an external webhook Product feature;
- external disclosure requires explicit Product/security/data approval;
- tenant subscription binding and destination security are mandatory when enabled;
- each admitted delivery is bound to the tenant/subscription disclosure scope and exact authorized destination configuration generation under which the obligation was created.

## OPEN-EVT-022 — Outbound webhook signature/auth profile

**Question:** Exact algorithm, covered representation, timestamp window, key storage/rotation and verification guidance.

**Already fixed:**

- authenticity covers the intended payload/delivery identity and freshness-relevant metadata;
- unbound timestamp is insufficient;
- secrets are referenced/stored in secret authority, never normal payload/log;
- retry preserves delivery/source identity;
- attempt-scoped authentication metadata may change only under the accepted profile and cannot mutate webhook semantic payload, contract version, tenant/subscription scope or destination configuration generation.

## OPEN-EVT-023 — Webhook retry, delivery identity and destination-generation implementation

**Question:** Attempts/window/backoff/throttling/terminal policy, concrete storage/representation of the immutable delivery semantic snapshot, globally unique delivery-ID generation mechanism, destination configuration-generation representation, and the Product-specific cancel/fence/quarantine/reissue behavior when destination/disclosure authority changes.

**Already fixed:**

- external delivery is at least once unless stronger end-to-end proof exists;
- one stable `webhook_delivery_id` identifies one immutable external semantic delivery obligation for the full supported retry/recovery horizon;
- the default delivery-ID namespace is globally unique across tenants/subscriptions; any future scoped external identity must expose the complete stable scope required for deduplication;
- retry of the same delivery ID preserves webhook contract/version, source identity, tenant/subscription scope, canonical semantic payload meaning and the exact bound destination configuration generation;
- rolling deployment/current mutable state cannot change the semantic body represented by the same delivery ID;
- subscriber timeout may redeliver the same immutable delivery obligation only while its bound destination generation remains eligible;
- a destination/configuration generation change never silently retargets the existing delivery ID;
- old-generation obligations are cancelled/fenced/quarantined or deliberately reissued according to accepted Product/security policy;
- deliberate reissue under a new destination generation is a new delivery obligation with a new delivery ID and causation to the original;
- one subscriber cannot exhaust global delivery capacity;
- permanent/security failure reaches governed terminal state;
- restore/PITR cannot resurrect retired destination generations or reconstruct an existing delivery ID with changed semantics.

The exact ID algorithm, snapshot storage, generation encoding and per-Product cancel/quarantine/reissue choice remain OPEN; the stable identity/semantic-freeze/generation-fence properties are not OPEN.

## OPEN-EVT-024 — Webhook egress/SSRF implementation

**Question:** Exact DNS/IP validation, proxy/egress, private-network deny/allow policy, redirect handling and TLS profile.

**Already fixed:**

- arbitrary subscriber URL cannot reach prohibited metadata/internal/control-plane targets;
- redirects cannot escape destination policy;
- response/time/size/concurrency are bounded;
- redirects or retries cannot escape the delivery obligation's bound destination-configuration authority.

## OPEN-EVT-025 — Recovery-generation and reconciliation tooling

**Question:** Exact epoch/generation encoding, `(R,F]` inventory automation, broker/history/inbox/webhook/equivalence-profile reconciliation tools and activation gates.

**Already fixed:**

- missing restored state is uncertainty, not absence;
- missing/older content-comparison evidence is not proof of a safe duplicate;
- retained comparison evidence is not sufficient when the historical canonicalization/profile/verifier authority required to interpret it is missing, stale or unknown;
- effectful async admission and duplicate classification remain fail-closed until required continuity/equivalence and historical comparison authority are proven;
- stale producer/replay/authorization/webhook-destination authority does not revive;
- restored obsolete comparison verifier/profile cannot become current authority for unrelated messages or scopes;
- offset/outbox/inbox state alone cannot contradict surviving external/audit/effect/equivalence evidence;
- webhook recovery preserves stable delivery identity, semantic snapshot/reproduction authority and destination-generation fences.

## OPEN-EVT-026 — Numeric retention / replay / quarantine horizons

**Question:** Concrete durations by workload/data class.

**Already fixed:**

- replay support does not exceed safe schema/dedup/content-equivalence/data evidence;
- message-content comparison evidence survives as long as the scoped ID can legitimately redeliver/replay/recover, or an alternate durable authority proves equivalence;
- any historical comparison profile/verifier generation required to interpret retained evidence survives for the same supported horizon or is replaced by an equality-preserving governed migration before retirement;
- unresolved same-ID/content conflicts or unknown historical verifier state never age into benign duplicate success;
- unresolved irreversible ambiguity never expires into blind retry;
- legal hold/erasure governance overrides ordinary broker cleanup as required;
- schema definitions/readers remain available for supported retained history;
- webhook retry/recovery cannot outlive the identity/snapshot/destination-generation evidence needed to prove what the stable delivery ID means and where it may still be sent.

## OPEN-EVT-027 — Cross-region / residency deployment

**Question:** Broker/history replication and data residency topology for future regional/compliance requirements.

**Already fixed:**

- logical contract remains region/cell independent;
- no contract forces global replication by accident;
- tenant/data classification and current placement/security remain enforceable;
- physical region/cell identifiers are not canonical payload semantics.

## OPEN-EVT-028 — Contract/deprecation support durations

**Question:** Minimum support/deprecation periods for internal integration contracts, external webhooks and realtime protocol majors.

**Already fixed:**

- retirement is measured/governed;
- supported producers/consumers/history must no longer depend on the retired version or a retained adapter/reader must exist;
- retained message-content equivalence evidence and any historical comparison authority required to interpret it remain until duplicate/replay/recovery support for the associated identities safely ends or migrates;
- external webhook subscribers require explicit migration policy when Product enables them.

## OPEN discipline

No implementation choice closes an OPEN item merely because:

- a framework ships a default;
- a broker feature is convenient;
- the first deployment has one cell/service;
- an SDK generates a schema;
- a cloud product makes a topology easy.

The fixed semantic/security/recovery properties remain normative regardless of which implementation option is selected.
