# Security, Tenant Context and Data Classification

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines the trust model for asynchronous messages. It ensures that broker access, envelope fields, delayed execution or internal service credentials cannot become unintended tenant/authorization authority.

## Core rule

A message is **data plus bounded contract context**, not universal authority.

The receiver establishes whether it may trust:

- producer identity;
- message contract/version;
- tenant/global scope;
- source/generation;
- message identity scope;
- execution authority.

A broker-delivered message is not automatically trusted merely because it arrived on an internal network.

## Trust boundaries

Phase 10 crosses these accepted boundaries:

```text
owning use case -> outbox
outbox dispatcher -> broker/queue
broker/queue -> consumer
consumer -> domain/application authority
consumer -> external provider/service
integration event -> realtime fanout
integration event -> outbound webhook delivery
replay/admin control -> broker/consumer
```

Each boundary has explicit authentication, authorization, tenant/data and observability rules.

## Producer authentication

Only accepted producer identities may publish a contract namespace.

Transport credentials/ACLs SHOULD enforce least privilege such that a producer cannot arbitrarily publish every platform event family.

A compromised Monitoring publisher, for example, should not automatically gain authority to emit Organization & Access facts unless explicitly accepted.

Exact service identity/mTLS/OIDC/broker ACL technology remains OPEN.

## Producer authorization

Producer authorization is contract-scoped.

The platform maintains a governed mapping conceptually like:

```text
producer capability -> allowed contract namespace(s) -> allowed tenant/global scope
```

A broker's technical permission to write to a topic must align with the logical contract authority.

## Tenant scope

For tenant-scoped messages:

- `tenant_id` comes from trusted producing `TenantContext`/owner state;
- it is immutable logical identity;
- it is included in consumer isolation/dedup scope where required;
- it never identifies physical cell/database/shard;
- payload tenant text cannot override it.

A consumer SHALL fail closed if required tenant scope is missing, malformed or inconsistent with trusted route/source context.

## Global messages

Global contracts are explicit and rare.

A message without tenant scope is not automatically global. The declared `contract_name`/producer authority must permit global scope.

Consumers of global contracts must not accidentally run one effect per tenant unless the owning process explicitly enumerates and authorizes those effects.

## Tenant placement

A tenant-scoped async message identifies the logical tenant, not historical physical placement.

Before protected state access/mutation, the worker:

1. resolves current placement;
2. validates current placement/admission generation;
3. establishes trusted `TenantContext`;
4. uses owner-domain access policies/RLS as applicable.

A stale queue/topic/cell route is a hint that must be corrected, not authority to write stale placement.

## Delayed human authority

Human/session/membership authorization from message creation time does not persist automatically into delayed execution.

If the operation requires current human/policy authority, the message carries safe actor/request context for audit plus stable operation intent, while the worker rechecks current authority before protected execution/resume.

Examples include:

- user-requested export;
- privileged automation;
- administrative mutation;
- webhook subscription changes;
- tenant-scoped remediation.

The accepted process contract determines whether revocation causes cancellation, denial, wait-for-approval, compensation or reconciliation.

## Service principals

Workers use narrowly scoped machine/service identities.

A service principal declares:

- owning consumer capability;
- allowed contracts;
- tenant/global scope;
- allowed domain/application operations;
- secret access required;
- outbound network capabilities.

A generic worker credential with unrestricted database/provider access is prohibited.

## Message integrity

The accepted producer/broker path must preserve envelope/payload integrity.

Consumers validate:

- message framing/serialization;
- declared contract/version;
- required envelope fields;
- trusted producer context;
- tenant/source scope;
- payload schema/limits;
- optional signature/MAC where the transport/profile requires end-to-end integrity beyond broker trust.

The exact broker-integrity/auth profile remains OPEN, but consumers may not silently accept malformed or cross-contract messages.

## Message-equivalence evidence

Duplicate-sensitive consumers need durable evidence that a repeated scoped `message_id` still represents the **same immutable semantic message**, not merely the same identifier reused with different content.

That comparison evidence may be implemented as:

- a canonical collision-resistant fingerprint/digest under an accepted profile;
- an authenticated digest/MAC when payload entropy/classification makes plain digest disclosure unsafe;
- protected retained immutable content;
- another deterministic evidence form that proves semantic equivalence over the contract-defined immutable comparison surface.

The exact algorithm/storage mechanism remains OPEN, but these properties are fixed:

