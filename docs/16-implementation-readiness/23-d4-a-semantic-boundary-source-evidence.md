# D4-A Source Evidence — Semantic Broker Boundary and Consumer Registration Gate

**Status:** source-evidence harness candidate; no ledger credit; no Kafka selection; no D4/Wave 4/Product/production/C3 authority  
**Canonical base:** `main@c4613a30050b6a3a987a73af39f224e152b72fa5`

## Scope

This package implements the first executable D4-A source-evidence harness for exactly:

- `broker_neutral_anti_corruption_stub_swap`
- `exactly_once_guardrail_consumer_inbox_enforcement`

It does **not** claim a live Kafka broker run, capacity, ordering/partition, outage/recovery, ledger credit, candidate selection, or implementation/production authority.

## Complete current D4 broker-boundary discovery

The proof is explicitly bounded to the **currently governed D4 implementation namespace**. Product/runtime transport authority does not yet exist.

`boundary-inventory.json` independently pins the four expected broker-facing paths, D4 code roots, consumer-discovery root, registration entrypoint and the only native-transport allowlisted class: `KafkaCandidateAdapter`. `validate_repository_boundary.py` mechanically discovers direct and indirect `BrokerFacingPath` descendants across governed Python sources. `validate_structural_boundary_guards.py` independently rechecks lexical native-adapter boundaries, acknowledgement authority and historical alias/destructuring escape classes.

A third independent guard, `validate_lexical_reflection_and_hierarchy.py`, now owns the declaration-time/lexical closure that cannot safely be represented by a final file-wide alias map. It evaluates statically known base/sequence bindings in source order and at each class declaration. Therefore a later reassignment cannot rewrite the evidence for an earlier class. Ordinary sequence assignments such as `Bases = (OutboxDispatchPath,)`, copied aliases such as `Alias = Bases`, target-side starred capture such as `*Bases, = (OutboxDispatchPath,)`, and their later expansion in `class EscapingPath(*Bases)` / `class EscapingPath(*Alias)` are resolved at the declaration where Python consumes them. These descendants increase inventory multiplicity and fail the exact four-path gate.

If a starred class base cannot be established statically — for example `Bases = choose_bases(); class EscapingPath(*Bases)` — the source-evidence proof fails closed. It does not silently assume that the unresolved sequence is outside the governed broker hierarchy.

Declaration discovery retains source-location identity and walks nested executable scopes. Same-name descendants in distinct scopes remain distinct records. Exact inventory equality **and declaration multiplicity** are required.

The no-Kafka-business-authority scan walks the local assurance dependency closure **transitively** from the broker boundary, durable effect verifier and consumer-registration guard. Complete local module paths are resolved, including nested subpackages, relative imports and executable parent-package `__init__.py` files.

`broker_boundary.py` is protected by layered checks. The native exception must bind to exactly one top-level lexical declaration named `KafkaCandidateAdapter`. Only direct executable bodies of its direct methods may contain candidate-native mechanics; class-body execution, decorators, defaults, annotations, bases, keywords, type-parameter expressions and nested lexical declarations remain governed.

## Lexical reflection and native transaction authority

Dynamic transaction-member resolution is treated as an executable authority surface, but ordinary reflection is not prohibited merely because it exists. The guards detect direct attributes and constant/computed reflective transaction names, imported or qualified builtin access, and aliases that preserve reflective authority.

The lexical guard additionally propagates **reflected callable results**. Thus `transaction = getattr(client, transaction_name); transaction()` is rejected even though the reflective lookup and invocation occur in separate statements. Equivalent namespace-map forms are covered through literal, imported, qualified and assigned `vars` surfaces, including `builtins.vars(client)[transaction_name]()`, `from builtins import vars as namespace; namespace(client)[transaction_name]()` and `namespace = vars(client); namespace[transaction_name]()`.

Fail-closed handling applies when an unresolved reflected member is actually consumed as callable authority. A benign read such as `value = getattr(record, field_name)` is not automatically classified as a Kafka transaction. Conversely, unresolved reflected call-through remains forbidden because the source proof cannot establish that the runtime member is not `commitTransaction` or another prohibited transaction API.

Reflective builtin identity is lexical and order-aware in the independent guard. Function parameters, local definitions, imports and rebinding can shadow spellings such as `getattr`; a locally defined non-builtin `getattr` is not permanently treated as Python's reflective builtin. This prevents the fail-closed control from turning ordinary application helpers into false Kafka findings while preserving the actual builtin/alias attack surface.

Native Kafka SDK usage and Kafka transaction APIs including initialization, begin, commit, abort and send-offsets-to-transaction remain rejected across the governed closure and every source language in `CODE_SUFFIXES`. Transaction matching remains owner-name independent and normalized across snake/camel/Pascal spellings and supported generic/turbofish call syntax.

## Acknowledgement authority and hierarchy immutability

The logical path call graph remains deliberately narrow:

