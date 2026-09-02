# D4 — Eventing & Asynchronous Transport C2 Entry Gate

**Status:** scoped evidence gate — no D4 transport, Wave 4, Product implementation or production authority is granted by this record  
**Canonical base:** `main@ee8775fc5e7a25b1c4e166a8bb48b53438f6bd42`  
**Predecessor:** D3 Identity/Security C2 separately accepted and merged by PR #51  
**Scope:** internal eventing/asynchronous transport mechanisms classified C2; production numerics/topology and Product-gated webhook/realtime mechanisms remain outside this gate

## Purpose

D4 closes the replaceable **eventing/asynchronous transport mechanism decisions** that Phase 10 intentionally left OPEN after fixing broker-neutral message semantics, outbox/inbox laws, replay/recovery rules and security boundaries.

D4 exists specifically to prevent a broker SDK, serializer, schema registry, queue topology, DLQ feature, tracing library or deployment default from becoming architecture by implementation-first accident.

D4 is not permission to implement Monitoring/Wave 4, not production eligibility, and not permission to close C3 numerics without evidence.

```text
D3_SEPARATELY_ACCEPTED != D4_TRANSPORT_SELECTED
D4_SCOPED != KAFKA_ACCEPTED
D4_ACCEPTED != WAVE4_IMPLEMENTATION_AUTHORIZED
D4_ACCEPTED != PRODUCTION_AUTHORIZED
C2_MECHANISM != C3_NUMERIC_TOPOLOGY
```

## Canonical predecessor boundary

D3 is accepted at canonical `main@ee8775fc5e7a25b1c4e166a8bb48b53438f6bd42` with D3-A..E in `accepted_candidate` state. That predecessor gives D4 trusted mechanism inputs for human/workload identity, session/replay authority, CSRF/key rotation and cryptographic historical-verifier continuity.

D3 does **not** select any D4 broker, serialization, schema-registry, topic/partition, acknowledgement, quarantine, replay-history or broker-credential mechanism.

## Fixed Phase 10 invariants D4 cannot change

- logical event/message contracts are broker-neutral;
- default delivery is at least once;
- broker exactly-once/transaction features never prove business-effect exactly-once by themselves;
- message identity, tenant identity, producer identity and consumer identity do not depend on physical topic, partition, offset or consumer-group identity;
- required mutation + durable publication responsibility remains atomic or deterministically recoverable under the accepted outbox model;
- acknowledgement/checkpoint follows durable consumer responsibility;
- lease/visibility/timeout expiry never proves protected-effect absence;
- inbox/dedup identity and immutable-content equivalence remain scoped, durable and fail closed on conflict;
- ambiguous external outcomes reconcile before retry eligibility;
- quarantine is canonical platform meaning; broker DLQ alone is not process/recovery truth;
- replay is privileged, audited, bounded and cannot disable protected-effect safety;
- historical semantic meaning and comparison authority remain reproducible for the supported horizon;
- provider/broker/network presence is not trust;
- service/workload authentication does not grant tenant/business authorization;
- trace context is observability only;
- secrets/credentials are prohibited from ordinary message payloads;
- high-volume raw telemetry is not forced through the general event broker;
- recovery/restore/relocation cannot resurrect retired producer, consumer, verifier or effect authority.

## D4 bounded tracks

### D4-A — Broker transport, physical routing and anti-corruption boundary

**Source decisions:** `OPEN-EVT-001`, `OPEN-EVT-005`, `OPEN-REL-012.A`.  
**Leading candidate:** Kafka.  
**Entry state:** `candidate_leading_closure_pending`.

Kafka is a leading candidate only. `OPEN-EVT-001-kafka-decision-record.md` explicitly keeps selection non-canonical until binding closure conditions are satisfied.

D4-A SHALL prove:

