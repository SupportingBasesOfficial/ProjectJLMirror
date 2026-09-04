# D4-A — Outbox / Backlog Drain / Recovery Source Evidence

**Status:** source-evidence harness only  
**Canonical base:** `main@3f517258cdade3adc55765435cc087f9a8e90c3a`  
**Track:** D4-A  
**Ledger before this source package:** 6/7  

## Purpose

This package produces the final missing D4-A source-evidence class without modifying the governed D4-A ledger.

Evidence ID:

`broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark`

Evidence kind:

`real_candidate_failure_recovery_benchmark`

A green source run is not ledger credit, is not Kafka selection, is not D4 acceptance and grants no Product/Wave 4/production/C3 authority.

## Binding proof obligations

The package must prove all five machine-owned assertions together:

1. committed outbox backlog survives a real broker outage;
2. recovery drains backlog without starving protected/current work;
3. broker-ack ambiguity retries the same committed fact with the same logical `message_id`;
4. broker offset/ack progress is not treated as business-effect truth;
5. bounded test lag/drain values remain test evidence and do not grant C3 production-numeric authority.

These obligations derive from the accepted Phase 10 publication/recovery invariants and the D4-A evidence plan.

## Real outage model

The workflow starts the immutable Kafka 4.3.1 candidate image already used by the accepted Capacity/Ordering evidence package, creates the bounded recovery topic and then executes an actual container stop/start outage.

While Kafka is unavailable, the harness commits outbox rows to a SQLite database configured with WAL + `synchronous=FULL`. The outbox connection is closed and reopened independently of the broker lifecycle. The test fails unless the same committed rows remain pending after database reopen and after Kafka restarts.

SQLite is only the bounded durable truth store used by this evidence harness; this package does not select the production outbox database implementation or claim production topology authority.

## Priority-preserving recovery drain

The recovery profile defines:

- normal recovery-backlog priority;
- higher protected/current-work priority;
- a bounded maximum number of backlog dispatches allowed before newly arriving protected work is admitted;
- finite dispatcher batch controls.

Protected current work is inserted during recovery drain rather than being preloaded before recovery. The harness records the observed backlog-dispatch count before every protected delivery and fails if the configured bound is exceeded. It also requires the complete historical backlog to drain, so protecting new work cannot starve recovery work indefinitely.

The values are bounded C2 test inputs only.

## Broker acknowledgement ambiguity

One committed outbox message is intentionally published successfully while the local dispatcher treats the acknowledgement as ambiguous and leaves the durable outbox row pending.

The next attempt republishes the exact same semantic payload using the same logical `message_id`. The harness fails if another semantic identity is invented.

The broker therefore contains one deliberate duplicate record for one logical message. Consumer admission uses an inbox keyed by logical `message_id`; identical duplicate content is suppressed, while conflicting content under the same ID would fail closed.

This demonstrates at-least-once retry safety. It does not claim Kafka-native exactly-once business semantics.

## Broker progress is not business-effect truth

Before consumer effect admission, the harness reads positive Kafka end-offset progress and separately verifies the business-effect table is still empty.

Only the consumer-side inbox/effect transaction creates business-effect truth. The final result requires:

- positive broker progress before effect admission;
- zero business effects at that point;
- exactly one durable business effect per unique logical message after consumer admission;
- suppression of the deliberate ambiguous duplicate.

An offset, publish acknowledgement or broker receipt therefore cannot satisfy business-effect completion by itself.

## Immutable candidate pin

Candidate test image:

`apache/kafka:4.3.1@sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837`

Linux/amd64 child manifest:

`sha256:ccd1314e47ec76909e01f86308b4dcf2064f19f7c89759234322314b0e319e26`

The workflow verifies both before running the benchmark.

## Negative controls

Static falsification rejects, at minimum:

- mutable Kafka tag substitution;
- synthetic/documentation-only recovery evidence kind;
- source-run auto-credit;
- premature seventh ledger credit;
- removal of recovery from `evidence_remaining`;
- disabling real outage evidence;
- trivial backlog/current-work samples;
- protected priority no stronger than backlog priority;
- unbounded starvation allowance;
- disabling broker-ack ambiguity;
- changing semantic identity on ambiguous retry;
- treating broker progress as business-effect truth;
- removing anti-starvation measurement;
- selecting Kafka or granting production authority.

Runtime validation separately proves that the real broker, durable outbox, drain scheduler and consumer effect boundary satisfy the expected results.

## Source-run provenance

Every successful source run emits an artifact containing:

- `benchmark-results.json`;
- `resolved-source-run-provenance.json`.

Provenance binds the artifact to:

- exact repository SHA;
- workflow run + attempt;
- exact job identity;
- immutable Kafka index/amd64 digests;
- source-manifest digest;
- recovery-profile digest;
- benchmark-result digest;
- evidence ID/kind;
- explicit zero source ledger credit;
- all non-authority boundaries.

## Non-promotion boundary

This source PR must leave the machine-owned ledger unchanged:

- D4-A stays `six_of_seven`;
- the recovery evidence ID remains in `evidence_remaining`;
- Kafka stays `not_selected`;
- D4 stays `scoped`;
- D4 transport authority stays `not_selected_not_granted`;
- Product/Wave 4 authority stays `not_granted`;
- production authority stays `none`;
- C3 numeric/topology authority stays `not_selected`.

Only a later, separately reviewed ledger-promotion PR may move D4-A from 6/7 to 7/7. Even that ledger completion must not silently select Kafka or accept D4 unless the governing acceptance/decision step explicitly authorizes those transitions.
