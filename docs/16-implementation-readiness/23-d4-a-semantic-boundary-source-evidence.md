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

`boundary-inventory.json` independently pins the four expected broker-facing paths, D4 code roots, consumer-discovery root and registration entrypoint. `validate_repository_boundary.py` independently pins those values again, mechanically discovers every direct **and indirect** `BrokerFacingPath` descendant across governed Python sources, and propagates descendant identity through imported aliases plus simple assignment and annotated-assignment aliases. Declaration collection walks the complete Python AST rather than only module-level statements, so the same rules apply inside executable conditional/feature-gate blocks and other nested statement scopes. This includes chains such as `from broker_boundary import OutboxDispatchPath as Base`, `Base = OutboxDispatchPath`, `Alias2: object = Base`, and a `ConditionalPath` declared beneath an `if` guard. Exact inventory equality/multiplicity is required, governed implementation code is scanned for direct Kafka SDK/native bypass, and the exact dependency call graph of every logical path is pinned.

The no-Kafka-business-authority scan walks the local assurance dependency closure **transitively** from the durable effect verifier and consumer-registration guard. Complete local module paths are resolved, including nested subpackages and relative imports. For every resolved nested module, every existing parent-package `__init__.py` that Python executes on the import path is also included in the scanned closure, so executable package initialization cannot carry hidden broker or transaction authority. A helper such as `helpers.guard`, its package initializer, and deeper imported helpers are therefore all scanned automatically.

Native Kafka SDK usage and Kafka transaction APIs such as begin/commit/abort/send-offsets-to-transaction are rejected across that closure and across every governed source language in `CODE_SUFFIXES`. Python AST attribute detection and non-Python member-call detection now share the same case-and-underscore normalization, so snake_case, camelCase and PascalCase spellings such as `commit_transaction`, `commitTransaction`, `CommitTransaction`, `send_offsets_to_transaction`, `sendOffsetsToTransaction` and `SendOffsetsToTransaction` map to the same prohibited transaction authority. Detection remains owner-name independent, so aliasing an injected client as `client`, `transport`, `session`, or another arbitrary variable cannot hide those APIs.

The logical path call graph is deliberately narrow:

- outbox -> `BrokerPort.publish`;
- consumer receive -> `BrokerPort.receive`;
- inbox acknowledgement -> durable verifier, then `BrokerPort.acknowledge`;
- replay -> `BrokerPort.publish`.

A logical path cannot call an imported helper, physical-metadata alias, or extra dependency without violating the exact call-graph proof. Constructors are included in that closure. This closes the earlier substring-only dependency escape.

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

Every JSON consumer declaration anywhere under the governed `implementation` discovery root is recursively discovered, including partial Kafka-shaped declarations that omit `consumer_contract`. Governed JSON is parsed **fail closed**: malformed syntax or invalid UTF-8 raises a gate failure instead of being silently skipped as a non-consumer. Every discovered consumer must traverse `register_consumer -> issue_registration_permit -> register_validated`.

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

The package is source-evidence-ready only after exact-HEAD CI and fresh adversarial review prove current-namespace discovery, nested-scope import/assignment-alias-aware direct/indirect broker-path inheritance discovery, executable transitive assurance closure including parent-package initializers, owner-independent polyglot Kafka transaction-API rejection with shared snake/camel/Pascal-case normalization including Python, exact logical call-graph closure, canonical versioned record reconstruction, durable effect/ack boundary, executable registration binding, semantic payload/effect equivalence and resolved source-run provenance. Merge of this PR still credits **0/7** D4-A evidence.