1. **Capacity envelope:** Baseline/Growth/Stress evidence exists for the relevant tenant/event/cardinality dimensions before capacity is used to justify selection.
2. **Broker-neutral anti-corruption layer:** outbox/inbox/consumer code depends only on platform logical ports; a stub/alternate transport swap proves Kafka offsets, consumer groups and transactional APIs do not leak into canonical semantics.
3. **Erasure granularity:** `sensitive_or_regulated` payload fields are not retained as raw shared Kafka record-value bytes unless a separately reviewed isolation/retention profile proves governed erasure; the default is opaque reference to governed per-record cryptographic-erasure storage.
4. **Exactly-once guardrail:** tooling rejects consumer registration without real inbox/dedup/effect protection even if Kafka producer idempotence/transactions are enabled.
5. **Ordering/partition ceiling/fallback:** every logical ordering-scope class has a trusted partition-key strategy validated against tenant/device cardinality tiers; a named consumer-side key-level concurrency mechanism serializes only the required logical key scope; evidence benchmarks the maximum practical partition-count ceiling per topic/cluster tier and documents the required tenant-cohort topic-sharding fallback when that ceiling would otherwise be exceeded. The benchmarked ceiling is candidate-conformance evidence, not production partition-count authority.
6. **Physical naming/routing/topology mapping:** concrete topic/subject/queue naming, routing and per-cell/global transport placement are selected behind the adapter boundary, preserve logical contract identity and tenant authorization, and can be replaced without consumer semantic rewrite. Production partition/replica/count numerics remain C3.
7. **Broker-integrated outbox/backlog drain:** the selected broker/outbox/drain mechanism proves priority-preserving, bounded backlog recovery/drain behavior under broker outage/recovery and cannot starve protected/current work or reinterpret broker progress as business-effect truth. Benchmarks use bounded evidence profiles only and do not grant production lag/retention/partition numerics.

Kafka selection is prohibited until all seven D4-A evidence slots are credited by exact-run provenance and separately accepted.

### D4-B — Serialization, schema/catalog tooling and contract version representation

**Source decisions:** `OPEN-EVT-002`, `OPEN-EVT-003`, `OPEN-EVT-004`.  
**Entry candidate:** none.  
**Entry state:** `candidate_selection_open`.

D4-B SHALL select only after evidence proves:

- one canonical bounded serialization interpretation;
- duplicate/alias protected fields and parser ambiguity fail closed;
- schema/catalog tooling keeps reviewed contract + semantic manifest + provenance authoritative;
- compatibility CI catches semantic breaking changes in addition to schema shape changes;
- retained historical messages remain interpretable and keep comparison-profile/equivalence semantics;
- the concrete `contract_version` representation is distinct from deployment/API/provider/realtime/schema-registry versions and preserves breaking-change governance.

A serializer or registry SDK cannot close D4-B merely because it generates code successfully.

### D4-C — Delivery, acknowledgement, quarantine, equivalence, outbox, replay, historical-reader and recovery mechanisms

**Source decisions:** `OPEN-EVT-008..015`, `OPEN-EVT-025`.  
**Entry candidate:** none as a combined transport profile.  
**Entry state:** `candidate_selection_open`.

The accepted Waves 1–3 substrate already contains generic outbox/inbox/quarantine/reconciliation primitives, but those primitives are **evidence inputs**, not automatic closure of Phase 10's concrete transport/profile decisions.

D4-C SHALL prove:

- ack/checkpoint follows durable responsibility under crash, lease expiry and redelivery ambiguity;
- quarantine/redrive remains privileged/currently authorized and cannot bypass inbox/dedup/reconciliation;
- bytes/nesting/list/batch/compression/decompression limits are concrete and enforced;
- scoped same-ID/same-content equivalence succeeds while same-ID/different-content fails closed without becoming a cross-tenant equality oracle;
- outbox claim/dispatch/retry preserves one immutable logical message through broker-ack ambiguity and recovery;
- producer/source generation cannot resurrect across failover/restore/relocation;
- replay preserves original identity/meaning and cannot repeat irreversible effects by disabling dedup;
- historical readers/upcasters preserve semantic meaning and equivalence-profile continuity;
- recovery generation/epoch encoding, `(R,F]` inventory/reconciliation tooling and activation gates preserve broker/history/inbox/equivalence authority, treat restored missing evidence as uncertainty rather than absence, and cannot revive stale producer/replay/verifier authority.

