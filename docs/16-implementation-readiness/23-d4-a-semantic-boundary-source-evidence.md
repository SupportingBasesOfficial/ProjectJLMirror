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

The current authoritative lexical/control-flow closure is layered. `validate_controlflow_authority_and_bracket_calls_v4_entry.py` first applies the stable imported-base identity patch used by the v4 gate. `validate_controlflow_authority_and_bracket_calls_v4.py` then enforces control-flow-aware reflective authority, definition-time defaults/lambdas, walrus propagation, feasible `try`/`match` state, lexical shadowing, class-base sequence invalidation and non-Python bracket transaction-member checks. Finally, `validate_residual_escape_closure_v5.py` runs **over the patched v4 gate** and closes the residual escape classes found by later adversarial reviews.

Historical guards remain defense-in-depth and regression context, but the workflow does not treat an older lexical guard as the final authority once v4/v5 have superseded its residual surface.

If a starred or computed class base cannot be established safely by the authoritative layered guards, the source-evidence proof fails closed. It does not silently assume an unresolved sequence or expression is outside the governed broker hierarchy.

Declaration discovery retains source-location/lexical evidence across the layered checks and walks nested executable scopes. Exact inventory equality and declaration multiplicity are required; an additional real broker-facing descendant must make the gate fail.

The no-Kafka-business-authority scan walks the local assurance dependency closure transitively from the broker boundary, durable effect verifier and consumer-registration guard. Complete local module paths are resolved, including nested subpackages, relative imports and executable parent-package `__init__.py` files.

`broker_boundary.py` is protected by layered checks. The native exception must bind to exactly one top-level lexical declaration named `KafkaCandidateAdapter`. Only direct executable bodies of its direct methods may contain candidate-native mechanics; class-body execution, decorators, defaults, annotations, bases, keywords and nested lexical declarations remain governed.

## Lexical reflection and native transaction authority

Dynamic transaction-member resolution is treated as executable authority, but ordinary reflection is not prohibited merely because it exists. The guards detect direct attributes, constant/computed reflective transaction names, imported/qualified builtin access and aliases that preserve reflective authority.

The v4 control-flow gate carries potential authority across feasible branches rather than dropping it merely because one continuation shadows a builtin. It handles definition-time defaults and lambda captures, walrus expressions, `try`/handler/else/finally flow, `match` cases, function-parameter invalidation of inherited base sequences, and branch-sensitive base-sequence state.

The v5 residual closure additionally proves, with executable negative controls, that:

- aliases of `type.__setattr__` / `type.__delattr__` remain protected through further call-through aliases;
- starred destructuring cannot hide `vars(...)` authority behind walrus expressions or deterministic tuple/list/dict selections;
- definition-time reflective builtin capture remains visible through deterministic tuple/list/dict keyed selections;
- broker-facing descendants declared in loop/context bodies are inventoried, including statically known `for`/`async for` target aliases;
- computed non-Python bracket transaction members remain detectable when assembled from string fragments, including balanced parenthesized grouping.

Fail-closed handling applies when unresolved reflected member authority is actually consumed as callable authority. A benign ordinary read is not automatically classified as a Kafka transaction, while an unresolved callable path that may select a prohibited transaction API is rejected.

Reflective builtin identity is lexical and order-aware. Function parameters, local definitions, imports and rebinding can shadow spellings such as `getattr`; the protected declaration identity is preserved without making an ordinary local spelling permanently privileged.

Native Kafka SDK usage and Kafka transaction APIs including initialization, begin, commit, abort and send-offsets-to-transaction remain rejected across the governed closure and every source language in `CODE_SUFFIXES`. Transaction matching remains owner-name independent and normalized across snake/camel/Pascal spellings and supported generic/turbofish/bracket call syntax.

## Acknowledgement authority and hierarchy immutability

The logical path call graph remains deliberately narrow:

- outbox -> `BrokerPort.publish`;
- consumer receive -> `BrokerPort.receive`;
- inbox acknowledgement -> durable verifier, **then** `BrokerPort.acknowledge`;
- replay -> `BrokerPort.publish`.

`InboxAcknowledgePath.acknowledge_after_durable_responsibility` must remain a synchronous, undecorated, linear two-statement authority path with unconditional durable verification before broker acknowledgement. The complete lookup hierarchy is constrained: `InboxAcknowledgePath` inherits directly and only from inert `BrokerFacingPath`, and replacement-capable decorators, metaclasses, descriptors, lookup hooks and class-body rebinding are rejected.

Post-declaration namespace mutation is governed. Direct attribute assignment/deletion, aliases/imported/qualified `setattr`/`delattr`, class-symbol aliases and `type.__setattr__`/`type.__delattr__` cannot replace the acknowledgement entrypoint or protected lookup hooks. `__bases__` is explicitly part of the protected authority surface, so a later hierarchy replacement cannot inject an acknowledgement lookup bypass while leaving the reviewed verify-before-ack method text unchanged.