- evidence covers every immutable field whose difference would make same-ID reuse an integrity failure;
- comparison uses the same canonical structured interpretation as contract validation, not parser-specific raw-text accidents;
- the evidence record identifies/inherits a stable comparison-profile version sufficient to reproduce the same canonicalization/comparison surface for the supported horizon;
- evidence comparison occurs only after the trusted `(consumer_contract, message_identity_scope, message_id)` has been derived; a fingerprint is never a substitute for that trusted identity scope;
- where a digest/MAC construction supports domain separation, its input/context is bound to the accepted consumer/contract and trusted message-identity scope so the evidence cannot become an accidental cross-tenant/cross-consumer correlation namespace;
- evidence remains available for the full supported dedup/redelivery/replay/recovery horizon or equivalent surviving authority proves comparison;
- same scoped ID with non-equivalent evidence fails closed into integrity/quarantine handling and is never accepted as an ordinary duplicate;
- loss/rollback of comparison evidence or of the historical comparison profile/key authority needed to interpret it is recovery uncertainty, not permission to assume equivalence;
- evidence inherits the payload's confidentiality/retention/erasure risk and SHALL NOT become a new side channel;
- evidence is correctness/recovery evidence only: it is not authorization, tenant routing, ordering authority, a public/external identifier, or a bearer capability.

Comparison evidence SHALL NOT be used as a global reverse lookup such as `find tenant/message by fingerprint`. Lookup begins from trusted scoped message identity; only then may the corresponding evidence be compared. Implementations prevent unrestricted equality-oracle behavior across tenants, consumers or unrelated contract namespaces.

A plain unsalted/unkeyed digest of low-entropy confidential values may permit offline guessing and is not automatically a safe storage/logging representation. Where that risk exists, the accepted profile uses a protected comparison mechanism such as keyed/authenticated hashing or protected retained evidence. Fingerprints/MACs are not logged casually and are not exposed externally as message identifiers.

When keyed/authenticated comparison evidence is used:

- the receipt/evidence retains a non-secret stable key/profile generation reference sufficient to determine the historical verification authority;
- key material itself remains behind the accepted secret/KMS boundary and is never copied into the message, ordinary inbox payload, log or quarantine record;
- key/profile rotation either preserves historical comparison ability for the supported dedup/replay/recovery horizon or performs an explicitly governed evidence migration that proves equivalence before retiring the old verifier;
- loss, retirement or temporary unavailability of a historical verifier does **not** turn unknown equivalence into duplicate success or new effect eligibility; the affected identity stays fail-closed/reconciliation-blocked until an accepted authority proves equivalence;
- successful verification with a current key/profile does not retroactively re-authorize, re-scope or otherwise reinterpret an old message.

Canonicalization/comparison-profile evolution follows the same discipline. A new parser/canonicalization release may not silently recompute an old receipt under different rules and then treat a mismatch as message corruption or, worse, treat changed content as equivalent. Historical evidence remains interpretable under its accepted profile, or a reviewed deterministic migration preserves the old semantic comparison result before retirement.

Erasure/minimization may replace full payload retention with the smallest governed comparison evidence sufficient for duplicate/recovery safety, but erasure cannot remove all equivalence evidence while the same logical message remains eligible to redeliver/replay and duplicate suppression still matters. If policy requires destroying the last usable comparison authority, the corresponding old identity/replay path must cease to be effect-eligible or remain fail-closed under the accepted governance/reconciliation policy; erasure cannot manufacture proof of equivalence.

## Provider-originated data

Provider callbacks are untrusted external ingress until Phase 09 authentication/freshness/replay/canonical parsing/tenant binding completes.

An internal async message derived from provider data:

- uses JLMIRROR `contract_name`;
- uses trusted tenant/integration mapping;
- may retain provider identifiers only as explicit external references;
- does not expose raw provider credentials/signatures;
- does not let provider fields select producer/tenant authority.

## Message data classification

Every contract declares data classification sufficient for:

- publication eligibility;
- broker/storage placement;
- encryption requirements;
- logging/redaction;
- retention/replay;
- cross-region restrictions;
- realtime exposure;
- outbound webhook disclosure.

Baseline classes are logical and may map to existing organization policy:

```text
public
internal
confidential_tenant
sensitive_or_regulated
secret_or_credential
```

`secret_or_credential` content is not permitted in ordinary async payloads.

Derived correctness evidence such as message fingerprints, authenticated digests, tombstones and result-linkage metadata is classified deliberately rather than assumed harmless. If the derivation can reveal or test confidential source values, it receives corresponding protection, retention and logging restrictions. Comparison-profile/key-generation references are also governed metadata: they may aid recovery/version selection but never grant key access or message authority.

## Secret references

When work requires secret material, the message carries an opaque reference/identity rather than the secret.

The worker:

- authenticates under its own narrow service identity;
- checks tenant/resource scope;
- retrieves only the required secret at execution time;
- does not persist the plaintext back into message/inbox/log/quarantine state;
- honors revocation/rotation.

A secret reference is not authorization by itself.

