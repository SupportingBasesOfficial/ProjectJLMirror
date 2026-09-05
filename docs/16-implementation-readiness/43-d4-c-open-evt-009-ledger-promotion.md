# D4-C OPEN-EVT-009 ledger promotion

Status: **reviewed source evidence promotion only; no candidate selection and no implementation authority**.

Promotion base: `main@a238c82b8ddd4084b3ae80786e0e75b39111132e`.

## Transition

This governed transition promotes exactly one previously reviewed D4-C evidence obligation:

- decision: `OPEN-EVT-009`;
- evidence: `quarantine_redrive_current_authority_and_dedup_preservation`;
- D4-C ledger: `1/9 -> 2/9`;
- D4-wide ledger: `13/26 -> 14/26`.

OPEN-EVT-008 remains the first independently promoted D4-C credit. Its immutable promotion record is retained and revalidated; this transition does not rewrite or replace that history.

## Reviewed source binding

The second credit is bound to the separately merged source PR #74:

- reviewed source HEAD: `f3c5e49828160abde9fd99b25688456fa13408df`;
- source squash on main: `a238c82b8ddd4084b3ae80786e0e75b39111132e`;
- independent exact-HEAD review id: `5123104259`;
- source workflow id: `351163085`;
- source run: `33992605858`, attempt `1`;
- source job: `101377381065` (`D4-C OPEN-EVT-009 source evidence`);
- source artifact: `9977118464`;
- artifact digest: `sha256:680d0d965b965c7f44b4474a7725b3e6c23e143af8ed34f41aa37a0bbbdabaa1`;
- source manifest SHA-256: `2e03e9a7ade9f6c379953b44ce7778846272948c30cd27336cb0c06f18483ddc`.

The promotion gate admits the live source run/artifact only when the pull request changes D4-C evidence-promotion authority. On later steady-state runs it validates durable promotion records and source digests without requiring the 90-day artifact to remain available.

## Evidence meaning retained

Promotion means only that the reviewed source evidence is now credited against the D4-C obligation. It preserves the source semantics already proven by PR #74, including:

- platform quarantine truth is independent of broker-native DLQ identity;
- retry exhaustion is governed and non-regressive;
- current redrive authority is actor-, tenant- and classification-scoped;
- tenant authority is distinct from consumer message identity scope;
- redrive cannot bypass deduplication, equivalence or reconciliation;
- conflicting immutable content fails closed;
- ambiguous external effects require reconciliation;
- broker replacement cannot rewrite platform quarantine process truth.

This promotion does **not** make the SQLite harness, SHA-256 fixture, retry fixture values, broker metadata representation, storage schema, IAM model or any test mechanism a production selection.

## Authority boundary

After this promotion the required state is exactly:

- D4-A `7/7`;
- D4-B `5/5` selected bounded C2 profile;
- D4-C `2/9`, candidate `null`, `not_selected`, `candidate_selection_open`;
- D4-D `0/5`;
- D4-wide `14/26`;
- D4 gate `scoped`;
- transport authority `selected_not_granted`;
- Product implementation authority `not_granted`;
- Wave4 implementation authority `not_granted`;
- production authority `none`;
- C3 numeric/topology authority `not_selected`.

A third D4-C credit is forbidden by this transition. Candidate selection and full D4 acceptance remain separate future governed actions. Merge still requires separate explicit user authorization after an exact-HEAD CLEAN gate.
