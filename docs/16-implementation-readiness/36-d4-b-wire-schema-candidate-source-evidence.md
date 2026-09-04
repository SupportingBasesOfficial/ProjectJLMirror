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

The package is grounded in format specifications/documentation, not one language runtime:

- Protocol Buffers encoding guide: `https://protobuf.dev/programming-guides/encoding/`
  - singular duplicate fields are accepted with last-one-wins behavior;
  - field serialization order is not guaranteed;
  - raw serialized bytes therefore cannot be stable cross-runtime contract-equivalence authority.
- Protocol Buffers editions guide: `https://protobuf.dev/programming-guides/editions/`
  - unknown binary fields are preserved by binary message handling;
  - some nonbinary conversion/copy paths can lose them.
- Apache Avro 1.11.2 specification: `https://avro.apache.org/docs/1.11.2/specification/`
  - historical interpretation uses writer schema plus reader schema;
  - reader-only fields require a default or resolution fails.
- JSON Schema Draft 2020-12 validation vocabulary: `https://json-schema.org/draft/2020-12/json-schema-validation`
  - JSON numeric instances are not inherently platform-bounded by JSON Schema.
- JSON Schema object reference: `https://json-schema.org/understanding-json-schema/reference/object`
  - additional object properties are allowed unless a profile explicitly restricts them.

These source facts are pinned in the machine-owned manifest and cannot silently disappear from the evidence rationale.

## Candidate result interpretation

All three concrete candidates currently reach only `eligible_for_evidence_execution`.

That means a reviewed JLMirror guard profile can satisfy the exercised Axis A contract. It does **not** mean raw/default format behavior is accepted, preferred, canonical, production-ready or implementation-authorized.

## Common source-profile boundary

### Static reviewed schema authority

The harness uses a finite reviewed schema-reference set for every concrete candidate. Schema/descriptor/writer-reader selection is configuration authority, not message authority.

Untrusted message content cannot provide a URL, descriptor, schema body or executable object that becomes authoritative. The harness explicitly attempts such message-driven selection and requires fail-closed behavior.

This source PR does not choose the future catalog/registry implementation. Axis B remains independent.

### Historical interpretation

Historical evidence binds:

- candidate/profile identity;
- reviewed schema identity;
- original payload bytes.

Re-reading with the same profile/schema preserves the exact historical bytes. Attempting to reinterpret those bytes through another candidate/profile or schema fails closed.

Axis A therefore proves the profile/schema binding requirement. Axis B remains responsible for the later catalog/provenance mechanism that makes reviewed schema content durably recoverable.

### Compression boundary

No compression algorithm/profile is selected here. The source harness therefore accepts only identity transport and rejects compressed input.

That is deliberate: with compression unselected, decompression work is exactly zero and bounded. A future compressed profile must separately prove a compressed-input bound, an output/decompression-work bound and fail-closed behavior before schema processing.

The fixture message-size numbers in this source package are evidence bounds only and do not select production C3 numerics.

## Bounded JSON + JSON Schema profile

The evidence profile adds requirements beyond base JSON Schema validation:

- strict UTF-8 parsing;
- duplicate-member rejection before object materialization;
- protected alias-group collision rejection (`tenant_id`/`tenantId`, etc.);
- explicit required/type/null/enum/additional-property semantics;
- platform message-size, nesting, numeric magnitude, precision and scale bounds;
- bounded Decimal parsing instead of binary-float-dependent authoritative mapping;
- canonical numeric semantics (`1.0` and `1e0` are equivalent; signed zero normalizes to zero);
- deterministic recursive semantic normalization for content equivalence;
- historical profile/schema binding;
- no schema/code loading selected by untrusted message content.

This matters because JSON Schema alone does not supply all platform resource bounds JLMirror requires and additional properties are not denied by default.

The specific numeric limits exercised here are test-profile bounds, not selected production thresholds.

## Protobuf profile

Raw Protobuf wire behavior is intentionally **not** accepted as sufficient for protected fields.

The JLMirror evidence profile requires a bounded wire predecoder before generated bindings. It:

- rejects non-minimal varints, including alternate byte encodings of the same value;
- rejects varints above the `uint64` domain;
- rejects invalid/reserved field numbers;
- rejects duplicate protected singular field numbers before normal last-one-wins behavior can collapse them;
- rejects protected oneof collisions before generated binding resolution;
- establishes required-field presence for the fixture's protected tenant/event fields;
- makes optional severity semantics explicit: accepted enum values are explicit and null is represented by absence in this profile;
- preserves unknown binary field bytes when forward compatibility requires it;
- treats semantic normalization, not raw serializer bytes, as equivalence authority;
- preserves occurrence order inside each repeated field number;
- binds historical payloads to reviewed Protobuf profile/schema identity;
- forbids descriptor/dynamic-message loading selected by untrusted message content.

The normalization rule is asymmetric by design: occurrences belonging to **different field numbers** may be regrouped because wire serialization order is not contract authority; occurrences belonging to the **same repeated field number** retain their original order because repeated-value order may be semantic. A global sort would therefore be invalid even if deterministic.

The varint hardening also prevents a superficially bounded parser from admitting values outside the Protobuf `uint64` scalar domain through a ten-byte over-range representation.

## Avro profile

Avro evolution is made explicit rather than implicit:

- original writer schema identity/content must remain recoverable for historical interpretation;
- reader-schema resolution is explicit;
- reader-only fields require defaults or resolution fails;
- required tenant/event fixture semantics are explicit after resolution;
- nullable severity and its accepted enum values are explicit after resolution;
- field aliases are reviewed and ambiguous aliases fail closed;
- equivalence is computed after explicit writer→reader resolution, not from raw schema text;
- historical payloads are bound to Avro profile/writer-schema identity;
- message payloads cannot choose arbitrary writer/reader schema content.

The harness uses a small specification-level record-resolution model to exercise these invariants without selecting a particular Avro runtime or registry product.

## Runtime-independence boundary

The source harness deliberately does not declare one SDK's generated-object behavior authoritative.

It exercises:

- JSON bytes plus bounded Decimal/object semantics;
- Protobuf wire tags/lengths/varints/unknown segments before generated bindings;
- Avro writer/reader resolution semantics.

A later Java, Go, Python, Rust or other implementation remains eligible only if these authoritative semantics survive. Runtime convenience cannot redefine canonical JLMirror contract meaning.

## Cross-axis independence

Axis A does not select:

- reviewed Git catalog vs registry-backed catalog vs hybrid catalog (`OPEN-EVT-003`);
- `contract_version` representation (`OPEN-EVT-004`).

Likewise, a future catalog/registry product cannot select JSON, Protobuf or Avro by implication.

The accepted surface rule remains: internal broker and external webhook profiles may differ only when conversion to canonical domain semantics and historical interpretation are explicit.

## Negative controls

The falsification suite blocks:

- additive hidden candidate selection;
- duplicate JSON members hiding conflicting selection state;
- source-run auto-credit or non-empty ledger credit;
- candidate promotion to `selected`;
- pretending an unevaluated equivalent candidate is eligible;
- removal of any Axis A must-prove invariant or candidate-specific guard requirement;
- removal/rewrite of official source-fact inventory;
- compressed input without a selected decompression profile;
- schema/descriptor selection by untrusted message content;
- historical cross-profile reinterpretation;
- JSON protected duplicates/aliases, excessive nesting and runtime-dependent numeric spellings;
- Protobuf non-minimal varints, `uint64` overflow, protected last-one-wins collapse and presence/enum weakening;
- Protobuf raw-byte-order authority and repeated-order loss;
- loss of required Protobuf unknown binary fields;
- Avro alias ambiguity, missing reader defaults and nullable-semantic loss;
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

This PR may be accepted only after exact-HEAD CI, adversarial/panoramic review and zero unresolved material threads prove that all three candidate profiles remain bounded, source-only and non-selecting.

Acceptance of this source PR still does not authorize D4-B selection. Axis B catalog/registry evidence remains separately required before a later cross-axis selection decision.