Keyed message-equivalence evidence follows the same secret boundary. The inbox/evidence record may retain a non-secret verifier/profile generation reference needed for historical comparison, but that reference does not authorize key retrieval by arbitrary workers. Only the narrowly authorized comparison/recovery path may obtain the required historical verifier material.

## Payload minimization

Async contracts publish only the data consumers actually require.

Avoid:

- full database row serialization;
- unnecessary PII;
- full provider responses;
- unrestricted raw documents;
- large telemetry samples;
- authorization/session/token state.

Consumers needing current mutable state may receive a stable resource reference and fetch an authorized projection instead of receiving a stale oversized snapshot.

Correctness evidence is minimized independently from payload retention. A consumer may retain a protected canonical fingerprint/result linkage plus the minimum comparison-profile/version reference after deleting full payload bytes, but only when that evidence still satisfies classification, erasure, historical verification and recovery requirements.

## Encryption

Transport/storage encryption is required according to security/data policy.

Exact broker encryption/KMS technology remains OPEN.

Encryption at rest/in transit does not make an over-broad payload acceptable; minimization and authorization remain required.

## Logs and traces

Normal logs SHALL NOT contain:

- credentials/tokens/secrets;
- unrestricted confidential payloads;
- full regulated records;
- protected cursor/capability values;
- webhook signing material;
- message-equivalence fingerprints/MACs when their classification or offline-guessing risk makes them unsuitable for ordinary observability.

Safe observability uses:

```text
message_id
contract/version
consumer/producer
safe tenant hash/reference
operation/correlation IDs
error class
attempt/retry/quarantine state
```

Payload sampling, if ever enabled, requires explicit classification/redaction policy.

A safe reason may record that equivalence verification was unavailable, profile-mismatched or content-conflicting, but normal logs do not emit the compared confidential content, verifier material, raw MAC/fingerprint, or unrestricted cross-tenant equality data.

## Quarantine security

Quarantine is a security/data store and inherits classification/retention controls.

Operators do not gain unrestricted tenant payload visibility merely because a message failed.

Remediation tooling applies:

- current operator authorization;
- tenant scope;
- redacted/safe views;
- audit;
- bounded export/download.

For same-ID/different-content integrity failures, quarantine/diagnostics may retain governed comparison evidence, comparison-profile references and safe reason classes without exposing unrestricted conflicting payloads or verifier material to ordinary operators.

## Replay security

Replay is privileged.

Replay authorization includes:

- allowed contract/consumer;
- tenant/global range;
- time/message range;
- target projection/rebuild generation;
- data-retention eligibility;
- external-effect safety.

A replay operator cannot bypass tenant isolation by choosing arbitrary message IDs/offsets.

Replay that depends on historical duplicate suppression also depends on the corresponding historical comparison authority. If its profile/verifier is unavailable or retired without a proved migration, replay remains blocked/reconciliation-required for duplicate-sensitive effects rather than treating the old receipt as equivalent by identity alone.

## Realtime security

Realtime messages are sent only after Phase 09 current subscription authority.

Phase 10 payloads do not contain any field capable of extending/renewing authority independently.

If authority is revoked, protected delivery stops even if:

- socket is open;
- subscription ID is known;
- resume cursor is valid;
- old messages remain buffered.

## Outbound webhook disclosure

Only an accepted external webhook projection may leave the platform.

Before delivery, the webhook adapter validates:

- current subscription status;
- tenant/event scope;
- payload classification allowed for that destination/profile;
- destination SSRF/network policy;
- signing credential/reference.

Internal event availability does not imply external disclosure permission.

## Cross-region/data residency

If Product/compliance later requires regional residency, the event contract must remain logical while deployment enforces where message data may be stored/delivered.

A contract must not require cross-region broker replication merely because the initial broker topology is global.

Region/cell IDs remain deployment metadata, not payload/business identity.

## Multi-tenant broker isolation

Possible implementation patterns include shared broker with strong logical isolation or dedicated infrastructure for selected tenants/cells.

The contract stays the same.

Required properties:

- no cross-tenant consumption from weak topic naming;
- tenant context trusted from producer boundary;
- service ACLs scoped appropriately;
- replay/admin tools respect tenant boundaries;
- telemetry/logging do not leak payloads across tenants;
- equivalence evidence is compared only inside the trusted consumer/message-identity scope and is not exposed as a cross-tenant correlation/oracle surface.

## Message spoofing / confused deputy

Consumers must prevent a message from causing them to exercise broader authority than the producer contract permits.

A message saying:

```json
{"action":"delete_everything","tenant_id":"other"}
```

has no authority unless that exact command contract, producer, tenant scope and current execution policy are accepted.

Generic "action" event buses that let payload text select arbitrary privileged operations are prohibited.

Message-equivalence evidence cannot widen this authority. A matching MAC/fingerprint proves only the accepted comparison statement for the already-derived scoped identity; it does not authenticate a new producer, tenant, command or permission.

