# D4-A Kafka C2 Selection

## Status

This record governs the transition from **D4-A evidence complete (7/7)** to **bounded C2 mechanism selection**.

Canonical selection base:

- `main@9763e8b01b7a9bf4e5fda4be2c05abb04e8532e8`

Selected D4-A mechanism family:

- **Kafka**

Reviewed conformance pin used by the evidence program:

- candidate version: `4.3.1`
- image: `apache/kafka:4.3.1@sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837`
- OCI/index digest: `sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837`
- Linux/amd64 manifest digest: `sha256:ccd1314e47ec76909e01f86308b4dcf2064f19f7c89759234322314b0e319e26`

The immutable 4.3.1 image is the **reviewed C2 conformance pin**, not a permanent production-version freeze. A later Kafka upgrade may be admitted only through governed compatibility/conformance evidence that preserves the accepted semantic and authority boundaries.

## Decision

Kafka is selected as the **D4-A bounded C2 broker/transport mechanism** because the complete D4-A evidence program has now established all seven required evidence classes:

1. `capacity_envelope_baseline_growth_stress`
2. `broker_neutral_anti_corruption_stub_swap`
3. `regulated_payload_erasure_granularity`
4. `exactly_once_guardrail_consumer_inbox_enforcement`
5. `ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency`
6. `physical_naming_routing_and_cell_topology_adapter_mapping`
7. `broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark`

The governed machine-owned transition is:

- D4-A candidate: `kafka`
- D4-A candidate status: `selected_c2_candidate`
- D4-A track state: `selected_candidate`
- D4-A evidence: `7/7`
- D4-A selection state: `selected`
- D4-A acceptance state: `track_selected_separate_d4_acceptance_required`

## Selection is not authority

This selection is intentionally narrower than an implementation or deployment authorization.

After this transition:

- D4 global gate remains `scoped`;
- D4 transport authority is `selected_not_granted`;
- canonical Product implementation authority remains `not_granted`;
- Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

Therefore, **Kafka selected** does not mean:

- D4 accepted;
- Product implementation authorized;
- Wave 4 implementation authorized;
- production deployment authorized;
- production partition counts, retry numerics, retention horizons, lag limits, topology, or other C3 values selected.

## D4-B / D4-C / D4-D remain open

D4-A completion and selection do not propagate evidence or candidate choices into sibling tracks.

The following remain explicitly open:

- **D4-B — serialization/schema/catalog/versioning**: no candidate selected; zero evidence credited.
- **D4-C — delivery/ack/quarantine/outbox/replay/history/recovery**: no candidate selected; zero evidence credited.
- **D4-D — broker auth/message protection/trace context**: no candidate selected; zero evidence credited.

Full D4 acceptance remains impossible until all D4 tracks reach reviewed terminal C2 disposition, all required evidence is complete, exact-HEAD assurance is clean, and a separate acceptance action is performed.

## Historical truth is immutable

The D4-A source evidence and ledger-promotion records predate this selection. They must continue to represent the state that existed when they were created.

In particular:

- source runs remain `current_run_auto_credit=false`;
- source runs remain `ledger_credit=[]`;
- source-run provenance that recorded `kafka_selection_state=not_selected` remains unchanged;
- the final recovery promotion record remains `kafka_selection_state=not_selected` and `d4_transport_authority=not_selected_not_granted`, because selection had not yet occurred at promotion time.

The current selection is represented only by the present evidence plan/state plus `implementation/d4-eventing-async/d4-a-selection-record.json`.

Rewriting historical source/promotion records to say Kafka was already selected would corrupt the evidence chain and is forbidden.

## Replacement and upgrade governance

Kafka is selected because its reviewed evidence satisfies the current D4-A contract and authority requirements. The platform must nevertheless remain semantically broker-neutral at its domain boundaries.

A material replacement of Kafka, or a change that alters the selected broker mechanism's semantic behavior, requires a separately reviewed transition demonstrating equivalent or stronger evidence for the affected D4-A obligations.

An in-family Kafka version upgrade does not require pretending that 4.3.1 is permanently frozen, but it must preserve:

- canonical logical message identity independent of topic/partition/offset/group identity;
- outbox/inbox and consumer-effect safety;
- ordering-scope semantics and bounded concurrency;
- regulated-payload and erasure boundaries;
- topology anti-corruption boundaries;
- recovery, ambiguity, and anti-starvation semantics;
- transport non-authority over business effects.

## Governed artifacts

Current selection authority is represented by:

- `implementation/d4-eventing-async/d4-a-evidence-plan.json`
- `implementation/d4-eventing-async/state-manifest.json`
- `implementation/d4-eventing-async/d4-a-selection-record.json`
- `tools/assurance/validate_d4a_evidence_plan.py`
- `tools/assurance/test_validate_d4a_evidence_plan.py`
- `tools/assurance/validate_d4_eventing_async_state.py`
- `tools/assurance/test_validate_d4_eventing_async_state.py`
- `.github/workflows/d4-a-kafka-candidate-evidence-plan.yml`
- `.github/workflows/d4-eventing-async-entry-gate.yml`

The prior promotion/source provenance chain remains independently validated and byte-bound by SHA-256.

## Merge and acceptance governance

This selection change may merge only after:

1. exact-HEAD CI is clean;
2. full D4-A and related D4 panoramic/adversarial review is clean;
3. no unresolved material review thread remains;
4. the PR is mergeable;
5. separate explicit user authorization for merge is given.

Merging this selection record still does **not** constitute full D4 acceptance. Full D4 acceptance remains a later, separate governed action.
