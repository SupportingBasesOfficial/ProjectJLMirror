# Schema Evolution, Compatibility and Governance

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines how asynchronous contracts are authored, versioned, reviewed, tested and evolved while producers/consumers coexist across rolling deployments, replay historical messages and move across service/broker/topology boundaries.

Schema shape is only one compatibility dimension. Delivery, identity, ordering, retry, recovery and security semantics are equally part of the contract.

## Canonical contract direction

The reviewed contract is canonical:

```text
accepted async contract
  -> machine-readable schema/manifest
  -> generated/shared types where useful
  -> producer implementation
  -> consumer implementation
  -> broker adapters/topology
```

The reverse direction is prohibited as the canonical source:

```text
ORM class / queue DTO / broker schema / provider payload
  -> accidental public integration contract
```

A generated schema ID or broker topic does not define semantic truth independently of the reviewed contract.

## Contract package

Every implemented Phase 10 contract has a reproducible package containing as applicable:

- human-readable normative contract;
- machine-readable payload/envelope schema;
- semantic manifest;
- compatibility metadata;
- example/test vectors with no secrets;
- producer/consumer ownership metadata;
- data classification;
- deprecation/support state.

Exact schema-registry/code-generation tooling remains OPEN.

## Semantic manifest

Every async contract declares/inherits structured metadata at least equivalent to:

```text
contract_name
contract_version
message_class
owning_producer_capability
allowed_producer_authority
allowed_consumer_contracts or discovery policy
tenant_scope_policy
message_identity_policy
message_identity_scope_policy
producer_generation_policy
subject_identity_policy
payload_schema_profile
data_classification
correlation_causation_policy
publication_outbox_policy
delivery_semantics
ack_durable_responsibility_policy
retry_classification_policy
quarantine_policy
consumer_effect_completion_policy
ordering_profile
ordering_scope_policy
sequence_gap_policy
replay_policy
replay_identity_policy
retention_policy
recovery_continuity_policy
current_placement_policy
current_authorization_policy
realtime_projection_policy
outbound_webhook_projection_policy
observability_policy
audit_policy
compatibility_class
deprecation_state
```

`not_applicable` is an explicit value where a dimension genuinely does not apply. Silent omission is not accepted for security/correctness-sensitive dimensions.

## Consumer manifest

Each consumer additionally declares:

```text
consumer_contract
accepted_contract_name/version range
trusted message_identity_scope derivation
effect owner/effect class
inbox/idempotency mechanism
local transaction or cross-authority completion profile
external ambiguity/reconciliation policy
ordering/gap handling
replay/rebuild behavior
placement/auth execution behavior
retry/quarantine policy
```

A broker subscription/group alone is not a complete consumer contract.

## Contract versioning model

Phase 10 distinguishes:

```text
contract semantic version
realtime protocol version
API version
provider protocol version
deployment version
schema-registry artifact ID
```

These are independent unless an accepted contract explicitly relates them.

### Contract major

A breaking semantic change requires a new contract major/version family or an explicitly accepted migration mechanism.

Breaking changes include more than schema deletion. Examples:

- changing tenant/global scope;
- weakening/changing message identity namespace;
- changing fact into command semantics;
- changing at-least-once duplicate behavior in a way old consumers cannot safely handle;
- adding a new required ordering guarantee old producers cannot satisfy;
- removing a prior ordering guarantee consumers rely on;
- changing source-generation meaning;
- changing replay identity from original ID to new IDs;
- shortening retention below supported replay/dedup horizon;
- changing acknowledgement/completion boundary;
- changing authorization/current-placement requirements;
- broadening external webhook disclosure;
- changing field meaning/units while keeping name/type;
- turning a previously closed enum into incompatible semantic behavior.

### Compatible additive evolution

Within one supported major, compatible changes may include:

- adding optional payload fields whose absence preserves old semantics;
- adding documented open-enum values where consumers are required to tolerate unknown values;
- adding non-authoritative observability metadata;
- adding a new independent event contract rather than changing existing semantics;
- extending consumer support to a newer compatible producer version.

A field being optional in JSON is not enough; semantic default/absence behavior must be defined.

## Field rules

Every field declares:

- required/optional;
- meaning and units;
- null/absence semantics;
- data classification;
- open/closed enum behavior;
- bounds;
- compatibility implications.

The platform does not rely on language-default zero/empty/null behavior for contract meaning.

## Unknown fields

Consumers of an additive-compatible schema SHOULD tolerate unknown fields when the contract says the object is extensible.

