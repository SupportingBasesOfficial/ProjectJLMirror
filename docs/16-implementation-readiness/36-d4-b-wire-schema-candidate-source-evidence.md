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
  - reader-only fields require a default or resolution fails;
  - writer/reader field types must resolve according to Avro compatibility/promotion rules.
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

For the Avro evidence profile, a reviewed reference is additionally bound to the **exact reviewed structural schema content**. `avro:event:v1` and `avro:event:v2` are not free-form labels: passing a different same-name schema under either reviewed reference fails closed before resolution.

This source PR does not choose the future catalog/registry implementation. Axis B remains independent.

### Historical interpretation

Historical evidence binds candidate/profile identity, reviewed schema identity and original payload bytes. Re-reading with the same profile/schema preserves the exact historical bytes. Attempting to reinterpret those bytes through another candidate/profile or schema fails closed.

For Avro, the reviewed schema reference must resolve to the exact reviewed schema object before the writer/reader pair can participate in reviewed equivalence. This closes the gap where a historical string label could otherwise survive while the schema content silently changed.

Axis A therefore proves the profile/schema binding requirement. Axis B remains responsible for the later catalog/provenance mechanism that makes reviewed schema content durably recoverable.

### Compression boundary

No compression algorithm/profile is selected here. The source harness therefore accepts only identity transport and rejects compressed input. With compression unselected, decompression work is exactly zero and bounded.

A future compressed profile must separately prove a compressed-input bound, an output/decompression-work bound and fail-closed behavior before schema processing. Fixture message-size numbers remain source-evidence bounds, not selected production C3 numerics.

## Bounded JSON + JSON Schema profile

The evidence profile adds requirements beyond base JSON Schema validation:

- strict UTF-8 parsing;
- duplicate-member rejection before object materialization;
- protected alias-group collision rejection (`tenant_id`/`tenantId`, etc.);
- explicit required/type/null/enum/additional-property semantics;
- platform message-size, nesting, numeric magnitude, precision and scale bounds;
- bounded Decimal parsing instead of binary-float-dependent authoritative mapping;
- canonical numeric semantics (`1.0` and `1e0` are equivalent; signed zero normalizes to zero);
- distinct bounded decimal values remain distinct even above the exact-integer range of IEEE-754 binary64;
- decimal canonicalization is constructed directly from the exact `Decimal.as_tuple()` representation and does **not** call context-sensitive `Decimal.normalize()`;
- lowering or otherwise mutating the ambient thread-local Decimal context cannot change canonical equivalence;
- deterministic recursive semantic normalization for content equivalence;
- historical profile/schema binding;
- no schema/code loading selected by untrusted message content.

The specific numeric limits exercised here are test-profile bounds, not selected production thresholds. The context-independence rule is normative: authoritative equivalence cannot depend on caller-local Decimal precision.

## Protobuf profile

Raw Protobuf wire behavior is intentionally **not** accepted as sufficient for protected fields.

The JLMirror evidence profile requires a bounded wire predecoder before generated bindings. It:

- rejects non-minimal varints, including alternate byte encodings of the same value;
- rejects varints above the `uint64` domain;
- rejects invalid/reserved field numbers;
- rejects duplicate protected singular field numbers before normal last-one-wins behavior can collapse them;
- rejects **repeated occurrences of the same protected oneof member** as well as collisions between different oneof members;
- establishes required-field presence for the fixture's protected tenant/event fields;
- makes optional severity semantics explicit: accepted enum values are explicit and null is represented by absence in this profile;
- preserves unknown binary field bytes when forward compatibility requires it;
- treats semantic normalization, not raw serializer bytes, as equivalence authority;
- preserves occurrence order inside each repeated field number;
- binds historical payloads to reviewed Protobuf profile/schema identity;
- forbids descriptor/dynamic-message loading selected by untrusted message content.

The normalization rule is asymmetric by design: occurrences belonging to **different field numbers** may be regrouped because wire serialization order is not contract authority; occurrences belonging to the **same repeated field number** retain their original order because repeated-value order may be semantic. A global sort would therefore be invalid even if deterministic.

The same-oneof-member rule closes a separate ambiguity: `field 3=a, field 3=b` must not reach a generated binding that could collapse it with last-one-wins semantics merely because no *different* oneof member was present.

## Avro profile

Avro evolution is made explicit rather than implicit. The evidence model includes primitive/union type declarations and checks writer→reader compatibility before resolving values.

The profile requires:

