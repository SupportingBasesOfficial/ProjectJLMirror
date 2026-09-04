# D4-B — Schema / Contract Ledger Promotion

**Status:** proposed reviewed-source ledger promotion — D4-B evidence credit only  
**Promotion base:** `main@4c80d4bf79d9b16d499cfd2f5e723b6dc8a93609`  
**Source PR:** #64  
**Reviewed source HEAD:** `0a5509442d4b55f6d4de989af9bb62a088198ab4`

## Purpose

This change performs the separate ledger action required by the D4-B source-evidence policy. It does not create new schema/serialization evidence and does not select a serialization format, schema catalog/registry product, code-generation stack, or exact `contract_version` syntax.

It promotes exactly the five evidence IDs proven by the already-reviewed D4-B schema/contract source run:

1. `canonical_bounded_serialization_profile`;
2. `parser_ambiguity_and_duplicate_field_negative_vectors`;
3. `schema_catalog_semantic_manifest_compatibility_ci`;
4. `historical_reader_and_equivalence_profile_continuity`;
5. `contract_version_representation_and_breaking_change_vectors`.

After this promotion, D4-B moves from **0/5 to 5/5 evidence credited** and enters `evidence_complete_selection_pending`. Candidate/mechanism selection remains a separate governed transition.

## Exact source provenance

The promoted source is pinned by `implementation/d4-eventing-async/ledger-promotions/d4-b-schema-contract-promotion-v1.json`:

- source PR: `#64`;
- reviewed source HEAD: `0a5509442d4b55f6d4de989af9bb62a088198ab4`;
- independent exact-HEAD adversarial CLEAN review: `5108877160`;
- unresolved material review threads at source closure: `0`;
- workflow run: `33832558443`, attempt `1`;
- workflow job: `100898421033` — `D4-B schema contract source evidence`;
- source artifact ID: `9922185873`;
- artifact name: `d4-b-schema-contract-source-0a5509442d4b55f6d4de989af9bb62a088198ab4-33832558443-1`;
- artifact digest: `sha256:3d8f585ea3e594edc40179a0232c2d00d5133fb652961fa60337dae48b4313dc`;
- source-manifest SHA-256: `2b442fd7b8733105ba004cf7ae982dd3a64a7731d11187b1e0409270f1da118a`.

The final source HEAD completed the exact-HEAD CI gate with 19/19 workflows successful. The fresh exact-HEAD Codex request returned no new finding, and the final independent adversarial review was CLEAN.

## Promotion semantics

The source package remains immutable in meaning and remains explicitly nonpromoting:

- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- `candidate=null`;
- `candidate_status=not_selected`;
- serialization selection `not_selected`;
- schema catalog selection `not_selected`;
- contract-version syntax selection `not_selected`.

That source manifest does not rewrite itself after review. The separate promotion introduces the reviewed ledger state and requires four representations to remain consistent:

1. immutable source manifest bytes;
2. exact source run/job/artifact/review provenance;
3. D4-B evidence-plan ledger state;
4. machine-owned D4 track state.

Any provenance mismatch, source-manifest byte drift, missing or extra credited evidence, candidate selection, or authority escalation fails the promotion assurance gate.

## External provenance revalidation

The D4-B promotion workflow uses read-only GitHub Actions authority to re-read the pinned source run, job and artifact during the promotion PR. It requires:

- exact source run ID, attempt and source HEAD;
- source run `completed/success`;
- exact source job ID/name/run/attempt and `completed/success`;
- exact artifact ID/name/digest;
- artifact not expired;
- artifact bound to the exact source run and source HEAD.

Repository-side validators independently pin the same provenance and source-manifest digest. Workflow metadata alone therefore cannot redirect ledger credit to another source run.

## Selection boundary

Evidence completion is not technology selection. This promotion deliberately leaves all D4-B selection dimensions open:

- D4-B candidate: `null`;
- D4-B candidate status: `not_selected`;
- serialization format: `not_selected`;
- schema catalog/registry technology: `not_selected`;
- exact contract-version syntax: `not_selected`.

No inference may be made from the reference harness that JSON, JSON Schema, Protobuf, Avro or any catalog/registry product is selected.

## Authority boundary

This promotion changes evidence accounting only. The following remain unchanged:

- D4 gate state: `scoped`;
- D4-A: Kafka selected bounded C2 candidate, 7/7 evidence;
- D4 transport authority: `selected_not_granted`;
- canonical Product implementation authority: `not_granted`;
- Wave 4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`;
- D4-C and D4-D: open, candidate-neutral and uncredited.

The D4-wide evidence ledger therefore moves from 7/26 to **12/26**, without D4 acceptance.

## Next governed transition

After this ledger promotion is separately reviewed and merged, D4-B may proceed to a separate candidate/mechanism evaluation and selection transition. That future transition must evaluate candidate serialization/schema-catalog/versioning mechanisms against the already-proven semantic invariants; it must not treat this ledger promotion itself as a technology decision.

## Merge gate

This promotion may merge only after:

- exact-HEAD CI is clean;
- source run/job/artifact provenance revalidation is clean;
- source manifest immutability/nonpromotion is clean;
- D4-B credit is exactly 5/5 and no other track is over-credited;
- panoramic review confirms no selection or authority escalation;
- adversarial review on the exact promotion HEAD is clean, using the documented independent substitution only if Codex is unavailable;
- zero unresolved material review threads remain;
- separate explicit user authorization is given.

Merge credits exactly **5/5 D4-B evidence** and nothing else.
