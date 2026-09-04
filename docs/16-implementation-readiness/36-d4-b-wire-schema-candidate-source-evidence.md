# D4-B — Wire Serialization / Schema Candidate Source Evidence

**Status:** source evidence only — no D4-B wire selection, no catalog selection, no contract-version selection, no ledger promotion  
**Canonical base:** `main@9cfe67915b6081af015670d7f1edb7ecf11ffdf2`  
**Track:** D4-B / Axis A — `OPEN-EVT-002`

## Purpose

This package executes governed candidate-dependent source evidence for the D4-B wire serialization/schema-language axis.

It evaluates three concrete candidate classes admitted by the accepted plan:

1. `bounded_json_plus_json_schema_profile`;
2. `protobuf_profile`;
3. `avro_profile`.

The abstract `equivalent_reviewed_profile` remains `insufficient_evidence` because no concrete equivalent candidate has been supplied.

```text
ELIGIBLE UNDER A GUARD PROFILE != DEFAULT FORMAT BEHAVIOR IS ACCEPTABLE
ELIGIBLE FOR EVIDENCE != SELECTED
SOURCE EVIDENCE != LEDGER CREDIT
AXIS A RESULT != AXIS B/C CHOICE
INTERNAL PROFILE != EXTERNAL WEBHOOK PROFILE BY IMPLICATION
D4-B RESULT != D4 ACCEPTANCE
```

## Official source facts used by the evidence

The source package is grounded in format specifications/documentation, not in one language runtime:

- Protocol Buffers encoding guide: `https://protobuf.dev/programming-guides/encoding/`
  - singular duplicate fields are accepted with last-one-wins behavior;
  - field serialization order is not guaranteed;
  - raw serialized bytes therefore cannot be treated as stable cross-runtime contract equivalence.
- Protocol Buffers editions guide: `https://protobuf.dev/programming-guides/editions/`
  - unknown binary fields are preserved by binary message handling;
  - some nonbinary conversion/copy paths can lose them.
- Apache Avro 1.11.2 specification: `https://avro.apache.org/docs/1.11.2/specification/`
  - historical interpretation uses the writer schema plus reader schema;
  - reader-only fields require a default or resolution fails;
  - writer-only fields may be ignored by a reader that does not define them.
- JSON Schema Draft 2020-12 validation vocabulary: `https://json-schema.org/draft/2020-12/json-schema-validation`
  - JSON numeric instances are not inherently bounded by JSON Schema.
- JSON Schema object reference: `https://json-schema.org/understanding-json-schema/reference/object`
  - additional object properties are allowed unless a profile explicitly restricts them.

These facts are pinned in the machine-owned manifest so they cannot silently disappear from the evidence rationale.

## Candidate result interpretation

All three concrete candidates currently reach only `eligible_for_evidence_execution`.

That means a reviewed JLMirror guard profile can satisfy the Axis A invariants exercised here. It does **not** mean any raw/default implementation behavior is accepted, preferred, canonical, production-ready or implementation-authorized.

### Bounded JSON + JSON Schema profile

The evidence profile adds requirements beyond base JSON Schema validation:

- strict UTF-8 parsing;
- duplicate-member rejection before object materialization;
- protected alias-group collision rejection (`tenant_id`/`tenantId`, etc.);
- explicit required/type/null/enum/additional-property semantics;
- platform numeric, message-size and nesting bounds;
- deterministic semantic normalization for content equivalence;
- no schema/code loading selected by untrusted message content.

This matters because JSON Schema alone does not provide the platform resource bounds JLMirror requires and additional properties are not denied by default.

### Protobuf profile

The raw Protobuf wire behavior is intentionally **not** accepted as sufficient for protected fields.

The JLMirror evidence profile therefore requires a bounded wire predecoder before generated bindings. That predecoder:

- rejects duplicate protected singular field numbers before Protobuf's normal last-one-wins behavior can collapse them;
- rejects protected oneof collisions before generated binding resolution;
- preserves unknown binary field bytes where forward compatibility requires it;
- treats field-order-independent semantic normalization, not raw serializer bytes, as equivalence authority;
- forbids descriptor/dynamic-message loading from untrusted message content.

This preserves Protobuf as a candidate without weakening JLMirror's fail-closed invariant.

### Avro profile

Avro's evolution model is made explicit rather than implicit:

- the original writer schema identity/content must remain recoverable for historical data;
- reader-schema resolution is explicit;
- reader-only fields require defaults or resolution fails;
- field aliases are reviewed and collisions fail closed;
- equivalence is computed after explicit writer→reader resolution;
- message payloads cannot choose arbitrary writer/reader schema content.

The harness uses a small record-resolution model to exercise those invariants without selecting a particular Avro runtime or registry product.

## Runtime-independence boundary

The source harness deliberately does not declare one SDK's generated-object behavior to be authoritative.

It exercises:

- JSON bytes and object semantics;
- Protobuf wire tags/lengths/unknown segments before generated bindings;
- Avro writer/reader resolution semantics.

A later implementation may use Java, Go, Python, Rust or another runtime only if the same normative behavior survives. Language-specific mapping convenience cannot redefine canonical JLMirror contract semantics.

## Bounded parser / decompression boundary

This source PR proves explicit message-size, nesting and wire-length bounds in its fixture harness. It does not select production numeric thresholds and it does not grant a decompression algorithm/profile.

Any later compressed transport profile must apply a hard compressed-input bound plus a hard post-decompression/output-work bound before schema processing. Those numerics remain outside this source-only decision.

## Cross-axis independence

Axis A does not select:

- reviewed Git catalog vs registry-backed catalog vs hybrid catalog (`OPEN-EVT-003`);
- `contract_version` representation (`OPEN-EVT-004`).

Likewise, a future catalog product cannot select JSON/Protobuf/Avro by implication.

The accepted surface policy remains: internal broker and external webhook profiles may differ only when conversion to canonical domain semantics and historical interpretation are explicit.

## Negative controls

The falsification suite blocks:

- additive hidden candidate selection;
- duplicate JSON members hiding conflicting selection state;
- source-run auto-credit or non-empty ledger credit;
- candidate promotion to `selected`;
- pretending an unevaluated equivalent candidate is eligible;
- removal of any Axis A must-prove invariant;
- removal of candidate-specific guard requirements;
- removal/rewrite of official source-fact inventory;
- JSON protected duplicates/aliases and excessive nesting;
- Protobuf protected last-one-wins collapse;
- Protobuf oneof collision and raw-byte-order authority;
- loss of required Protobuf unknown binary fields;
- Avro alias ambiguity and reader-only fields without defaults;
- D4-B ledger selection;
- D4/Product/Wave4/production/C3 authority escalation.

## Existing D4 state remains immutable

This package does not modify accepted ledger/state:

- D4-A remains Kafka bounded-C2 with 7/7 evidence;
- D4-B remains 5/5 evidence complete and selection pending;
- D4-C/D remain open, unselected and uncredited;
- D4-wide remains 12/26;
- D4 remains `scoped`;
- transport authority remains `selected_not_granted`;
- Product/Wave4 implementation remains `not_granted`;
- production remains `none`;
- C3 numeric/topology remains `not_selected`.

## Exit condition

This PR may be accepted only after exact-HEAD CI, panoramic/adversarial review and zero unresolved material threads prove that all three candidate profiles remain bounded, source-only and non-selecting.

Acceptance of this source PR still does not authorize a D4-B selection transition. Axis B catalog/registry evidence remains separately required before a later cross-axis selection decision.
