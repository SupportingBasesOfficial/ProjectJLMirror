# D4-B — Wire Serialization / Schema Candidate Source Evidence

**Status:** source evidence only — no D4-B wire selection, no catalog selection, no contract-version selection, no ledger promotion  
**Canonical base:** `main@9cfe67915b6081af015670d7f1edb7ecf11ffdf2`  
**Track:** D4-B / Axis A — `OPEN-EVT-002`

## Purpose

This package executes candidate-dependent source evidence for the D4-B wire serialization/schema-language axis. It evaluates:

1. `bounded_json_plus_json_schema_profile`;
2. `protobuf_profile`;
3. `avro_profile`.

Each concrete candidate may reach only `eligible_for_evidence_execution`. `equivalent_reviewed_profile` remains `insufficient_evidence`.

```text
ELIGIBLE FOR EVIDENCE != SELECTED
SOURCE EVIDENCE != LEDGER CREDIT
AXIS A RESULT != AXIS B/C CHOICE
D4-B RESULT != D4 ACCEPTANCE
```

## Common authority boundary

- reviewed schema identity is configuration authority, never message authority;
- message content cannot select arbitrary schema, descriptor, URL or executable code;
- historical interpretation binds candidate/profile, schema identity and original bytes;
- Avro historical envelopes additionally bind exact reviewed structural schema content by SHA-256;
- compression remains unselected, therefore only identity transport is accepted and decompression work is zero;
- `current_run_auto_credit=false` and `ledger_credit=[]` remain mandatory;
- no result in this package grants implementation, production or D4-wide authority.

## Bounded JSON + JSON Schema profile

The evidence profile requires:

- strict UTF-8 byte decoding;
- duplicate-member rejection before object materialization;
- protected alias collision rejection;
- explicit required/type/null/enum/additional-property semantics;
- bounded message size, nesting, numeric precision, scale and magnitude;
- bounded Decimal parsing rather than binary-float authoritative mapping;
- context-independent numeric canonicalization built from exact `Decimal.as_tuple()` data;
- context-independent magnitude admission using exact `Decimal.copy_abs()` semantics;
- parser and traversal recursion exhaustion translated to controlled `EvidenceViolation` rejection;
- decoded JSON **keys and string values must be Unicode scalar sequences**: escaped lone surrogates such as `"\ud800"` are rejected after JSON unescape, rather than preserved as host-language surrogate code points;
- deterministic semantic normalization for content equivalence;
- historical profile/schema binding and no message-selected schema loading.

The Unicode-scalar rule is normative because raw UTF-8 validity alone is insufficient: JSON escape processing can construct an unpaired surrogate after the byte decoder has already succeeded. Canonical interpretation must therefore validate decoded strings, recursively including object keys and nested values, before they can become contract meaning.

## Protobuf profile

The evidence profile requires a bounded predecoder before generated bindings. It:

- rejects non-minimal varints and `uint64` overflow;
- rejects invalid/reserved field numbers;
- rejects duplicate protected singular fields before last-one-wins collapse;
- rejects repeated occurrences of the same protected oneof member and collisions across protected oneof members;
- makes required presence and enum semantics explicit;
- preserves required unknown binary fields;
- does not treat raw serialized cross-field order as equivalence authority;
- preserves occurrence order inside the same repeated field number;
- binds historical payload to reviewed profile/schema identity;
- forbids descriptor/dynamic schema loading from untrusted message content.

## Avro profile

Avro evolution is modeled through explicit writer schema, selected writer-union branch, reader schema and bounded reader-side promotion.

The profile requires:

