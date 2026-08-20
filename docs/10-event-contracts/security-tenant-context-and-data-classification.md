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

## Secret references

When work requires secret material, the message carries an opaque reference/identity rather than the secret.

The worker:

- authenticates under its own narrow service identity;
- checks tenant/resource scope;
- retrieves only the required secret at execution time;
- does not persist the plaintext back into message/inbox/log/quarantine state;
- honors revocation/rotation.

A secret reference is not authorization by itself.

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
- webhook signing material.

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

## Quarantine security

Quarantine is a security/data store and inherits classification/retention controls.

Operators do not gain unrestricted tenant payload visibility merely because a message failed.

Remediation tooling applies:

- current operator authorization;
- tenant scope;
- redacted/safe views;
- audit;
- bounded export/download.

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
- telemetry/logging do not leak payloads across tenants.

## Message spoofing / confused deputy

Consumers must prevent a message from causing them to exercise broader authority than the producer contract permits.

A message saying:

```json
{"action":"delete_everything","tenant_id":"other"}
```

has no authority unless that exact command contract, producer, tenant scope and current execution policy are accepted.

Generic "action" event buses that let payload text select arbitrary privileged operations are prohibited.

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

## Supply chain / schema trust

Generated message code/schema artifacts come from reviewed contract sources.

Consumers do not dynamically fetch untrusted schemas/code from message-provided URLs.

Schema-registry access is authenticated/authorized; registry compromise is included in threat modeling.

## Recovery security

After restore/PITR:

- stale authorization caches/generations do not regain authority;
- stale producer generations remain retired where required;
- missing inbox/replay state is uncertainty, not permission;
- quarantined/ambiguous effects remain blocked until reconciliation;
- audit/security evidence in `(R,F]` is restored/reconciled.

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

## Required security tests

Implementations test:

- producer cannot publish unauthorized contract namespace;
- payload tenant cannot override trusted envelope tenant;
- stale cell route cannot mutate retired tenant placement;
- delayed job after permission/session revocation is denied/handled by process policy;
- generic worker credential cannot access unrelated tenant/domain secrets;
- provider payload cannot spoof internal producer/contract identity;
- secret values fail message schema/publication/logging rules;
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
- replay/quarantine admin UI implementation.

The trust, tenant isolation, current authority, data minimization and fail-closed recovery properties are fixed.
