# D4-A Source Evidence — Semantic Broker Boundary and Consumer Registration Gate

**Status:** source-evidence harness candidate; no ledger credit; no Kafka selection; no D4/Wave 4/Product/production/C3 authority  
**Canonical base:** `main@c4613a30050b6a3a987a73af39f224e152b72fa5`

## Scope

This package implements the first executable D4-A source-evidence harness for exactly two planned evidence IDs:

- `broker_neutral_anti_corruption_stub_swap`
- `exactly_once_guardrail_consumer_inbox_enforcement`

It intentionally does **not** claim live Kafka broker evidence. Capacity, ordering/partition and outage/recovery claims remain reserved for later real-candidate evidence packages.

## Complete current D4 broker-boundary discovery

The proof is bounded to the **currently governed D4 implementation namespace**, because product/runtime transport authority has not been granted yet. Within that namespace, coverage is no longer self-declared by the broker module.

`boundary-inventory.json` independently pins the expected broker-facing path IDs/classes, implementation code roots, consumer-discovery root and registration entrypoint. `validate_repository_boundary.py` then mechanically:

- discovers every subclass of `BrokerFacingPath` and requires the discovered set to equal the independently pinned four-path inventory;
- rejects Kafka-native primitives inside every discovered logical path;
- scans governed D4 implementation code for direct Kafka SDK/native bypass outside the evidence adapter boundary;
- recursively discovers every JSON consumer declaration anywhere under `implementation/d4-eventing-async`, rather than trusting one fixture directory;
- requires the canonical registration entrypoint and validated-permit path to exist.

Therefore a new governed D4 path or consumer cannot remain invisible merely because it was omitted from a hand-maintained list or placed in another nested directory. When future product/runtime eventing code is authorized outside this namespace, its code root must be added to the independently pinned inventory before this evidence can be promoted/relied upon for that expanded surface.

## Anti-corruption semantic swap

`broker_boundary.py` defines one logical `BrokerPort`. Kafka-shaped physical metadata exists only in `KafkaCandidateAdapter`; the alternate stub uses different physical concepts. Both adapters execute the same discovered logical path classes.

The semantic transcript compares contract, message identity, tenant scope **and payload** for original delivery and replay. A corrupting alternate transport is a negative control and must produce a different transcript. Replay keeps the original message identity, and broker progress/transactions never become business-effect authority.

This remains a semantic source proof, not evidence that Kafka itself has met capacity, partition-count, recovery or backlog requirements.

## Governed consumer-registration gate

`consumer_registration_gate.py` recursively discovers every consumer declaration under the governed D4 implementation root. Every discovered declaration must traverse `register_consumer`, which first mints a `RegistrationPermit` only after validating:

- stable consumer contract and candidate topic declaration;
- durable inbox ownership;
- trusted dedup identity `(consumer_contract, message_identity_scope, message_id)`;
- a real protected-effect profile: atomic local effect or externally reconciled effect.

The registration sink accepts only a typed validated permit. Negative controls prove direct unvalidated registration is rejected, nested/alternate consumer-manifest locations are still discovered, missing inbox/effect protection is blocked, and Kafka idempotence/transactions cannot bypass rejection.

Because no production Kafka transport authority exists yet, the sink is an evidence sink rather than a live broker administrator. The source claim is that the governed registration boundary is mechanically unavoidable inside the current D4 namespace—not that production topic creation has occurred.

## Source-run / ledger separation

`source-evidence-manifest.json` records the source package while keeping `current_run_auto_credit=false`, `ledger_credit=[]`, Kafka unselected and all D4/Product/Wave4/production/C3 authorities ungranted. A green run is source evidence only; credit requires a separate ledger-promotion PR after exact-run review.

## Exit condition

This PR is source-evidence-ready only after exact-HEAD CI and adversarial review establish complete current-namespace discovery, semantic payload preservation, registration non-bypass and non-authority. Merge still does not credit either evidence slot.