`OPEN-EVT-025` is included here because its canonical question explicitly covers broker/history/inbox/equivalence-profile recovery and reconciliation, not only webhook recovery. Future webhook activation must reuse the accepted recovery-generation mechanism while adding the Product-specific destination/snapshot authority required by the webhook contracts.

### D4-D — Broker authentication, message protection and trace-context adaptation

**Source decisions:** `OPEN-EVT-016..018`.  
**Entry candidate:** none as a complete D4 profile.  
**Entry state:** `candidate_selection_open`.

D3 accepted SPIFFE/X.509-SVID workload identity and provider-neutral cryptographic authority as upstream mechanisms. D4-D must adapt those authorities to event transport without making broker-native identity, ACLs, trace headers or KMS product semantics canonical.

D4-D SHALL prove:

- workload identity derives a least-privilege broker credential/connection authority through a narrow replaceable adapter;
- producer/consumer authorization is contract- and scope-bounded and cannot be self-asserted through message headers;
- message protection and historical verifier continuity preserve the D3 cryptographic authority boundary;
- secret/credential payload exclusion and governed erasure remain true through broker/history/quarantine paths;
- trace-context input is bounded, validated/redacted and cannot become tenant, authorization, idempotency, ordering or replay authority.

## Deliberately excluded C3 decisions

The following remain outside D4 C2 acceptance and cannot be silently selected by benchmarks used only as bounded evidence values:

- `OPEN-EVT-006` partition counts / production partition mapping numerics;
- `OPEN-EVT-007` retry/backoff/jitter/concurrency numerics;
- `OPEN-EVT-019` realtime transport/buffer/session numerics;
- `OPEN-EVT-026..028` retention/replay/quarantine, residency and deprecation production horizons;
- `OPEN-REL-012.B` partition/retention/lag production numerics;
- production partition counts, retention horizons, retry budgets and realtime buffer/session values.

D4 may use bounded non-production values to execute falsification. Those values do not become production policy.

## Product-gated / later-gate decisions

`OPEN-EVT-020..024` are not silently waived. They are deliberately outside this internal D4 package because realtime resume and outbound webhook mechanisms depend on later/deferred capability or Product applicability gates.

In particular:

- `OPEN-EVT-021` first requires Product authority establishing which outbound webhook capability/families exist;
- `OPEN-EVT-022` and `OPEN-EVT-024` remain C2 once that webhook applicability exists, but do not block this internal eventing transport gate when the Product surface itself is not yet authorized;
- `OPEN-EVT-023` is Product-specific behavior and therefore cannot be invented by D4;
- `OPEN-EVT-020` remains coupled to an authorized realtime-resume slice;
- `OPEN-EVT-025` is **not deferred**: its internal broker/history/inbox/equivalence recovery mechanism belongs to D4-C. A later webhook slice adds destination-generation/snapshot-specific recovery obligations without replacing the accepted internal recovery authority.

Any later activation of the deferred surfaces requires its own exact mechanism/evidence gate and cannot inherit D4 acceptance by implication.

## D4 state machine

```text
scoped
  -> candidate_evidence_running
  -> per_track_conformed
  -> d4_acceptance_eligible
  -> separately_accepted
```

At entry:

```text
D4-A = candidate_leading_closure_pending
D4-B = candidate_selection_open
D4-C = candidate_selection_open
D4-D = candidate_selection_open
required_evidence = 26
credited_evidence = 0
transport_authority = not_selected_not_granted
wave4_implementation_authority = not_granted
production_authority = none
```

