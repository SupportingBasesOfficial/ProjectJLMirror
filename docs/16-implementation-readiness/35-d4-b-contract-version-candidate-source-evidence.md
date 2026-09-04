# D4-B — Contract-Version Candidate Source Evidence

**Status:** source evidence only — no D4-B selection, no canonical syntax selection, no ledger promotion  
**Canonical base:** `main@a871ac9c0ce7f33cf06fb70246bb902aff82900f`  
**Track:** D4-B / Axis C — `OPEN-EVT-004`

## Purpose

This package executes the first candidate-dependent D4-B evidence after acceptance of the three-axis evaluation plan. It evaluates the three concrete `contract_version` representation classes without choosing among them and without coupling the result to wire serialization or schema catalog tooling.

```text
TEST FIXTURE SYNTAX != CANONICAL SYNTAX
ELIGIBLE FOR EVIDENCE != SELECTED
SOURCE EVIDENCE != LEDGER CREDIT
AXIS C RESULT != AXIS A/B CHOICE
D4-B RESULT != D4 ACCEPTANCE
```

## Evaluated concrete candidate classes

The executable harness evaluates:

1. `positive_integer_family_revision`;
2. `semantic_version_like_contract_revision`;
3. `opaque_monotonic_contract_token`.

The abstract `equivalent_reviewed_representation` class remains `insufficient_evidence` because no concrete equivalent candidate has been supplied. It cannot receive positive evidence by abstraction alone.

Each concrete candidate currently reaches only `eligible_for_evidence_execution`. This result means the class can satisfy the bounded Axis C contract under the exercised evidence fixture. It does **not** mean preferred, selected, canonical, production-ready, or implementation-authorized.

## Test-fixture boundary

The harness necessarily uses concrete strings to exercise parser behavior. Those strings are noncanonical source-evidence fixtures only.

The fixture profiles intentionally prove:

- one deterministic bounded parse per candidate;
- rejection of ambiguous/noncanonical alternatives;
- the opaque-monotonic candidate uses a strictly increasing and explicitly bounded internal issuance sequence while emitting externally opaque tokens;
- the opaque fixture mapping is a deterministic bijection across the bounded uint64 evidence domain, so distinct issuance sequences cannot collide inside the fixture;
- equality-only comparison surface;
- no ordering authority;
- no tenant, authorization, routing or message-identity authority emitted from version parsing;
- separation from deployment/API/provider/realtime/registry version namespaces;
- breaking semantic change cannot reuse the same version **within each candidate family**;
- historical evidence retains both the original candidate family and original version bytes;
- a historical value cannot be reinterpreted through a different candidate-family adapter.

Merging this package therefore does **not** select integer syntax, semantic-version syntax, opaque-token syntax, widths, prefixes, separators, ordering rules, issuance implementation or production storage representation.

## Opaque monotonicity without public ordering

The opaque candidate has two distinct properties and the harness tests both:

1. its **issuance authority** receives an internal sequence that must increase strictly, stay inside the bounded evidence range and reject replay/repeat/decrement/overflow;
2. the resulting external token is treated as opaque and supports equality only.

For the evidence fixture, the bounded internal uint64 sequence is transformed through an affine permutation with an odd multiplier, which is bijective modulo `2^64`, and then encoded as an opaque test token. This removes probabilistic collision assumptions from the harness. It is not a production token-generation selection, cryptographic security claim or public ordering profile.

The internal sequence is not emitted as canonical message semantics and the external token does not gain `<`, `>`, range, routing or upgrade authority.

## Historical meaning is family-bound

Historical continuity is not represented by a byte copy alone. The evidence record binds:

- candidate-family identity;
- original version bytes.

The original adapter must reproduce the exact historical value, while an attempt to restore that historical value through another candidate-family adapter fails closed. This prevents a retained value such as `1`, `1.0.0` or an opaque token from silently acquiring new meaning merely because a later runtime uses another representation family.

The breaking-change guard is also exercised independently inside all three candidate families: reusing the same canonical version for a breaking semantic change fails; transitioning to another valid value succeeds. This remains an evidence rule, not a selected production migration policy.

## Why ordering is deliberately absent

All three candidate classes are exercised through equality semantics only. Even when a test value looks numeric, semantic-version-like or is produced by monotonic issuance, the source profile exposes no `<`, `>`, range, upgrade or routing authority.

That is deliberate because the accepted Axis C invariant says ordering is not assumed unless a later selected profile explicitly grants and governs it. A convenient lexical/numeric interpretation must not silently become canonical contract semantics.

## Negative controls

The source falsification suite rejects:

- additive hidden `candidate` selection;
- duplicate JSON members hiding conflicting selection state;
- `canonical_contract_version_syntax_selected=true`;
- D4-B selection or selection-authority grant;
- source-run auto-credit or non-empty `ledger_credit`;
- promoting a candidate result to `selected`;
- pretending an unevaluated equivalent class is eligible;
- removing required proofs, the opaque-monotonic issuance assertion, the collision-free fixture assertion or the historical-family continuity assertion;
- non-increasing/replayed/overflow opaque issuance sequence;
- cross-family historical reinterpretation;
- D4-B ledger selection mutation;
- full-D4/Product/Wave4/production/C3 authority escalation;
- ordering authority or non-version authority fields exposed by a candidate adapter.

## Existing D4 state remains immutable

This source package does not modify the accepted D4 ledger/state:

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

This source PR may be accepted only after exact-HEAD CI, adversarial/panoramic review and zero unresolved material threads prove that the executable harness and manifest are bounded, non-selecting and non-authoritative.

After acceptance, the next D4-B source-evidence work should evaluate Axis A and/or Axis B candidate behavior. A later selection transition must consider reviewed evidence across the relevant axes and remains a separate governed action requiring explicit authorization.
