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

`boundary-inventory.json` independently pins the four expected broker-facing paths, D4 code roots, consumer-discovery root, registration entrypoint and the only native-transport allowlisted class: `KafkaCandidateAdapter`. `validate_repository_boundary.py` independently pins those values again, mechanically discovers every direct **and indirect** `BrokerFacingPath` descendant across governed Python sources, and propagates descendant identity through imported aliases plus assignment and annotated-assignment aliases. Declaration collection walks the complete Python AST rather than only module-level statements, so the same rules apply inside executable conditional/feature-gate blocks and other nested statement scopes. Chained assignment propagates every simple name target as well, so forms such as `Base = Alias = OutboxDispatchPath` cannot hide a descendant.

Discovered declarations are retained with a distinct declaration identity that includes source location instead of being keyed only by file plus unqualified class name. Same-name descendants in separate nested scopes therefore remain separate records and increase multiplicity; they cannot overwrite one another or replace an expected top-level declaration. Exact inventory equality **and declaration multiplicity** are required.

The no-Kafka-business-authority scan walks the local assurance dependency closure **transitively** from the broker boundary, durable effect verifier and consumer-registration guard. Complete local module paths are resolved, including nested subpackages and relative imports. For every resolved nested module, every existing parent-package `__init__.py` that Python executes on the import path is also included in the scanned closure, so executable package initialization cannot carry hidden broker or transaction authority.

`broker_boundary.py` is protected by two layers. The repository validator scans the boundary surface, and the independent structural guard `validate_structural_boundary_guards.py` requires the native exception to bind to **exactly one top-level lexical declaration** named `KafkaCandidateAdapter`. A second top-level declaration with that name, a nested declaration with that name, or any ambiguity in the exemption fails closed. The allowed adapter body may contain candidate-native mechanics, but every nested class inside it is treated as a separate lexical declaration and remains scanned. `AlternateStubTransport`, broker paths, helpers, module-level code and all other classes therefore remain inside the native Kafka/transaction prohibition.

Native Kafka SDK usage and Kafka transaction APIs including initialization, begin, commit, abort and send-offsets-to-transaction are rejected across that closure and across every governed source language in `CODE_SUFFIXES`. Python AST attribute detection and non-Python member detection share the same case-and-underscore normalization, so snake_case, camelCase and PascalCase spellings such as `init_transactions`, `initTransactions`, `commit_transaction`, `commitTransaction`, `CommitTransaction`, `send_offsets_to_transaction`, `sendOffsetsToTransaction` and `SendOffsetsToTransaction` map to the same prohibited transaction authority. Non-Python scanning does not require `(` to immediately follow the member name, so language-specific generic/turbofish forms such as Rust `commit_transaction::<()>()` and TypeScript `commitTransaction<Result>()` are also rejected. Detection remains owner-name independent.

The logical path call graph is deliberately narrow:

- outbox -> `BrokerPort.publish`;
- consumer receive -> `BrokerPort.receive`;
- inbox acknowledgement -> durable verifier, **then** `BrokerPort.acknowledge`;
- replay -> `BrokerPort.publish`.

The ordered call-set check remains a useful secondary signal, but the verify-before-ack claim no longer depends on lexical source order. The independent structural guard requires `InboxAcknowledgePath.acknowledge_after_durable_responsibility` to be a linear two-statement authority path: unconditional `_verifier.assert_durable(receipt)` followed by `_broker.acknowledge(...)`. Additional branches, `try` blocks, loops, early-return paths, broker-first order, or conditional verification are rejected. This establishes structural dominance for the currently governed source shape instead of assuming that an earlier line dominates a later call.

Negative controls explicitly falsify the two historical escapes: duplicate/nested allowlisted adapter declarations are rejected, and a conditional verifier such as `if receipt.receipt_id != "escape": assert_durable(...)` followed by broker acknowledgement is rejected even though its textual call order appears correct. A broker-first variant is rejected as well. Separately, a matching-semantics forged-receipt runtime control proves that a receipt absent from durable state cannot remove the queued delivery.

A logical path cannot call an imported helper, physical-metadata alias, or extra dependency without violating the exact call-graph proof. Constructors are included in that closure.

## Logical message and physical-record separation

The shared `LogicalMessage` carries `contract_name` and `contract_version` as separate canonical fields together with message identity, trusted scope and payload. The Kafka-shaped candidate no longer stores the original logical object as its queue representation: publish encodes a Kafka-shaped physical record and receive reconstructs a new logical message from canonical record headers plus payload.

The transport-swap transcript compares contract name and contract version independently for initial delivery and replay. Negative controls prove that payload corruption and contract-version corruption change the transcript. A reconstruction probe also requires the candidate to return an equal-but-distinct logical object, preventing the source harness from passing by simply handing the original object back through an in-memory queue.

