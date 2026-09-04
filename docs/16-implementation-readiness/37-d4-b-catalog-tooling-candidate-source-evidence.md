# D4-B — Catalog / Registry / Tooling Candidate Source Evidence

**Status:** source evidence only — no catalog product or mechanism selected  
**Axis:** `schema_registry_catalog_and_tooling`  
**Decision:** `OPEN-EVT-003`  
**Canonical base:** `main@df62898b6d9fc36f2a10c0c3713679d2cbe05da8`

## Purpose

This record executes candidate-dependent source evidence for the D4-B Axis B classes accepted by the candidate-evaluation plan:

- `reviewed_git_catalog`;
- `registry_backed_catalog`;
- `hybrid_reviewed_git_plus_registry_catalog`.

`equivalent_reviewed_catalog` remains `insufficient_evidence`.

This PR does **not** select Git-only, a registry product, a hybrid topology, a wire serialization profile, or a `contract_version` representation. It does not add D4-B ledger credit and does not grant D4/Product/Wave4/production authority.

## Authority model

The evidence treats the reviewed logical contract as canonical authority. A registry registration, subject, vendor schema ID, registry version, Git SHA, blob ID or physical storage location may be provenance or mapping metadata, but none of those identifiers becomes logical contract identity.

A registry-backed or hybrid profile is eligible only if publish is downstream of a pre-existing reviewed contract revision. The source harness explicitly rejects an attempt to publish an arbitrary unreviewed `ContractRevision` into the registry mirror.

## Contract identity and immutable history

Logical identity in the evidence fixture is carried independently as domain/name/family. Each reviewed revision binds:

- payload-schema digest;
- semantic-manifest digest;
- reader reference;
- upcaster reference;
- comparison-profile reference;
- reviewed provenance.

The deterministic reviewed-content digest includes the reviewed provenance as well as the semantic/schema/history metadata. Registry publish requires exact equality with the committed reviewed revision, so a caller cannot reuse a valid logical revision while substituting forged provenance.

Revision history is append-only. Reusing an existing logical revision token with different reviewed content fails closed. Historical reader/upcaster/comparison metadata remains attached to the reviewed revision rather than being reconstructed from a vendor registry ID.

## Semantic compatibility, not syntax-only compatibility

The harness contains two revisions with an identical payload schema but a changed semantic manifest. The compatibility result is not `equivalent`; it becomes `semantic_review_required_breaking_until_proven_otherwise`.

This proves the accepted D4-B invariant that schema syntax compatibility alone is insufficient. A catalog/registry compatibility feature cannot silently overrule semantic manifest changes involving authoritative meaning.

## Authentication and authorization

The evidence distinguishes:

- `contract_reader`;
- `contract_reviewer`;
- `registry_publisher`.

Anonymous reads fail closed. Authenticated principals without the required role fail closed. A reader cannot publish registry mappings merely because the contract is readable.

This is evidence-profile behavior only; it does not select an IAM product, protocol or concrete policy engine.

## Tool outage and historical meaning

For registry-backed and hybrid candidates, registry availability is not contract-meaning authority. When the registry surface is unavailable, the same reviewed historical content digest remains resolvable from durable reviewed history. The outage may remove a distribution/index convenience, but it cannot rewrite or silently reinterpret committed history.

The evidence therefore models registry/catalog tooling as replaceable infrastructure around reviewed contract truth, not as the owner of domain semantics.

## Product replacement

The harness mirrors the same reviewed contract revision into two different registry-product fixtures with different product names, subjects, vendor versions and vendor IDs. Their physical mappings differ, but both bind the same reviewed content digest and the same logical contract identity.

This explicitly proves that catalog product identity is not contract identity.

## Candidate outcomes

The allowed result of this source-evidence stage is only:

- `reviewed_git_catalog = eligible_for_evidence_execution`;
- `registry_backed_catalog = eligible_for_evidence_execution`;
- `hybrid_reviewed_git_plus_registry_catalog = eligible_for_evidence_execution`;
- `equivalent_reviewed_catalog = insufficient_evidence`.

`eligible_for_evidence_execution` is not `selected`, `preferred`, `production_ready`, or an authority grant.

## Machine-owned boundaries

`implementation/d4-eventing-async/source-evidence/d4-b-catalog-tooling-candidate-source.json` owns the source-evidence inventory. Assurance pins:

1. all three concrete candidate results;
2. the exact eight Axis B `must_prove` obligations;
3. candidate-specific guard profiles;
4. source assertions, including provenance/content binding;
5. `selection_state=not_selected`;
6. `selection_authority=not_granted`;
7. `current_run_auto_credit=false`;
8. `ledger_credit=[]`;
9. independent Axis A and Axis C selection state;
10. unchanged global D4 authority state.

Negative controls must reject hidden selection, candidate promotion, proof removal, provenance-assertion removal, auto-credit, ledger credit, Product authority escalation, wire-format coupling and `contract_version` coupling.

## Preserved canonical state

After this source evidence, unless a later separately reviewed transition changes it:

- D4-A remains Kafka bounded-C2, 7/7;
- D4-B remains 5/5, `evidence_complete_selection_pending`, candidate `null`;
- Axis A wire serialization selection remains `not_selected`;
- Axis B catalog selection remains `not_selected`;
- Axis C `contract_version` selection remains `not_selected`;
- D4-C/D remain open/unselected/uncredited;
- D4-wide remains 12/26;
- D4 remains `scoped`;
- transport authority remains `selected_not_granted`;
- Product/Wave4 remain `not_granted`;
- production remains `none`;
- C3 remains `not_selected`.

## Exit condition

This source-evidence PR can be accepted only after exact-HEAD CI, adversarial/panoramic review, zero unresolved material threads, mergeability, and separate explicit merge authorization.

A later Axis B **selection** remains a different governed transition. Product-specific registry evaluation, if needed to justify such a selection, must be introduced as separate evidence rather than inferred from this class-level source evidence.