Security-sensitive consumers still validate known protected fields strictly and reject:

- duplicate/alias protected fields;
- malformed type/encoding;
- fields that conflict with envelope authority;
- unbounded unknown content beyond accepted size limits.

Unknown-field tolerance does not mean arbitrary payload execution.

## Enums

Enums are explicitly:

```text
open
closed
```

An open enum requires consumers to tolerate unknown future values without unsafe default behavior.

A closed enum adding a value is potentially breaking and requires compatibility review/version change.

Consumers SHALL NOT map unknown security/policy states to "allowed".

## Renames and aliases

Renaming a field/contract is not silently handled through permanent ambiguous aliases.

Migration may temporarily support old/new fields only under an explicit deterministic profile that prevents:

- both fields with conflicting values;
- first/last parser differences;
- different producer/consumer interpretations.

Prefer additive new version + controlled deprecation over indefinite alias ambiguity.

## Semantic immutability of historical events

A published historical event keeps the meaning of its original contract version.

New code SHALL NOT reinterpret an old event according to current business rules when those rules did not exist at occurrence time.

Upcasters/adapters may transform representation for current code, but must preserve historical semantic meaning and retain traceability to original contract/version.

## Upcasting

An upcaster is allowed only when:

- deterministic;
- version-to-version mapping is reviewed/tested;
- does not require unavailable current mutable state unless the replay contract explicitly permits reconciliation;
- does not fabricate a historical fact that was not represented by the source message;
- preserves tenant/source/message identity and occurrence semantics as required;
- does not bypass data-classification/erasure restrictions.

Upcasting code/version is part of supported replay compatibility evidence.

## Producer/consumer deployment skew

Contracts must support rolling deployment where:

```text
new producer -> old compatible consumer
old producer -> new compatible consumer
```

within the supported compatibility window.

Release gating tests these combinations for security/correctness-sensitive contracts rather than assuming simultaneous deployment.

A change that requires all consumers to deploy atomically is a distribution coupling signal and normally requires a versioned migration strategy.

## Multi-version publication

A producer MAY temporarily publish multiple contract versions during migration only when:

- the owning fact is not duplicated into multiple business effects accidentally;
- consumer routing/subscription is explicit;
- event identities/causation preserve traceability;
- dual-publish duration is bounded;
- retirement criteria are measured;
- recovery/replay semantics for both versions are defined.

Dual publication is a migration mechanism, not permanent architecture by default.

## Consumer version ranges

A consumer declares exactly which contract versions it accepts.

"Latest" is not a stable compatibility policy.

Unsupported versions fail into a governed compatibility/quarantine path rather than being parsed optimistically.

## Realtime protocol compatibility

Realtime `protocol_version` evolves separately from event/projection `contract_version`.

Within realtime protocol major 1:

- additive optional protocol fields are allowed when clients tolerate them;
- existing message-type semantics remain stable;
- a domain projection contract may evolve without changing protocol major;
- a transport/protocol semantic break requires protocol major/negotiation change.

Phase 09 admission authority semantics are not weakened by any protocol version.

## Webhook compatibility

Outbound webhook contract/version is an explicitly external compatibility surface.

Before Product exposes one, it defines:

- supported versions;
- deprecation notice/support period;
- subscriber migration/observability;
- signature profile compatibility;
- retry/ordering semantics.

An internal integration-event change does not automatically break external webhooks when the projection adapter preserves webhook semantics.

## Schema registry

A schema registry/catalog MAY store machine-readable contract artifacts.

Required properties:

- authenticated/authorized publication;
- immutable version history or governed replacement rules;
- contract-name/version uniqueness;
- provenance to reviewed source;
- compatibility checks;
- availability/recovery appropriate to runtime use;
- no untrusted message-provided schema URL/code loading;
- old schema retention matching supported replay history.

Registry vendor/product remains OPEN.

## Contract catalog

The platform maintains a discoverable catalog of implemented contracts.

Catalog metadata includes:

- owner;
- message class;
- current/supported versions;
- data classification;
- producer(s);
- consumer(s) where governed/discoverable;
- deprecation state;
- replay/retention class;
- links to schema/tests/docs.

The catalog does **not** create Product requirements. An event appears only after an accepted owning use case exists.

## Async contract template

Every new contract document/manifest answers:

### Identity

```text
Contract name:
Version:
Message class:
Owning producer capability:
Tenant/global scope:
Message identity policy:
Trusted message identity scope:
Producer/source generation policy:
Subject identity:
```

