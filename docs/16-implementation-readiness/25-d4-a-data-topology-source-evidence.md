# D4-A — Regulated Payload + Physical Topology Source Evidence

**Status:** source-evidence package only — no ledger credit, no Kafka selection, no D4/Wave 4/Product/production/C3 authority granted  
**Canonical base:** `main@63ced38f95b516b495db3f238e1a9e8689b184eb`  
**Track:** D4-A — broker transport, physical routing and anti-corruption boundary

## Purpose

This package implements the next preferred D4-A source-evidence block after the reviewed semantic-boundary evidence was promoted to 2/7. It generates reviewable source-run evidence for exactly two still-open obligations:

- `regulated_payload_erasure_granularity`;
- `physical_naming_routing_and_cell_topology_adapter_mapping`.

It intentionally does **not** edit the D4-A evidence ledger. A green run is evidence available for review, not evidence credit.

```text
SOURCE RUN != LEDGER CREDIT
OPAQUE REFERENCE DEFAULT != RAW PAYLOAD EXCEPTION
PHYSICAL MAPPING != CONTRACT IDENTITY
KAFKA LEADING CANDIDATE != KAFKA SELECTED
D4-A SOURCE EVIDENCE != D4 ACCEPTANCE
```

## Regulated-payload proof

The executable policy defaults `sensitive_or_regulated` traffic to an opaque governed reference. Raw regulated record-value bytes are rejected unless all exception controls hold simultaneously:

1. per-tenant topic or partition assignment provides the required isolation granularity;
2. an explicit maximum segment-retention ceiling is present and is no greater than the governed erasure SLA for the data class;
3. explicit sign-off exists from the erasure-governance authority.

Negative controls deliberately attempt raw regulated leakage, remove each exception control one at a time, and provide a retention ceiling that exceeds the erasure SLA. Every case must fail. A positive exceptional case exists only to prove the three-way conjunction is executable; it grants no general exception and no production retention numeric.

## Physical topology adapter proof

The topology probe establishes that tenant authorization must succeed **before** a logical channel can be mapped to any physical destination. An unauthorized mapping attempt is a failing negative control.

Two different physical mappings are then exercised for the same logical channel. The physical destination changes while the consumer semantic identity remains the logical channel. This demonstrates that physical topic/stream/cell naming remains adapter-owned and replaceable rather than becoming canonical contract identity.

The bounded example names are test fixtures only. They do not select production topology, partition counts, replica counts, cell counts, topic counts, or C3 numeric authority.

## Machine-owned source package

The package manifest is:

`implementation/d4-eventing-async/source-evidence/data-topology/source-evidence-manifest.json`

Assurance tooling:

- `tools/assurance/d4a_data_topology/policy_probe.py` — executable erasure and topology boundary;
- `tools/assurance/d4a_data_topology/test_data_topology.py` — positive/negative runtime controls;
- `tools/assurance/d4a_data_topology/validate_source_evidence.py` — exact evidence IDs/kinds, non-promotion and authority boundary checks;
- `tools/assurance/d4a_data_topology/emit_source_provenance.py` — runtime-resolved immutable source-run provenance.

CI workflow:

`.github/workflows/d4-a-data-topology-source-evidence.yml`

The workflow checks out the exact PR HEAD, runs the package probes, re-runs the D4 ledger/plan validators and the Phase 10 contract suite, proves the source package has not credited itself, resolves the exact workflow job ID at runtime, and emits a retained provenance artifact containing repository SHA, run ID, run attempt, job ID/name, manifest digest, evidence IDs/kinds and promotion rule.

## Non-claims

This source package does not claim:

- live Kafka broker execution;
- Kafka selection or acceptance;
- capacity, ordering/partition or recovery evidence;
- production erasure-retention numerics;
- production physical topology;
- any new D4 transport authority;
- Product or Wave 4 implementation authority;
- production authority;
- C3 numeric/topology authority.

## Exit gate

This PR is source-evidence complete only when its exact HEAD has green CI and adversarial review confirming:

- exactly the two intended evidence IDs/kinds are represented;
- raw regulated bytes are deny-by-default;
- all three exception controls are jointly mandatory and independently falsified;
- tenant authorization precedes physical transport mapping;
- physical destination replacement does not change consumer semantic identity;
- source-run provenance is runtime-resolved and immutable;
- `current_run_auto_credit=false` and `ledger_credit=[]` remain true;
- D4-A ledger remains 2/7;
- Kafka remains not selected;
- all D4/Wave4/Product/production/C3 authorities remain unchanged.

Only after the exact source run is reviewed may a separate PR promote these evidence IDs into the ledger.
