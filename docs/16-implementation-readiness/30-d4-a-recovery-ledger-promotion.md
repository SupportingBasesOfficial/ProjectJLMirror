# D4-A — Recovery Ledger Promotion to Seven of Seven

**Status:** proposed ledger promotion only  
**Canonical base:** `main@9fdf02dd7841ac9f4f28610759af751096057264`  
**Track:** D4-A  
**Transition:** `six_of_seven` → `seven_of_seven`

## Purpose

This change promotes the already reviewed source evidence for the final D4-A obligation into the machine-owned evidence ledger:

`broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark`

The promotion completes the D4-A evidence inventory. It does **not** select Kafka, accept D4-A as a transport decision, accept D4 as a gate, grant implementation authority or create production/C3 numeric authority.

The resulting state is deliberately:

- D4-A evidence: complete, 7/7;
- Kafka: leading candidate, **not selected**;
- D4-A selection: pending a separate governed decision;
- D4 gate: `scoped`;
- D4-B/D4-C/D4-D: still open;
- D4 transport authority: `not_selected_not_granted`;
- Product/Wave 4 authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

## Promoted source authority

The promotion is pinned to the final reviewed source run from PR #61:

- source PR: `61`;
- reviewed source HEAD: `40820f543c064c976b0e1443a227120a5577d36b`;
- source squash/main commit: `9fdf02dd7841ac9f4f28610759af751096057264`;
- workflow run: `33824087573`;
- run attempt: `1`;
- workflow job: `100872898415` — `D4-A recovery source evidence`;
- artifact: `9919338891`;
- artifact name: `d4-a-recovery-source-40820f543c064c976b0e1443a227120a5577d36b-33824087573-1`;
- artifact digest: `sha256:e0d5c4990627533408201ca6b50895c9272c4a0298acd0458b4813295c1731de`;
- exact-HEAD CI: 18/18 SUCCESS;
- independent exact-HEAD review: `PRR_kwDOT7x07M8AAAABMHlhng`;
- fresh Codex exact-HEAD review: `PRR_kwDOT7x07M8AAAABMHl-Kw`;
- final source gate comment: `5534198183`;
- unresolved material threads: `0`.

The source package itself remains immutable historical evidence with `current_run_auto_credit=false` and `ledger_credit=[]`. Credit comes only from this separate promotion.

## Source evidence proven

The admitted source artifact proves, against the immutable Kafka 4.3.1 bounded candidate pin:

1. a real broker stop/start outage occurs;
2. committed durable outbox rows survive broker unavailability, database close/reopen and broker restart;
3. the complete backlog drains;
4. protected/current work injected during recovery does not starve behind historical backlog;
5. the executed anti-starvation bound is at most three backlog dispatches before protected delivery;
6. one intentionally acknowledgement-ambiguous publish is retried with the same logical `message_id` and immutable meaning;
7. Kafka broker progress exists while business-effect count is still zero;
8. consumer inbox/effect admission creates exactly one business effect per unique logical message and suppresses the deliberate identical duplicate;
9. bounded benchmark values remain test-only and do not become production numerics.

The earlier panoramic finding for an unused `dispatcher_batch_limit` was closed by removing the non-executed declaration, leaving only the anti-starvation bound that the runtime actually measures.

## Admission-time live artifact verification

When this promotion changes D4-A authority projection, the D4-A promotion workflow must verify the source run from live GitHub evidence before admitting the new ledger state.

The gate verifies:

- workflow run/attempt/HEAD and SUCCESS result;
- exact workflow job identity and SUCCESS result;
- artifact ID/name/digest and non-expired state;
- artifact content inventory;
- source-run provenance schema and exact source SHA;
- source-manifest and benchmark-result digests;
- recovery runtime assertions listed above;
- source `ledger_credit=[]` and `current_run_auto_credit=false`;
- independent and Codex reviews anchored to the reviewed source HEAD;
- final gate comment existence.

This is an admission-time requirement because GitHub Actions artifact retention is temporary.

## Durable steady-state provenance

After promotion admission, repository steady-state does not depend forever on the external artifact remaining downloadable.

The promotion record cryptographically links:

`recovery promotion → capacity/ordering promotion → data/topology promotion → semantic-boundary promotion`

and every promotion record links to the exact source-manifest bytes that justified its credit.

The D4-A validator recursively walks this chain and fails if any historical promotion record or promoted source manifest no longer matches its pinned SHA-256 digest. Byte-level negative controls exercise historical-chain tampering.

Live-artifact verification is reactivated only when the D4-A authority projection changes; unrelated D4-B/C/D state evolution must not turn temporary artifact retention into a permanent repository dependency.

## Evidence completion is not selection

Seven of seven means exactly:

> every evidence class required by the D4-A evidence plan has reviewed ledger credit.

It does **not** mean:

- Kafka is selected;
- `OPEN-EVT-001`/`OPEN-REL-012.A` is canonically closed;
- D4 transport authority is granted;
- the full D4 gate is accepted;
- D4-B/C/D are complete;
- production topology/partition/retry/retention numerics are selected;
- Product or Wave 4 implementation may begin solely because of this promotion.

The machine-owned states therefore use explicit `evidence_complete_selection_pending` / `leading_candidate_evidence_complete_selection_pending` wording rather than overloading `selected` or `accepted`.

## Resulting machine-owned state

After this promotion is accepted and merged:

- `d4-a-evidence-plan.json` must report `ledger_credit_state=seven_of_seven`;
- all seven exact evidence IDs must be in `credited_evidence`;
- `selection_state=not_selected`;
- `acceptance_state=evidence_complete_separate_acceptance_required`;
- `latest_promotion_record` must point to `d4-a-recovery-promotion-v1.json`;
- D4-A `evidence_completed` must equal all seven required IDs;
- D4-A `evidence_remaining` must be empty;
- D4-A state must be `evidence_complete_selection_pending`;
- D4 itself must remain `scoped`;
- all non-authority boundaries must remain unchanged.

## Next governed step

After this promotion is merged, the next D4-A action is a **separate selection/acceptance decision** that evaluates whether the now-complete evidence justifies canonically selecting Kafka for the bounded D4-A transport decision.

That later action must not be smuggled into this promotion. It requires its own exact-HEAD review, gate and explicit authorization. Full D4 acceptance remains impossible until D4-B, D4-C and D4-D also reach reviewed terminal C2 dispositions with their own required evidence.