Topic/partition/offset/group data remain physical adapter metadata; they are not canonical message identity or business authority.

## Durable business-effect authority

`effect_protection.py` implements `SQLiteAtomicInboxEffectGuard`, an executable atomic-local guard. In one durable SQLite transaction it records trusted inbox identity and applies the protected business effect. It returns a `DurableResponsibilityReceipt` only after commit.

The replay-equivalence surface is immutable across `(consumer_contract, message_identity_scope, message_id)`: the retained durable state also binds `contract_name`, `contract_version` and a digest over contract name, version and payload. Reuse of the same scoped identity with changed contract metadata or payload fails closed instead of being treated as an ordinary duplicate.

Broker acknowledgement no longer accepts a caller boolean. `InboxAcknowledgePath` requires a receipt and asks the durable guard to re-open/verify committed inbox + effect + receipt state before acknowledging the broker. The broker acknowledgement then independently binds the receipt to the **currently delivered immutable semantics**: consumer contract, trusted scope, message ID, contract name, contract version and semantic digest must all match the queued delivery. A genuine historical receipt therefore cannot remove a later same-identity delivery whose contract version or payload changed. Cross-consumer and cross-scope receipts are likewise rejected, and the unmatched broker message remains available.

The semantic transport-swap transcript performs and observes this real protected effect. It compares delivery/replay contract and version, message identity, tenant scope, payload, publication acceptance, durable effect payload/digest, effect application count and durable receipts. Replay of the same logical identity is deduplicated: the protected effect remains applied exactly once. Kafka-shaped transport progress or transactions are therefore not used as business-effect truth.

A corrupting alternate adapter is a negative control and must diverge from the Kafka-shaped logical transcript.

## Executable consumer-registration binding

Every JSON consumer declaration anywhere under the governed `implementation` discovery root is recursively discovered, including partial Kafka-shaped declarations that omit `consumer_contract`. Governed JSON is parsed **fail closed**: malformed syntax or invalid UTF-8 raises a gate failure instead of being silently skipped as a non-consumer. In addition, path provenance is authoritative for governed registry locations: **every** JSON file beneath a `consumer-registry/` or `consumer_registry/` directory is treated as a consumer manifest even if only one declaration field survived. A partial file such as `consumer-registry/partial.json` containing only `{"topic":"unprotected"}` is therefore sent to required-field validation and rejected rather than disappearing behind declaration heuristics. Every discovered consumer must traverse `register_consumer -> issue_registration_permit -> register_validated`.

The manifest cannot merely claim `atomic_local`. Its effect-protection declaration must bind exactly to the executable `SQLiteAtomicInboxEffectGuard` and its `sqlite_atomic_inbox_effect_v1` contract. Unknown/fake implementations and Kafka-EOS-only bindings are rejected. `consumer_contract` is validated with the canonical async contract-name grammar, while `topic` must satisfy its separate stable Kafka-compatible identifier grammar.

The registration sink accepts only a typed permit whose unique issuance is recorded by successful validation; directly constructed typed permits are rejected. This remains an evidence registration sink because production Kafka authority is absent. The claim is that the current governed D4 registration surface is mechanically gated, not that production topics have been created.

## Exact source-run provenance

The repository manifest no longer accepts SHA/run/job placeholders as evidence provenance. It declares `runtime_resolved_artifact_required` and an exact required-field schema.

After all source probes, Phase 10 regressions and non-promotion checks pass, the workflow queries GitHub Actions for the current numeric job ID and emits a resolved provenance record containing:

- exact 40-hex analyzed repository SHA;
- workflow run ID and run attempt;
- numeric job ID and job name;
- exact probe path;
- SHA-256 of the source-evidence manifest;
- exact evidence IDs/kinds;
- non-credit and promotion-rule boundary.

That record is persisted as a GitHub Actions artifact using a SHA-pinned `actions/upload-artifact` action. A later ledger-promotion PR must cite/review this exact source run; a green current run still cannot credit itself.

## Exit condition

The package is source-evidence-ready only after exact-HEAD CI and fresh adversarial review prove current-namespace discovery, distinct same-name nested declaration accounting, multi-target-assignment-alias-aware direct/indirect broker-path inheritance discovery, **single-top-level-lexical-declaration** native allowlisting limited to `KafkaCandidateAdapter` with nested classes still scanned, executable transitive assurance closure including parent-package initializers, owner-independent polyglot Kafka transaction-API rejection including transaction initialization plus snake/camel/Pascal and language-specific generic syntax normalization, exact logical call-graph closure plus **structural unconditional dominance** of durable verification over acknowledgement, canonical versioned record reconstruction, durable effect/ack boundary, fail-closed governed consumer-registry path validation, executable registration binding, semantic payload/effect equivalence and resolved source-run provenance. Merge of this PR still credits **0/7** D4-A evidence.