No track may enter `per_track_conformed` from documentation, SDK compatibility or feature availability alone.

## Evidence engineering rules

- every concrete product/version/image/toolchain used as candidate evidence is immutable/pinned where the ecosystem permits;
- evidence is attached to exact source SHA + workflow run/job/probe + artifact pins where applicable;
- the exact required-evidence inventory is independently pinned by assurance tooling; replacing named proof obligations with generic/documentation placeholders is invalid;
- no workflow may auto-credit its own current run into the machine ledger;
- source evidence and ledger promotion remain separate governance actions;
- synthetic/unit tests complement but never replace real broker/parser/recovery/concurrency evidence where a closure condition is about those mechanisms;
- every positive claim has a negative control proving the harness detects the forbidden outcome;
- alternate/stub transport tests must exercise the same logical port rather than a fake side path;
- Kafka-specific offsets, groups, transactions, topic IDs and partition IDs cannot cross the anti-corruption boundary into canonical domain/event identity;
- a green broker benchmark cannot grant C3 production topology/numerics;
- unavailable historical verifier/equivalence authority fails closed rather than converting uncertainty into duplicate success or effect eligibility;
- recovery testing preserves the accepted `(R,F]` continuity and `uncertainty != absence` laws.

## Machine-owned entry state

`implementation/d4-eventing-async/state-manifest.json` is the machine-owned D4 entry state for this gate.

The entry manifest intentionally credits **zero of 26** evidence slots. It exists to make scope, candidate state, exclusions and future proof accounting mechanically falsifiable before implementation/evidence work starts.

`tools/assurance/validate_d4_eventing_async_state.py` SHALL reject at minimum:

- premature D4 acceptance;
- any D4/Wave4/Product/production authority escalation;
- Kafka being represented as already selected;
- silent candidate selection in D4-B/C/D;
- evidence pre-credit at entry;
- omission of internal `OPEN-EVT-025` recovery/reconciliation authority from D4-C;
- omission, substitution or collapse of any named required-evidence slot, including Kafka partition-ceiling/fallback evidence;
- C3/later-gate scope leakage;
- predecessor drift away from the separately accepted D3 canonical commit.

## Explicit non-authority

This gate does not authorize:

- canonical Monitoring/Wave 4 Product implementation;
- production deployment;
- Kafka as canonical broker before D4-A closure;
- any serializer/schema registry/catalog technology before D4-B closure;
- production partition/retention/retry/topology numerics;
- realtime resume or outbound webhook Product activation;
- broker-native identity, ACL, offset, partition, topic or transaction semantics as canonical JLMirror authority.

## Exit criteria

D4 can be proposed for separate acceptance only when:

1. every D4-A..D track has a reviewed terminal C2 disposition;
2. all 26 required evidence slots have exact provenance and no unresolved remainder;
3. Kafka, if retained, satisfies all binding closure conditions from `OPEN-EVT-001-kafka-decision-record.md`, including benchmarked partition ceilings and tenant-cohort topic-sharding fallback, plus the claimed `OPEN-EVT-005` physical mapping and `OPEN-REL-012.A` outbox/drain mechanism evidence;
4. all broker/serialization/delivery/security/recovery mechanisms remain behind broker-neutral/platform-neutral authority boundaries;
5. deterministic assurance and all applicable D4 conformance workflows are green on the exact final HEAD;
6. all P0/P1/P2 review findings are resolved on that exact final HEAD;
7. fresh adversarial Codex review is clean on the same HEAD;
8. Wave 4, Product implementation, production and C3 numeric/topology authority remain explicitly ungranted;
9. acceptance remains a separate governance transition;
10. merge occurs only after separate explicit user authorization.

## Advancement boundary

After D4 is separately accepted, the next governed step must be derived from the then-current Implementation Readiness/Wave 4 state. D4 acceptance alone does not authorize Monitoring implementation.