- reviewed `avro:event:v1` / `avro:event:v2` references are bound to exact reviewed structural schema content before resolution;
- original writer schema identity/content remains recoverable for historical interpretation;
- every field declared by the writer schema must be present in the writer datum;
- a reader default is applied only when the field is **absent from the writer schema**, never to fabricate a writer-declared field omitted by malformed input;
- reader-schema resolution is explicit;
- reader-only fields require defaults or resolution fails;
- writer/reader field types must be compatible under the reviewed Avro promotion rules;
- an incompatible type pair such as writer `boolean` → reader `string` fails closed;
- an allowed promotion is not merely *validated*: the writer-side datum is converted/materialized into the selected reader representation before equivalence;
- numeric promotion such as writer `int` → reader `double` canonicalizes to the same reader representation as a native writer `double` datum with the same reader value;
- **Avro `float` is materialized at its declared IEEE-754 binary32 width before equivalence**, both when the writer type is `float` and when a value is promoted into a reader `float`;
- writer `float` → reader `double` first materializes the writer's binary32 value and only then widens that resolved value to the reader's binary64 representation;
- the evidence vector `16777217` promoted from writer `int` to reader `float` must canonicalize to `16777216.0`, exactly matching a native Avro `float` carrying that same single-precision value;
- Python's host binary64 `float` representation is therefore never allowed to silently redefine Avro single-precision contract semantics;
- `bytes` → `string` promotion requires strict UTF-8 and produces a bounded reader string; invalid UTF-8 fails closed;
- `string` → `bytes` promotion produces bounded UTF-8 bytes;
- float/double admission and numeric promotion catch conversion overflow and convert it to `EvidenceViolation`; adversarial huge integer input cannot escape the fail-closed evidence boundary through raw `OverflowError`;
- defaults must match the first declared reader type in the evidence model;
- required tenant/event fixture semantics are explicit after resolution;
- nullable severity and its accepted enum values are explicit after resolution;
- record name, field count, field-name length and aliases-per-field are bounded before resolution;
- datum field count is bounded before copying/resolution;
- string and bytes scalar sizes are bounded before canonicalization;
- `int`/`long` values are constrained to their declared Avro ranges;
- float/double fixture values must be finite;
- the source evidence intentionally models only a reviewed bounded primitive/union subset; nested complex Avro types are not silently accepted by this fixture;
- canonical equivalence is structural and type-tagged **after reader-side promotion and bounded writer→reader resolution**, rather than using unrestricted recursive JSON serialization;
- generic reviewed record resolution and `Event` domain invariants are separate concerns: generic fixtures may prove promotion behavior, while a record named `Event` still cannot bypass required `tenant_id`/`event_type` semantics;
- field aliases are reviewed and ambiguous aliases fail closed;
- historical payloads are bound to Avro profile/writer-schema identity and exact reviewed schema content;
- message payloads cannot choose arbitrary writer/reader schema content.

These are evidence-profile limits, not selected production C3 numerics. A future concrete Avro runtime/profile may broaden the admitted schema subset only through separately reviewed bounded evidence; this PR does not imply arbitrary nested Avro datum processing is acceptable.

The harness remains a specification-level evidence model, not a substitute for a future pinned Avro runtime/registry conformance run.

## Runtime-independence boundary

The source harness deliberately does not declare one SDK's generated-object behavior authoritative. It exercises JSON bytes plus bounded/context-independent Decimal object semantics, Protobuf wire semantics before generated bindings, and bounded Avro writer/reader type resolution with exact reviewed schema binding, declared-width float materialization and explicit reader-side promotion.

A later Java, Go, Python, Rust or other implementation remains eligible only if these authoritative semantics survive. Runtime convenience cannot redefine canonical JLMirror contract meaning.

## Cross-axis independence

Axis A does not select reviewed Git catalog vs registry-backed catalog vs hybrid catalog (`OPEN-EVT-003`), nor `contract_version` representation (`OPEN-EVT-004`). A future catalog/registry product cannot select JSON, Protobuf or Avro by implication.

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
- JSON protected duplicates/aliases, excessive nesting, lossy binary-float normalization, collapse of distinct bounded decimals and ambient-Decimal-context drift;
- Protobuf non-minimal varints, `uint64` overflow, protected last-one-wins collapse, same-member oneof duplication, cross-member oneof collision and presence/enum weakening;
- Protobuf raw-byte-order authority and repeated-order loss;
- loss of required Protobuf unknown binary fields;
- Avro reviewed-ref / schema-content substitution under the same label;
- omission of a writer-declared Avro field followed by illegitimate reader-default fabrication;
- Avro `float` semantic drift caused by leaving a declared single-precision value in the host runtime's binary64 representation;
- uncaught float/double conversion overflow escaping the fail-closed validation path;
- Avro alias ambiguity, missing legitimate reader defaults, incompatible writer/reader types and nullable-semantic loss;
- Avro allowed-promotion validation without reader-side materialization, including numeric representation drift and invalid UTF-8 `bytes` → `string` conversion;
- Avro schema/datum cardinality overflow, overlong names/aliases/scalars, out-of-range numeric values and unrestricted nested datum acceptance;
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