## Schema/parser attacks

Message parsers use bounded canonical structured parsing.

At minimum:

- duplicate protected object keys rejected;
- malformed/ambiguous encoding rejected;
- size/depth/count limits;
- XML/active external resolution disabled unless separately accepted;
- decompression bounds when compression exists;
- deserializer type confusion/polymorphic code execution disabled.

Internal transport does not make parser input harmless because producers/integrations can be compromised or buggy.

Message-equivalence evidence is computed/verified over the accepted canonical semantic interpretation, not over whichever parser representation a worker happens to produce. Canonicalization/comparison profiles are versioned and retained/migrated consistently with supported historical receipts.

## Supply chain / schema trust

Generated message code/schema artifacts come from reviewed contract sources.

Consumers do not dynamically fetch untrusted schemas/code from message-provided URLs.

Schema-registry access is authenticated/authorized; registry compromise is included in threat modeling.

Comparison-profile implementations and migrations are reviewed contract/security artifacts as well. A compromised or unreviewed canonicalizer/fingerprint implementation cannot silently redefine equality for previously admitted message identities.

## Recovery security

After restore/PITR:

- stale authorization caches/generations do not regain authority;
- stale producer generations remain retired where required;
- missing inbox/replay state is uncertainty, not permission;
- missing/older message-equivalence evidence is uncertainty, not proof that a same-ID arrival matches the original message;
- missing historical comparison-profile/verifier authority is likewise uncertainty, not proof of equality or effect eligibility;
- quarantined/ambiguous effects remain blocked until reconciliation;
- audit/security evidence in `(R,F]` is restored/reconciled.

Recovery reconciles not only evidence bytes but the profile/key-generation authority needed to interpret them. A restore that revives an old comparison key/profile does not make that verifier current authority for unrelated messages, and a restore that loses the historical verifier does not convert existing receipts into unverified duplicates.

Recovery availability does not outrank tenant/security correctness.

## Abuse and DoS

Message surfaces enforce bounded:

- message bytes;
- batch count;
- nesting/collection complexity;
- publish rate;
- consumer concurrency;
- retries;
- replay scope/rate;
- quarantine size/retention.

One tenant/provider/producer cannot create unbounded global cost.

Comparison-evidence APIs/stores are not exposed as unrestricted hashing/equality oracles. Failed comparisons, historical-key lookups and migration work are rate/budget bounded according to the owning reliability/security profile so an attacker cannot force unbounded KMS/secret-store work through crafted duplicate IDs.

## Required security tests

Implementations test:

- producer cannot publish unauthorized contract namespace;
- payload tenant cannot override trusted envelope tenant;
- stale cell route cannot mutate retired tenant placement;
- delayed job after permission/session revocation is denied/handled by process policy;
- generic worker credential cannot access unrelated tenant/domain secrets;
- provider payload cannot spoof internal producer/contract identity;
- secret values fail message schema/publication/logging rules;
- same scoped message ID with different canonical immutable content is detected even after full payload retention has been minimized;
- equivalence-evidence retention/restore loss cannot convert same-ID/different-content into an accepted duplicate;
- low-entropy confidential payload comparison evidence is not exposed through naive ordinary logs or externally visible identifiers;
- same semantic content under different tenant/consumer scopes cannot use equivalence evidence to create cross-scope deduplication or an externally queryable correlation oracle;
- comparison-profile/canonicalization upgrade preserves historical equality semantics or fails closed until a reviewed migration proves equivalence;
- keyed/MAC evidence remains historically verifiable across accepted key rotation, or old duplicate-sensitive identities stay fail-closed when the verifier is unavailable/retired;
- restore to before comparison-key/profile rotation does not resurrect obsolete verifier authority for unrelated messages;
- historical verifier outage/loss never changes unknown equivalence into duplicate success or protected-effect eligibility;
- quarantine/replay admin tooling enforces tenant/operator scope;
- realtime buffered message is not delivered after authority retirement beyond accepted fence;
- webhook destination cannot SSRF internal/control-plane targets;
- parser duplicate/oversize/decompression/type-confusion attacks fail boundedly;
- restore does not resurrect stale producer/replay/authorization authority.

## Intentionally OPEN

- service identity technology;
- broker ACL syntax/product;
- message encryption/KMS product;
- exact data-classification labels mapping;
- cross-region topology;
- end-to-end message signature profile where needed;
- message-equivalence fingerprint/MAC algorithm, domain-separation construction and storage representation;
- comparison-profile/version representation and migration mechanism;
- historical verifier/key-generation retention or migration implementation;
- replay/quarantine admin UI implementation.

The trust, tenant isolation, current authority, message-equivalence integrity, scoped/non-oracular comparison, historical profile/verifier continuity, data minimization and fail-closed recovery properties are fixed.
