# D4-C OPEN-EVT-011 — Scoped Content Equivalence Source Evidence

## Status

This package is **candidate source evidence only** for D4-C axis `scoped_content_equivalence_authority` and evidence id `scoped_content_equivalence_confidentiality_and_conflict_rejection`.

Canonical source base: `main@3ee199dea84893571f09e20bfefdaa2903725450`.

It does **not** select a D4-C candidate, grant ledger credit, grant implementation authority, choose a production digest/key store/database/effect mechanism, or accept D4.

Current governed state remains:

- D4-A: 7/7, bounded Kafka C2 mechanism selected;
- D4-B: 5/5, bounded C2 contract profile selected;
- D4-C: 3/9, candidate `null`, `not_selected`, `candidate_selection_open`;
- D4-D: 0/5;
- D4-wide: 15/26;
- D4 gate: `scoped`;
- transport authority: `selected_not_granted`;
- Product/Wave4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

## Contract discrimination

The source harness deliberately does not make every named candidate pass.

`canonical_collision_resistant_fingerprint_profile` is `ineligible_by_contract` because an unkeyed deterministic fingerprint over low-entropy confidential immutable content creates an offline dictionary/cross-scope equality oracle. A collision-resistant hash is not sufficient confidentiality authority.

The following are eligible for evidence execution only when all obligations pass:

- `keyed_authenticated_digest_profile` — scope-separated authenticated evidence;
- `protected_retained_immutable_original_profile` — protected canonical original with comparison access control;
- `hybrid_equivalence_authority_profile` — scope-separated authenticated evidence plus protected retained original.

`equivalent_reviewed_profile` remains `insufficient_evidence` until independently instantiated and tested.

## Evidence semantics

The harness proves that deduplication identity and content equivalence are different authorities. The dedup key is `(consumer_contract, trusted_message_identity_scope, message_id)`. Trusted contract/scope admission occurs before semantic comparison work. Reusing a scoped identity is benign only when durable, verifiable equivalence evidence proves identical immutable semantic meaning.

All immutable fields required for same-id meaning are projected through one deterministic structured interpretation. The same canonical bytes feed protected contract interpretation and comparison evidence. Mutating any required immutable field under the same scoped identity is an integrity conflict and fails closed.

Missing evidence, inaccessible comparison evidence, unknown historical profile versions, or profile mismatch are uncertainty states. They never collapse to duplicate success.

## Confidentiality and authority separation

Low-entropy confidential content must not create a cross-scope equality oracle. Keyed profiles derive scope-separated authenticated evidence. Protected-original comparison exposes no comparison token without explicit comparison access.

Equivalence records do not carry authorization, routing, ordering, placement, or bearer authority. A matching digest/original is evidence of content equality only.

The fixture secrets, byte bound, profile names, operation ids, and algorithms are assurance fixtures. They are not production selections.

## Effect safety and history

Co-resident inbox/effect completion is modeled as one atomic outcome: an effect failure cannot leave a committed inbox equivalence record.

Cross-authority effects use a stable operation identity and durable result reconciliation. A retry cannot replace the authoritative result merely because a repeated message is observed.

Historical profile versions remain explicitly interpretable. Equality-preserving migration must preserve the comparison authority before an older profile can be retired. Payload erasure is refused when it would remove the last required equivalence authority; a hybrid profile may erase the retained original only when independent authenticated equality evidence remains.

## Bounded verification

Comparison requires explicit comparison access and operates under a noncanonical evidence-fixture byte bound. Oversized canonical semantic material fails closed and non-retryably. This bound is evidence-only and does not select a production numeric limit.

## Required outcome

The dedicated workflow must emit immutable provenance for the exact analyzed HEAD and must preserve all non-authority boundaries. Source success only establishes candidate classification for future governed evidence work. A separate ledger-promotion PR and separate authorization are required before OPEN-EVT-011 can become the fourth D4-C credit.