- reviewed refs bind exact structural schema content;
- historical envelopes persist and verify schema-content SHA-256;
- every writer-declared field is present in the datum;
- every writer value, including reader-discarded writer-only fields, is validated before projection;
- reader defaults apply only when a field is absent from the writer schema;
- aliases are reviewed and ambiguity fails closed;
- decoded union branch identity is preserved; ambiguous host-runtime branch inference is forbidden;
- **writer→reader compatibility for a union datum is evaluated from the selected writer branch only**. Incompatible unselected branches cannot reject a valid selected branch, while an incompatible selected branch must fail;
- allowed promotions materialize the reader representation before equivalence;
- Avro `float` is materialized at IEEE-754 binary32 width before equivalence;
- **integer (`int`/`long`) → Avro `float` promotion rounds directly from the exact integer to binary32**, without first converting through host binary64 and risking double rounding;
- the adversarial long vector `4611686293305294849` must resolve directly to the actual adjacent binary32 value `4611686568183201792`, not the lower neighbor produced by binary64 double-rounding;
- `float`/`double` runtime admission is type-strict and excludes boolean/string coercion;
- conversion overflow and non-finite values fail closed;
- string, schema-name and schema-digest encoding uses strict UTF-8 with encoding failures translated to `EvidenceViolation`;
- schema width, name/alias size, datum width, scalar size and numeric domains are bounded;
- canonical equivalence is structural and type-tagged after bounded writer→reader resolution;
- `Event` domain invariants remain enforced separately from generic promotion fixtures.

### Selected-union-branch invariant

For writer union `("string", "int")`, reader `("long",)` and decoded datum `AvroUnionDatum(1, 7)`, the selected `int` branch is compatible and must promote to `long(7)` even though the unused `string` branch is incompatible. Conversely `AvroUnionDatum(0, "x")` must fail. The wire-selected branch is authoritative for that datum; schema-wide compatibility across unused branches would be semantically wrong.

### Exact integer-to-binary32 invariant

Avro `long -> float` cannot use `float(integer)` as an intermediate representation. A binary64 intermediate may land exactly on a binary32 midpoint and then round a second time to the wrong neighbor. The evidence helper therefore performs round-to-nearest-ties-to-even directly with integer arithmetic before constructing the binary32 bit pattern. For the adversarial vector above, the exact midpoint is `4611686293305294848`; the test value is midpoint + 1 and therefore rounds upward to `4611686568183201792`.

## Runtime-independence boundary

Host-language convenience is not authoritative contract meaning. The package explicitly rejects or neutralizes runtime-specific behaviors including:

- Decimal ambient context drift;
- parser recursion exceptions escaping the evidence boundary;
- unpaired-surrogate strings surviving JSON unescape;
- Protobuf last-one-wins collapse and non-canonical varints;
- Avro implicit union inference;
- schema-wide rejection based on unselected Avro union branches;
- binary64 double-rounding during integer→binary32 promotion;
- host Unicode encoder exceptions escaping the Avro boundary;
- boolean/string coercion into numeric Avro values.

## Negative controls

The source evidence must fail if any of the following is weakened:

- hidden candidate selection or authority escalation;
- auto-credit or non-empty ledger credit;
- accepted Axis A must-prove inventory;
- JSON duplicate/alias, numeric, recursion or Unicode-scalar guards;
- Protobuf canonical-varint, duplicate/oneof, presence/enum, unknown-field or ordering guards;
- Avro schema-content binding, historical digest, writer-field validation, explicit union branch identity, selected-branch compatibility, direct exact integer→binary32 rounding, strict UTF-8, width/type/overflow, promotion or bounded-resource guards;
- D4-B 5/5 selection-pending state;
- D4-A Kafka 7/7 state;
- D4-C/D open/uncredited state;
- D4 scoped state or Product/Wave4/production/C3 non-authority.

## Existing D4 state remains immutable

- D4-A: Kafka bounded-C2, 7/7;
- D4-B: 5/5 evidence, candidate `null`, selection pending;
- D4-C/D: open, unselected, uncredited;
- D4-wide: 12/26;
- D4: `scoped`;
- transport authority: `selected_not_granted`;
- Product/Wave4 implementation: `not_granted`;
- production: `none`;
- C3 numeric/topology: `not_selected`.

## Exit condition

This PR may reach final gate only when the exact current HEAD has:

1. full exact-HEAD CI green;
2. candidate evaluator, falsification and manifest validator green;
3. Phase 10 contracts green;
4. zero unresolved material review threads;
5. fresh exact-HEAD adversarial review with no unresolved finding;
6. mergeable/open/non-draft PR state;
7. separate explicit merge authorization.

No source-evidence result in this document selects JSON/JSON Schema, Protobuf, Avro, a catalog/registry product, or `contract_version` syntax.
