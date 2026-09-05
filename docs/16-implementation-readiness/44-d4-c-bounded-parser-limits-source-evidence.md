# D4-C OPEN-EVT-010 bounded parser limits source evidence

Status: **candidate source evidence only; no ledger credit, no candidate selection, no implementation authority**.

Canonical base: `main@c72f53100e504922563106d1f8d2d3a5e7577589`.

## Scope

This source package evaluates the D4-C axis `bounded_message_payload_batch_and_compression` for `OPEN-EVT-010` / `bounded_message_batch_compression_and_parser_limits`.

Concrete candidate classes:

- `contract_bound_application_limits_with_transport_precheck`;
- `bounded_envelope_codec_profile`;
- `layered_transport_and_application_bounds_profile`.

`equivalent_reviewed_profile` remains `insufficient_evidence` until separately reviewed evidence exists.

## Required proofs

The package must prove all seven obligations from the accepted D4-C candidate evaluation plan:

1. message payload and batch sizes are bounded before unbounded allocation;
2. nesting, string, collection and field counts are bounded;
3. decompression work and output are bounded;
4. parser recursion and CPU amplification fail closed;
5. large artifacts and raw telemetry are referenced or routed to specialized planes;
6. transport limits cannot silently weaken contract limits;
7. limit failures are deterministic, observable and non-retry-amplifying.

## Executable evidence semantics

The evidence harness uses deliberately small numeric limits so adversarial cases are fast and deterministic. Those values are identified by `bounded_parser_fixture_only_noncanonical`; they are **test fixtures only**, not production limit selections.

The model enforces a contract-owned admission boundary:

- declared oversize is rejected before stream iteration;
- streams without a declared length are accumulated only inside a bounded budget;
- gzip output is produced incrementally with a hard decompressed-output ceiling;
- trailing bytes or concatenated gzip members are rejected rather than silently changing payload meaning;
- JSON nesting is pre-scanned outside quoted/escaped strings before recursive parser entry, so deeply nested small inputs fail closed before parser recursion;
- JSON is parsed only after wire, decompression and pre-parser nesting bounds have succeeded;
- structural validation is iterative and independently bounds strings, collections and total fields;
- top-level batches are bounded before per-item semantic admission;
- artifact and raw telemetry classes must use references to specialized planes rather than inline bulk payloads, including when nested inside wrappers;
- a transport configuration may be stricter than the contract, but a more permissive transport configuration cannot relax the contract bound;
- every limit rejection emits a stable machine code and `retryable=false`.

This package does not claim that Python, `json`, zlib/gzip, the test limit values, reference URI examples, or any transport implementation is the production choice.

## Non-authority boundary

After this source evidence run, the required governed state remains exactly:

- D4-A `7/7`;
- D4-B `5/5` selected bounded C2 profile;
- D4-C `2/9`, candidate `null`, `not_selected`, `candidate_selection_open`;
- OPEN-EVT-010 remains **uncredited**;
- D4-D `0/5`;
- D4-wide `14/26`;
- D4 gate `scoped`;
- transport authority `selected_not_granted`;
- Product implementation authority `not_granted`;
- Wave4 implementation authority `not_granted`;
- production authority `none`;
- C3 numeric/topology authority `not_selected`.

A later ledger promotion, candidate selection, production limits, parser/codec choice, topology or full D4 acceptance all require separate governed transitions.