### Payload

```text
Payload schema:
Required/optional fields:
Open/closed enums:
Bounds:
Data classification:
Secret handling:
```

### Publication

```text
Authoritative trigger/fact:
Outbox/transaction boundary:
Occurrence/created time semantics:
Correlation/causation:
```

### Delivery

```text
At-least-once/exact proof class:
Ack durable-responsibility boundary:
Retry classes/backoff profile:
Quarantine/terminal behavior:
```

### Consumer correctness

```text
Consumer contract(s):
Inbox/idempotency/effect mechanism:
Local vs cross-authority completion:
External ambiguity/reconciliation:
Current placement:
Current authorization:
```

### Ordering/replay

```text
Ordering profile/scope:
Sequence/gap behavior:
Replay eligibility:
Replay identity behavior:
Projection rebuild behavior:
```

### Recovery/retention

```text
Dedup retention/recovery horizon:
(R,F] continuity evidence:
Restore/PITR behavior:
Schema/history retention:
```

### Projections

```text
Realtime projection:
Outbound webhook projection:
Other read-model/integration projections:
```

### Governance

```text
Observability:
Audit:
Compatibility class:
Deprecation policy:
OPEN decisions:
Required tests/fault vectors:
```

## Review gate

A new/changed async contract cannot ship merely because a schema compiler passes.

Review compares:

- semantic manifest;
- payload/envelope schema;
- producer/consumer ownership;
- tenant/security/data classification;
- delivery/ack/retry/quarantine;
- inbox/effect completion;
- ordering/replay;
- recovery/retention;
- realtime/webhook external implications;
- deployment skew and service extraction.

## Security-sensitive semantic changes

The following trigger security/correctness review even if payload schema is unchanged:

- producer authority/ACL namespace;
- tenant/global scope;
- message identity scope;
- producer generation policy;
- consumer inbox/idempotency policy;
- ack durable boundary;
- retry classification/ambiguity handling;
- quarantine/re-drive behavior;
- ordering/gap semantics;
- replay identity/target behavior;
- current authorization/placement execution rules;
- retention/recovery continuity;
- data classification/logging;
- webhook disclosure/signing/destination policy;
- realtime subscription/protocol behavior that could affect protected delivery.

## CI requirements

CI/release tooling SHOULD eventually provide:

- schema validation;
- semantic-manifest completeness;
- compatibility diff;
- duplicate/alias parser tests;
- old/new producer-consumer fixture tests;
- envelope authority tests;
- replay fixture tests;
- consumer idempotency/fault tests;
- data-classification/secret linting;
- contract/catalog consistency;
- version uniqueness/provenance.

Exact tooling remains OPEN; release evidence does not.

## Deprecation

Deprecation is measured and governed.

A contract/version is retired only when:

- no supported producer still emits it, or migration adapter exists;
- no supported consumer requires it;
- retained replay history is either still readable through retained reader/upcaster or no longer supported/retained under accepted policy;
- realtime/webhook external subscribers have completed required migration where applicable;
- observability proves retirement eligibility;
- removal does not break recovery/legal/audit requirements.

## Removing fields/contracts

Removing an event field/version does not retroactively remove it from historical retained messages.

Consumers/replay tools must still be able to interpret supported history according to retention policy.

## No accidental topology contracts

Compatibility tests reject contracts that expose or depend on:

- broker topic/partition as semantic ID;
- cell/database/shard ID in payload;
- provider-native schema as platform contract;
- worker/service hostname as producer identity;
- broker offsets as public replay IDs unless explicitly accepted.

## Required governance tests

- additive optional field is tolerated by old compatible consumer;
- new consumer reads old supported message;
- closed enum change is detected as incompatible;
- same schema but changed tenant/idempotency/ack/replay policy is detected by manifest diff;
- unsupported version quarantines rather than guesses;
- historical upcast preserves message/tenant/occurrence meaning;
- schema registry cannot be poisoned by untrusted message schema URL;
- dual-publish migration does not duplicate protected consumer effect;
- replay of old version remains interpretable throughout supported retention;
- event contract does not change merely because service/broker topology changes.

## Intentionally OPEN

- exact version string syntax beyond stable contract identity;
- schema language/registry product;
- code-generation tooling;
- compatibility-diff implementation;
- catalog UI/product;
- deprecation duration values;
- exact dual-publish mechanics.

The semantic-manifest completeness, historical meaning, compatibility and governance properties are fixed.
