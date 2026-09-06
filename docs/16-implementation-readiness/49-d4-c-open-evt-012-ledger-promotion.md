# D4-C OPEN-EVT-012 Ledger Promotion

## Scope

This governed transition promotes exactly one already-reviewed D4-C source-evidence obligation:

- decision: `OPEN-EVT-012`;
- evidence: `outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity`;
- source PR: `#80`;
- exact reviewed source HEAD: `72bce1b28bce98425f486370b4d887e04c769091`;
- source squash merge: `077efd6d582fddf3e316cad5bdf03887ef08ace5`.

No candidate selection, implementation authority, production authority, C3 numeric/topology selection, broker/runtime choice, retry numeric, outbox schema, claim SQL, lease duration or deployment topology is introduced by this transition.

## Exact source provenance

- final exact-head review: `5124079168`;
- source workflow id: `351286755`;
- source workflow run: `34010311086`, attempt `1`;
- source job: `101424854557` — `D4-C OPEN-EVT-012 source evidence`;
- artifact: `9982251234`;
- artifact name: `d4-c-outbox-claim-dispatch-source-72bce1b28bce98425f486370b4d887e04c769091-34010311086-1`;
- artifact digest: `sha256:c15c57c7bb02a87a9dfaf0b779efb16a126f6919618235c48763d23acb4a794d`;
- source manifest: `implementation/d4-eventing-async/source-evidence/d4-c-outbox-claim-dispatch-source.json`;
- source-manifest SHA-256: `7737b26e9cf83c41328f18bf62d84199abef3e4ca6c0b51b37e2ecd86ec2c8d2`.

The promotion gate must re-fetch the source PR, exact-head review, workflow run, job and artifact from live GitHub state and must validate the immutable source-manifest bytes before admitting the credit.

## Governed state transition

Before this transition:

- D4-A: `7/7`;
- D4-B: `5/5`;
- D4-C: `4/9`;
- D4-D: `0/5`;
- D4-wide: `16/26`.

After this transition, if accepted:

- D4-A: `7/7`;
- D4-B: `5/5`;
- D4-C: `5/9`;
- D4-D: `0/5`;
- D4-wide: `17/26`.

Exactly one credit is added. Historical promotion records for `OPEN-EVT-008` through `OPEN-EVT-011` remain immutable.

## Source-time truth versus current ledger truth

The source manifest from PR #80 remains immutable historical evidence. It correctly records that the source run itself used `current_run_auto_credit=false`, `ledger_credit=[]`, and observed D4-C at `4/9`.

This promotion does not rewrite that history. Instead, a separate promotion record grants the fifth ledger credit after the source package has been independently reviewed and merged.

## Authority boundary

The transition preserves all existing non-authority boundaries:

- D4-C candidate: `null`;
- D4-C candidate status: `not_selected`;
- D4-C state: `candidate_selection_open`;
- selection authority: `not_granted`;
- D4 gate: `scoped`;
- transport authority: `selected_not_granted`;
- Product implementation authority: `not_granted`;
- Wave 4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

Candidate selection and full D4 acceptance remain separate later governed transitions.

## Merge gate

Merge requires all of the following on one exact final HEAD:

1. promotion provenance record exactly matches the accepted source evidence;
2. live GitHub source-provenance admission passes;
3. D4-C cumulative validator and falsification suite pass at exactly `5/9`;
4. global D4 validator and falsification suite pass at exactly `17/26`;
5. all applicable pull-request workflows complete successfully;
6. no unresolved material review thread remains;
7. fresh exact-head adversarial/panoramic review is clean;
8. separate explicit user authorization is given.

A green workflow, absence of reviewers, or this document does not itself authorize merge.
