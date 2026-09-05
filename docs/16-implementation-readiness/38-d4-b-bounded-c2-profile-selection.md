# D4-B — Bounded C2 Contract Profile Selection

## Status

This record governs the transition from **D4-B evidence complete (5/5), selection pending** to a **bounded C2 contract-profile selection**.

Canonical selection base:

- `main@1104997c5bb97aae59373077a9e2f8d7570968b4`

Source decisions:

- `OPEN-EVT-002` — wire serialization and schema language;
- `OPEN-EVT-003` — schema registry / contract catalog tooling;
- `OPEN-EVT-004` — contract-version syntax.

This record supersedes the *OPEN* status of those three decisions at bounded C2 scope. Their original baseline text and all source-evidence manifests remain historical truth and are not rewritten.

## Selected profile

### Axis A — wire serialization by explicit surface

Selected internal broker profile:

- **`protobuf_profile`**

Selected outbound webhook profile, if/when an outbound webhook Product surface is separately authorized:

- **`bounded_json_plus_json_schema_profile`**

The Phase 10 realtime protocol baseline remains its independently accepted bounded canonical JSON profile and is not changed by this decision.

The surface split is deliberate. The accepted D4-B evaluation plan explicitly permits internal broker and external webhook representations to differ when the divergence is explicit, tested and unable to redefine canonical domain meaning.

#### Why Protobuf for the internal broker

The reviewed source evidence showed that the bounded Protobuf profile can satisfy the internal asynchronous contract invariants while providing a compact typed binary representation and preserving explicit forward-compatibility/unknown-field behavior.

The selected profile includes the previously proven guards:

- canonical/minimal varint encoding;
- protected singular-field duplicate rejection;
- selected `oneof` branch authority without runtime inference;
- bounded message/parser work;
- explicit enum/null/required semantics;
- reviewed static schema authority;
- historical schema/profile binding;
- deterministic immutable-content equivalence;
- no dynamic untrusted schema/code loading;
- runtime-language mapping cannot redefine authoritative contract semantics.

This is a serialization/schema profile selection, not permission for generated Protobuf types to become domain models or business authority.

#### Why bounded JSON + JSON Schema for outbound webhooks

External HTTP integrations benefit from an interoperable JSON contract that does not require subscriber-specific binary runtime tooling. The selected profile is **not ordinary permissive JSON**. It inherits the reviewed bounded/canonical controls:

- strict UTF-8 and valid Unicode scalar values;
- duplicate-member rejection before materialization;
- protected alias conflict rejection;
- exact decimal semantics rather than binary-float parser authority;
- bounded bytes/nesting/numeric work;
- deterministic canonical semantic interpretation;
- reviewed static JSON Schema authority;
- no message-selected remote schemas or executable code.

Selecting this representation does **not** create a webhook Product requirement. `OPEN-EVT-021` and the remaining webhook Product/security/numeric decisions stay governed separately.

#### Surface-equivalence rule

The two representations are adapters over the same logical contract. A conversion between them may change representation, never:

- logical contract identity;
- tenant scope;
- message identity;
- contract-version meaning;
- occurrence/causation semantics;
- authoritative payload meaning;
- data classification;
- ordering authority;
- duplicate-sensitive semantic-equivalence result.

A future new surface or serializer requires a separately reviewed profile/equivalence transition. It cannot silently inherit selection merely because a library can parse it.

`avro_profile` remains an evidence-eligible historical alternative but is not selected by this transition.

## Axis B — catalog / registry mechanism

Selected mechanism class:

- **`hybrid_reviewed_git_plus_registry_catalog`**

The authoritative contract history remains the reviewed Git-backed contract package. A registry is a replaceable authenticated/authorized distribution, discovery, compatibility and physical-mapping surface downstream of reviewed authority.

This combines durable review/audit provenance with operational registry ergonomics without making a registry product, subject, vendor version or schema ID become contract identity.

The selected hybrid profile preserves the previously proven rules:

- registry publish requires an exact pre-existing reviewed revision;
- reviewed provenance is content-bound;
- reviewed history is append-only;
- semantic manifest participates in compatibility in addition to payload schema;
- semantic JSON numbers are canonicalized with exact decimal semantics;
- reviewed digest fields are structurally framed rather than delimiter-concatenated;
- historical reader/upcaster/comparison-profile metadata remains recoverable;
- every reviewed-history read is authenticated and authorized;
- registry mapping provenance is immutable/idempotent per reviewed revision;
- registry outage cannot rewrite or reinterpret committed historical meaning;
- registry/vendor/Git/storage identifiers are metadata, not logical contract identity;
- replacing a registry product does not change the logical contract identity.

### Registry product remains unselected

