# D4-C OPEN-EVT-008 source evidence — ack / lease / checkpoint

Status: **source evidence only; no ledger credit; no selection**.

Canonical base: `main@c0b061eb3f9e42f63b9f4c05e7b8b2d2de75a987`.

## Scope

This package evaluates the first D4-C axis bound to `OPEN-EVT-008` and evidence obligation `ack_after_durable_responsibility_and_lease_ambiguity`.

The three concrete candidate classes admitted by the accepted D4-C candidate-evaluation plan are exercised against one platform-owned responsibility/fencing model backed by SQLite with `synchronous=FULL` for restart-survival probes:

- `durable_inbox_claim_then_broker_ack_profile`;
- `broker_visibility_lease_plus_durable_receipt_profile`;
- `database_owned_work_claim_plus_broker_checkpoint_profile`.

All three may reach only `eligible_for_evidence_execution`. `equivalent_reviewed_profile` remains `insufficient_evidence` until a concrete reviewed equivalent exists.

SQLite is an evidence fixture here, not a selected production store or schema.

## Fixed semantics proved

The executable harness and falsification suite require all of the following:

1. ack/checkpoint never precedes durable consumer responsibility;
2. lease/visibility expiry is ambiguity, not proof that an effect did not happen;
3. broker progress is never business-effect truth;
4. redelivery/rewind remains safe through durable inbox/effect idempotency;
5. scoped identity alone is insufficient after rewind: durable content-equivalence authority is required;
6. same scoped identity with conflicting immutable content fails closed as integrity failure;
7. the evidence fixture compares immutable **envelope + payload** semantics, and independently rejects envelope drift and payload drift under the same scoped ID;
8. ownership/takeover is fenced so a stale worker cannot execute an effect after takeover;
9. takeover after expiry requires a **strictly newer fence epoch** and cannot reuse the expired epoch;
10. a higher epoch cannot steal a still-unexpired claim by implication;
11. crashes between durable responsibility/effect and broker progress recover without semantic loss or repeated business effect.

The reference state machine deliberately keeps broker ack/checkpoint state subordinate to platform durable receipt/equivalence/effect truth. This prevents Kafka, a future broker, or a broker-native visibility/DLQ primitive from becoming business-effect authority by implication.

The harness uses canonicalized JSON plus SHA-256 only as a deterministic **test comparison fixture**. It does **not** select the production content-equivalence mechanism, hash/MAC, canonicalization profile, storage representation or historical verifier governed by `OPEN-EVT-011`.

## Crash and ambiguity controls

The source harness separately exercises:

- durable responsibility with broker progress but no effect, proving progress is not effect truth;
- rejection of a higher-epoch claim while the current lease remains valid;
- lease expiry after a completed effect, followed by equivalent redelivery and a strictly higher fenced takeover, proving exactly one business effect;
- rejection of a same-epoch takeover after expiry;
- process close/reopen after durable responsibility but before effect/progress, proving receipt, equivalence and fence state survive restart before safe takeover and completion;
- process close/reopen after effect completion but before broker progress, proving effect truth and count survive restart and redelivery becomes an idempotent no-op;
- missing historical content-equivalence authority after close/reopen, which remains uncertainty and fails closed;
- conflicting same-ID/different-envelope and same-ID/different-payload redelivery, both of which fail closed;
- stale-owner effect execution after takeover, which is fenced.

These probes prove logical/process restart continuity of the accepted semantics. They do not select a production database durability model, filesystem, replication topology, timeout, lease duration or failover product.

## Source-run provenance

The exact-HEAD workflow emits an immutable source artifact containing:

- exact repository SHA;
- workflow run ID and attempt;
- exact resolved job ID/name;
- candidate results and their SHA-256;
- source decision/evidence binding;
- exact required-proof, source-assertion and non-authority inventories;
- SHA-256 digests for the source manifest, evaluator, validator, falsification suite, provenance emitter, readiness record and workflow itself.

The artifact is retained as source evidence only. Its existence or digest grants no ledger credit or selection.

## Governance boundary

This PR is intentionally **source evidence only**:

- D4-C remains `not_selected`;
- D4-C remains `0/9` credited evidence;
- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- the OPEN-EVT-011 content-equivalence profile remains `not_selected`;
- no candidate, timeout, lease duration, broker-specific ack API, checkpoint topology, production database schema, persistence product, comparison algorithm/profile, or numeric production setting is selected;
- D4-D remains `0/5`, open and unselected;
- D4-wide remains `12/26`;
- D4 remains `scoped`;
- D4 transport authority remains `selected_not_granted`;
- Product/Wave4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

A green source run is not a ledger promotion. Any D4-C credit requires a later, separately reviewed promotion transition pinned to the exact reviewed source HEAD/run/job/artifact.
