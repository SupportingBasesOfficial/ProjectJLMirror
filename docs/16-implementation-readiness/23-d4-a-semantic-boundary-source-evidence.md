# D4-A Source Evidence — Semantic Broker Boundary and Consumer Registration Gate

**Status:** source-evidence harness candidate; no ledger credit; no Kafka selection; no D4/Wave 4/Product/production/C3 authority  
**Canonical base:** `main@c4613a30050b6a3a987a73af39f224e152b72fa5`

## Scope

This package implements the first executable D4-A source-evidence harness for exactly two planned evidence IDs:

- `broker_neutral_anti_corruption_stub_swap`
- `exactly_once_guardrail_consumer_inbox_enforcement`

It intentionally does **not** claim live Kafka broker evidence. Capacity, ordering/partition and outage/recovery claims remain reserved for later real-candidate evidence packages.

## Anti-corruption evidence boundary

`tools/assurance/d4a_semantic_boundary/broker_boundary.py` defines one logical `BrokerPort` and four currently actual broker-facing paths in this evidence namespace:

- outbox dispatch;
- consumer receive;
- inbox acknowledgement after durable responsibility;
- replay dispatch preserving original message identity.

The harness requires every registered path class to remain free of Kafka-native topic/partition/offset/group/rebalance/transaction coupling. Kafka-shaped physical metadata exists only inside `KafkaCandidateAdapter`; the alternate stub uses different physical concepts. Both adapters run the same semantic transcript through the same logical path classes and must produce identical logical results.

The negative control injects Kafka-native primitive text into a synthetic path source and proves the mechanical leak detector rejects it.

This is a source boundary proof, not evidence that Kafka itself has met capacity, partition-count, recovery or backlog requirements.

## Consumer registration gate

`tools/assurance/d4a_semantic_boundary/consumer_registration_gate.py` is the actual CI command used before manifests in the D4-A evidence consumer registry can be treated as Kafka-topic registrations.

The gate requires:

- a stable consumer contract;
- Kafka candidate context and a target topic;
- durable inbox ownership;
- trusted dedup identity `(consumer_contract, message_identity_scope, message_id)`;
- a real protected-effect profile: atomic local effect or externally reconciled effect.

The same production-shaped gate path is used for positive and negative controls. Invalid manifests never reach the registrar. Kafka idempotent-producer or transaction flags do not bypass the inbox/effect rejection.

## Source-run / ledger separation

`source-evidence-manifest.json` records the source package and exact evidence kinds while keeping:

- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- Kafka `not_selected`;
- D4 transport authority ungranted;
- Product/Wave4/production/C3 authority ungranted/unselected.

A green run is only source evidence suitable for later review. Crediting either D4-A slot requires a separate ledger-promotion PR after the exact source run is reviewed.

## Falsification requirements

The workflow fails if:

- any registered logical broker path contains Kafka-native primitive coupling;
- Kafka and alternate adapters do not preserve the same logical transcript;
- invalid/no-inbox/no-effect consumers reach topic registration;
- Kafka EOS/transactions bypass the registration gate;
- the source manifest claims live Kafka evidence, benchmark evidence, ledger credit, selection or authority;
- canonical D4-A ledger state is mutated away from 0/7 by this source package.

## Exit condition

This PR may be considered source-evidence-ready only after exact-HEAD CI, panoramic review and fresh adversarial review establish that the harness proves the two declared semantic obligations without overclaiming real Kafka evidence or granting authority. Merge of this source package still does not credit either evidence slot.
