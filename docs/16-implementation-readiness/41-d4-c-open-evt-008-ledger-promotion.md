# D4-C OPEN-EVT-008 ledger promotion — 1/9

Status: **promotion transition only; selection remains open**.

Promotion base: `main@69ad19e6129898e7fdf7e9d57e40a841cb0d4ef5`.

## Source authority

This transition promotes exactly one reviewed source obligation into the D4-C ledger:

- decision: `OPEN-EVT-008`;
- evidence: `ack_after_durable_responsibility_and_lease_ambiguity`;
- source PR: `#72`;
- exact reviewed source HEAD: `02063da13a4a93fe6bc67521e4a7e4e0d4999045`;
- source workflow run: `33948472401`, attempt `1`;
- source job: `101258703919` — `D4-C OPEN-EVT-008 source evidence`;
- source artifact: `9964116208`;
- artifact digest: `sha256:2a7a38caff4ddb6e7740ee079bb0c3cffb2f3e29acacb842ce84c0ab987786d6`;
- source manifest digest: `5c085286b9b6cac8df524f87fa4043accc74cc0878939427abd5df7da16a7708`.

The promotion workflow re-fetches the PR, exact review, workflow run, job and artifact from live GitHub state and verifies the artifact payload and source-manifest digest before admitting credit.

## Ledger transition

Before this transition:

- D4-C = `0/9`;
- D4-wide = `12/26`.

After this transition:

- D4-C = `1/9`;
- D4-C remaining = `8/9`;
- D4-wide = `13/26`.

Only `ack_after_durable_responsibility_and_lease_ambiguity` is credited.

## Temporal interpretation of the candidate-evaluation baseline

The accepted PR #71 candidate-evaluation plan is preserved as an immutable **baseline snapshot** of the moment when D4-C had `0/9` promoted evidence. Its historical cross-axis statement that existing D4-C credit was zero is therefore interpreted at that baseline point in time; it is not a prohibition on later governed promotions.

The live invariant after this transition is stricter and temporal:

- candidate-evaluation runs remain non-promoting and may never auto-credit the D4-C ledger;
- source-evidence runs remain non-promoting and keep `current_run_auto_credit=false` and `ledger_credit=[]`;
- only a separately reviewed promotion transition, bound to exact source HEAD/review/run/job/artifact provenance, may change `evidence_completed`;
- historical validators remain byte-preserved as snapshot oracles and are evaluated against their historical sibling-ledger projection;
- current validators separately require the real current state to be exactly `D4-C=1/9`, `D4-wide=13/26`, with candidate selection still open and all authorities unchanged.

This temporal split prevents both failure modes: rewriting historical truth to match today, and freezing the current ledger forever at the historical `0/9` baseline.

## Non-authority boundary

This promotion does **not** select any D4-C candidate or implementation mechanism. In particular it does not select:

- a concrete ack API;
- a lease/visibility timeout;
- a checkpoint topology;
- a durable inbox storage product/schema;
- a content-equivalence algorithm/profile (`OPEN-EVT-011` remains open);
- a production numeric/topology configuration.

The following remain unchanged:

- D4-C candidate: `null`;
- D4-C candidate status: `not_selected`;
- D4-C state: `candidate_selection_open`;
- D4-D = `0/5`;
- D4 gate = `scoped`;
- transport authority = `selected_not_granted`;
- Product/Wave4 implementation authority = `not_granted`;
- production authority = `none`;
- C3 numeric/topology authority = `not_selected`.

Candidate selection remains a later, separate reviewed transition. Full D4 acceptance remains a separate gate after all tracks reach reviewed terminal C2 disposition with all required evidence complete.