- outbox -> `BrokerPort.publish`;
- consumer receive -> `BrokerPort.receive`;
- inbox acknowledgement -> durable verifier, **then** `BrokerPort.acknowledge`;
- replay -> `BrokerPort.publish`.

`InboxAcknowledgePath.acknowledge_after_durable_responsibility` must remain a synchronous, undecorated, linear two-statement authority path with unconditional durable verification before broker acknowledgement. The complete lookup hierarchy is constrained: `InboxAcknowledgePath` inherits directly and only from inert `BrokerFacingPath`, and replacement-capable decorators, metaclasses, descriptors, lookup hooks and class-body rebinding are rejected.

Post-declaration namespace mutation is also governed. Direct attribute assignment/deletion, aliases/imported/qualified `setattr`/`delattr`, class-symbol aliases and `type.__setattr__`/`type.__delattr__` cannot replace the acknowledgement entrypoint or protected lookup hooks. **`__bases__` is explicitly part of the protected authority surface**: direct or reflective base replacement fails closed, so a later `EvilBase` cannot inject a replacement `__getattribute__` while leaving the reviewed verify-before-ack method text unchanged.

Negative controls cover conditional/broker-first ack paths, decorated or metaclass-replaced entrypoints, inherited lookup hooks, post-declaration mutation and base replacement. A matching-semantics forged-receipt runtime control separately proves that a receipt absent from durable state cannot remove the queued delivery.

## Logical message and physical-record separation

The shared `LogicalMessage` carries `contract_name` and `contract_version` separately together with message identity, trusted scope and payload. The Kafka-shaped candidate encodes a physical record and reconstructs a new logical message instead of returning the original logical object.

The transport-swap transcript compares contract/version, identity, trusted scope, payload and publication acceptance across delivery/replay. Negative controls prove payload/version corruption diverges, and a reconstruction probe requires an equal-but-distinct logical object.

Topic/partition/offset/group data remain physical adapter metadata; they are not canonical message identity or business authority.

## Durable business-effect authority

`effect_protection.py` implements `SQLiteAtomicInboxEffectGuard`. In one durable SQLite transaction it records trusted inbox identity and applies the protected business effect, returning `DurableResponsibilityReceipt` only after commit.

The immutable replay-equivalence surface is `(consumer_contract, message_identity_scope, message_id)` plus retained `contract_name`, `contract_version` and semantic digest. Reuse with changed contract metadata or payload fails closed.

Broker acknowledgement requires a durable receipt and then independently binds that receipt to the currently delivered consumer contract, trusted scope, message ID, contract name/version and semantic digest. Historical, cross-consumer, cross-scope or semantically conflicting receipts cannot remove the current delivery.

The semantic transport-swap transcript performs and observes the protected effect and proves duplicate replay applies the business effect once. Kafka-shaped transport progress or transactions are not business-effect truth.

## Executable consumer-registration binding

Every governed JSON consumer declaration under `implementation` is recursively discovered, including partial declarations. Governed malformed JSON/UTF-8 fails closed, and every JSON beneath `consumer-registry/` or `consumer_registry/` is treated as a manifest even when required fields are missing. Every discovered consumer traverses `register_consumer -> issue_registration_permit -> register_validated`.

Effect protection must bind to the executable `SQLiteAtomicInboxEffectGuard` / `sqlite_atomic_inbox_effect_v1` contract rather than merely claiming a label. Consumer contracts use the canonical async naming grammar; topics use their separate stable identifier grammar. The sink accepts only permits recorded as issued by successful validation; directly constructed typed permits are rejected.

This remains an evidence registration sink because production Kafka authority is absent. It proves the currently governed D4 registration surface, not production topic creation.

## Exact source-run provenance

The source manifest requires runtime-resolved provenance. After source probes, regressions and non-promotion checks pass, the workflow emits a resolved artifact containing the exact analyzed 40-hex SHA, workflow run/attempt, numeric job identity, probe path, source-manifest digest, exact evidence IDs/kinds and non-credit/promotion boundary.

A later ledger-promotion PR must cite/review that exact source run. A green source run cannot credit itself.

## Exit condition

The package is source-evidence-ready only after exact-HEAD CI and fresh adversarial review prove: complete current-namespace broker-path discovery; declaration-time, order/scoped static sequence and starred-base resolution with ordinary/copy aliases and unresolved-starred fail-closed behavior; a single lexical native-adapter exception limited to direct method bodies; executable transitive assurance closure; owner-independent native transaction rejection; lexical/order-aware reflection with callable-result and `vars`-mapping alias propagation but correct builtin shadowing; complete non-replaceable acknowledgement lookup hierarchy including post-declaration **`__bases__`** protection; canonical versioned record reconstruction; durable effect/ack binding; fail-closed governed consumer registration; semantic payload/effect equivalence; and resolved source-run provenance.

Merge of this PR still credits **0/7** D4-A evidence. Kafka remains unselected, and D4 transport/Product/Wave 4/production/C3 authority remains ungranted/unselected.