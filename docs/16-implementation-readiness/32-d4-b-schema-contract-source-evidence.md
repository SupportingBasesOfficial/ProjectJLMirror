# D4-B — Schema / Contract Source Evidence

**Track:** D4-B — serialization, schema catalog and contract versioning  
**Canonical base:** `main@790f967446bf039ba4d5f618c9f30494c720ee7c`  
**Status:** source evidence only; no selection, no ledger credit, no D4 acceptance

## Purpose

This package establishes a deterministic first-party reference harness for the five D4-B evidence requirements without selecting the final wire serialization, schema registry/catalog product, code-generation stack, or exact `contract_version` syntax.

The reference harness exists to make the semantic invariants executable before a technology choice can become canonical.

## Evidence exercised

1. `canonical_bounded_serialization_profile`
   - one bounded structured interpretation;
   - deterministic canonical semantic bytes for equality/testing;
   - explicit depth/member/array/string/wire bounds.

2. `parser_ambiguity_and_duplicate_field_negative_vectors`
   - duplicate members rejected;
   - malformed UTF-8/structured representation rejected;
   - excessive depth, members, arrays and strings rejected.

3. `schema_catalog_semantic_manifest_compatibility_ci`
   - deterministic semantic manifest independent of field declaration order;
   - compatibility evaluates semantic required/null/type/enum/equivalence-profile changes, not just raw schema text.

4. `historical_reader_and_equivalence_profile_continuity`
   - historical reader presence is required for compatibility evidence;
   - comparison/equivalence profile is explicit and version-bound;
   - profile change is treated as semantic compatibility work, not an invisible implementation detail.

5. `contract_version_representation_and_breaking_change_vectors`
   - reference-only bounded version token is exercised without selecting OPEN-EVT-004 syntax;
   - breaking semantic changes require either a new incompatible contract version/family or an accepted equality-preserving migration.

## Selection boundary

This PR deliberately keeps:

- D4-B `candidate=null`;
- D4-B `candidate_status=not_selected`;
- wire serialization selection `not_selected`;
- schema catalog/registry tooling selection `not_selected`;
- exact contract-version syntax selection `not_selected`;
- D4-B ledger credit empty.

The reference model is **not** a declaration that JSON, JSON Schema, Protobuf, Avro, a registry product, or a particular version-string syntax has been selected. It is a falsifiable semantic baseline against which candidates can be evaluated.

## Existing authority remains unchanged

D4-A remains the already selected bounded Kafka C2 candidate with 7/7 evidence. D4 itself remains `scoped`; transport authority remains `selected_not_granted`; Product/Wave4 implementation remains `not_granted`; production remains `none`; C3 numeric/topology remains `not_selected`; D4-C/D remain open.

## Promotion and selection

A successful source run produces exact SHA/run/job provenance but grants no ledger credit. Any D4-B evidence promotion and any serialization/catalog/version-syntax selection require separately reviewed governed transitions on exact reviewed HEADs.