Negative controls cover conditional/broker-first ack paths, decorated or metaclass-replaced entrypoints, inherited lookup hooks, post-declaration mutation and base replacement. A matching-semantics forged-receipt runtime control separately proves that a receipt absent from durable state cannot remove the queued delivery.

## Logical message and physical-record separation

The shared `LogicalMessage` carries `contract_name` and `contract_version` separately together with message identity, trusted scope and payload. The Kafka-shaped candidate encodes a physical record and reconstructs a new logical message instead of returning the original logical object.

The transport-swap transcript compares contract/version, identity, trusted scope, payload and publication acceptance across delivery/replay. Negative controls prove payload/version corruption diverges, and a reconstruction probe requires an equal-but-distinct logical object.

Topic/partition/offset/group data remain physical adapter metadata; they are not canonical message identity or business authority.

## Durable business-effect authority

`effect_protection.py` implements `SQLiteAtomicInboxEffectGuard`. In one durable SQLite transaction it records trusted inbox identity and applies the protected business effect, returning `DurableResponsibilityReceipt` only after commit.

The immutable replay-equivalence surface is `(consumer_contract, message_identity_scope, message_id)` plus retained `contract_name`, `contract_version` and semantic digest. Reuse with changed contract metadata or payload fails closed.

Broker acknowledgement requires a durable receipt and independently binds that receipt to the currently delivered consumer contract, trusted scope, message ID, contract name/version and semantic digest. Historical, cross-consumer, cross-scope or semantically conflicting receipts cannot remove the current delivery.

The semantic transport-swap transcript performs and observes the protected effect and proves duplicate replay applies the business effect once. Kafka-shaped transport progress or transactions are not business-effect truth.

## Executable consumer-registration binding

Every governed JSON consumer declaration under `implementation` is recursively discovered, including partial declarations. Governed malformed JSON/UTF-8 fails closed, and every JSON beneath `consumer-registry/` or `consumer_registry/` is treated as a manifest even when required fields are missing. Every discovered consumer traverses `register_consumer -> issue_registration_permit -> register_validated`.

Effect protection must bind to the executable `SQLiteAtomicInboxEffectGuard` / `sqlite_atomic_inbox_effect_v1` contract rather than merely claiming a label. Consumer contracts use the canonical async naming grammar; topics use their separate stable identifier grammar. The sink accepts only permits recorded as issued by successful validation; directly constructed typed permits are rejected.

This remains an evidence registration sink because production Kafka authority is absent. It proves the currently governed D4 registration surface, not production topic creation.

## Exact source-run provenance

The source manifest requires runtime-resolved provenance. After source probes, regressions and non-promotion checks pass, the workflow emits a resolved artifact containing the exact analyzed 40-hex SHA, workflow run/attempt, numeric job identity, probe path, source-manifest digest, exact evidence IDs/kinds and non-credit/promotion boundary.

A later ledger-promotion PR must cite/review that exact source run. A green source run cannot credit itself.

## Review substitution under tooling unavailability

Fresh adversarial Codex review remains the preferred automated adversarial reviewer when available. If the configured Codex reviewer cannot execute because its usage limit or service availability is exhausted, the gate may be substituted only by an explicitly documented **independent adversarial panoramic review on the exact HEAD**. That substitute must inspect the full PR delta, the authoritative v4-entry/v4/v5 chain, workflow wiring, evidence documentation, recent unresolved findings, non-claims and authority boundaries. It does not permit reuse of an older clean review or resolution of material threads without demonstrating that the exact current HEAD supersedes them.

The substitution is availability-specific; it does not weaken exact-HEAD CI, zero-material-thread, non-promotion or explicit merge-authorization requirements.

## Exit condition

The package is source-evidence-ready only after exact-HEAD CI and an exact-HEAD adversarial review (fresh Codex when available, otherwise the documented independent substitution above) establish: complete current-namespace broker-path discovery; control-flow/lexical reflective authority closure; patched-v4 plus v5 residual escape closure; a single lexical native-adapter exception limited to direct method bodies; executable transitive assurance closure; owner-independent native transaction rejection; complete non-replaceable acknowledgement lookup hierarchy including post-declaration `__bases__` protection; canonical versioned record reconstruction; durable effect/ack binding; fail-closed governed consumer registration; semantic payload/effect equivalence; and resolved source-run provenance.

Merge of this PR still credits **0/7** D4-A evidence. Kafka remains unselected, and D4 transport/Product/Wave 4/production/C3 authority remains ungranted/unselected.