This decision selects the **hybrid mechanism class**, not Confluent Schema Registry, Apicurio, AWS Glue Schema Registry or any other product.

A product-specific registry may become implementation-authorized only through later governed evidence showing that it conforms to the selected hybrid profile. Product identity remains replaceable infrastructure.

`reviewed_git_catalog` and `registry_backed_catalog` remain evidence-eligible historical alternatives but are not selected.

## Axis C — contract-version representation

Selected logical representation:

- **`positive_integer_family_revision`**

A contract version is a positive integer identifying a reviewed semantic contract family/revision. Zero is not a valid contract version.

The selected integer has **equality identity semantics only**. The fact that the representation is numeric does not grant consumers or infrastructure authority to infer:

- compatibility from `<` or `>`;
- deployment ordering;
- API/provider/realtime version ordering;
- registry artifact ordering;
- routing or authorization;
- message identity or tenant scope.

A breaking semantic change cannot reuse an existing integer revision. It requires a newly reviewed revision/family or an explicitly accepted migration.

The same logical positive integer is encoded using the bounded native integer representation of each selected wire profile. String spellings such as `"1"`, leading-zero variants and registry/vendor IDs are not alternate authoritative contract-version representations.

This choice is intentionally simpler than SemVer-like syntax: compatibility is determined by the reviewed semantic manifest and compatibility policy, not inferred from punctuation or a version-number convention. It is also more operator-readable than an opaque token while retaining the rule that version ordering itself is not authority.

`semantic_version_like_contract_revision` and `opaque_monotonic_contract_token` remain evidence-eligible historical alternatives but are not selected.

## Selection is not Product authority

After this transition:

- D4 global gate remains `scoped`;
- D4-A remains Kafka bounded-C2 7/7;
- D4-B remains 5/5 evidence and becomes `selected_candidate` at bounded C2 profile scope;
- D4-C and D4-D remain open, unselected and uncredited;
- D4-wide evidence remains 12/26;
- D4 transport authority remains `selected_not_granted`;
- canonical Product implementation authority remains `not_granted`;
- Wave 4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

Therefore this selection does **not**:

- accept full D4;
- authorize Product/Wave4 implementation;
- create outbound webhooks as a Product feature;
- select a registry vendor;
- authorize production deployment;
- choose production message-size, retention, retry, partition, replay or topology numerics;
- complete D4-C delivery/recovery behavior;
- complete D4-D broker/message security choices.

## Historical truth remains immutable

The Axis A/B/C source manifests intentionally retain:

- `selection_state=not_selected`;
- `selection_authority=not_granted`;
- `current_run_auto_credit=false`;
- `ledger_credit=[]`.

Those values were correct when the evidence was produced. Rewriting them after selection would corrupt provenance.

Current selection authority is represented only by the current D4-B evidence plan/state and `implementation/d4-eventing-async/d4-b-selection-record.json`.

## Replacement governance

A material change to any selected D4-B profile requires a separate governed transition with equivalent-or-stronger evidence for the affected axis and surface.

In particular:

- internal Protobuf -> another serializer requires canonical interpretation, bounded parser, historical-reader and equivalence continuity evidence;
- outbound JSON/JSON Schema -> another external wire profile requires external interoperability plus the same canonical/security properties;
- hybrid catalog -> another catalog mechanism requires preservation of reviewed authority, provenance, history, authz, outage and logical identity properties;
- positive integer contract version -> another representation requires historical family binding and no reinterpretation of retained messages.

A registry product swap inside the selected hybrid mechanism does not by itself require changing logical contracts, but the replacement product must prove conformance before it can receive implementation authority.

## Governed artifacts

Current D4-B selection authority is represented by:

- `implementation/d4-eventing-async/d4-b-selection-record.json`;
- `implementation/d4-eventing-async/d4-b-evidence-plan.json`;
- `implementation/d4-eventing-async/state-manifest.json`;
- `tools/assurance/validate_d4b_selection.py`;
- `tools/assurance/test_validate_d4b_selection.py`;
- `tools/assurance/validate_d4_eventing_async_state.py`;
- `tools/assurance/test_validate_d4_eventing_async_state.py`;
- `.github/workflows/d4-b-profile-selection.yml`.

The source evidence and its exact historical non-selection state remain independently validated by their existing assurance packages.

## Merge and acceptance governance

This selection may merge only after:

1. exact-HEAD CI is clean;
2. D4-B plus related D4 panoramic/adversarial review is clean;
3. all material review threads are resolved;
4. the PR is mergeable;
5. separate explicit user authorization for squash merge is given.

Merging this record still does **not** constitute full D4 acceptance. D4-C/D evidence and a later separate D4 acceptance transition remain required.
