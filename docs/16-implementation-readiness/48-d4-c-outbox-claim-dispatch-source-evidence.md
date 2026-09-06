# D4-C OPEN-EVT-012 — Outbox Claim / Dispatch / Ack Ambiguity Source Evidence

## Scope

This source-evidence package evaluates the accepted D4-C axis `outbox_claim_dispatch_and_ack_ambiguity` without selecting a candidate and without granting ledger credit.

Canonical source base: `aa36c4dcff1bed03178942ee05b6b8ef1fc03d08`.

The accepted candidate classes are:

- `database_skip_locked_polling_claim_profile`
- `compare_and_swap_lease_claim_profile`
- `notification_assisted_polling_claim_profile`
- separately reviewed equivalent profile, which remains `insufficient_evidence`

## Contract obligations exercised

The executable evidence proves:

1. authoritative business mutation and its required outbox fact commit atomically, with business state snapshotted immutably so caller-side mutation cannot bypass the outbox boundary;
2. claim takeover is fenced so stale owners cannot remain semantic owners, including an already in-flight worker that validated before expiry and a worker preempted after validation but before the broker effect completes;
3. retries preserve immutable fact meaning, including rejection of a coherent post-commit content+digest rewrite;
4. broker ACK ambiguity retries the same message identity and semantic content, while ambiguous or foreign `acked` receipts cannot grant terminal-delivery authority;
5. broker outage preserves committed backlog and an unavailable publish cannot become terminal delivery evidence;
6. dispatcher restart preserves stable message identity/content and notification remains only a wake-up hint;
7. cleanup cannot remove the last recovery authority before terminal evidence plus the safe horizon.

Effectful publish admission re-establishes the current, unexpired claim fence at the broker acceptance boundary. Because database claim authority and broker acceptance are cross-authority, the broker-side evidence model also makes acceptance idempotent for the same stable message identity and immutable content; a post-validation takeover can therefore produce retries/attempts but not a second semantic broker acceptance, and conflicting content for the same message identity fails closed.

Terminal-delivery admission independently re-establishes current, unexpired claim authority when the ACK is consumed. Its write is modeled as a conditional/CAS update over owner, fence, and lease at the commit boundary, so a takeover between method entry and write cannot restore the stale owner's claim or grant terminal evidence. An ACK obtained while the worker was current cannot be used after lease expiry or after takeover. Terminal evidence additionally requires an `acked` receipt bound to the same message identity and content digest as the immutable outbox fact.

The machine validator pins an exact seven-proof / twenty-eight-check inventory so removing business snapshot isolation, post-validation broker idempotence, stale-terminal/CAS fencing, in-flight takeover fencing, receipt binding, or immutability falsification cannot remain green by changing the evaluator alone.

The numeric times and lease durations used by the harness are evidence fixtures only. They do not select production retry, lease, retention, cleanup, partition, or topology numerics.

## Non-authority boundary

This package does **not**:

- select an OPEN-EVT-012 candidate;
- select SQL locking, CAS storage, notification technology, broker behavior, retry numerics, cleanup horizon, or production topology;
- grant OPEN-EVT-012 ledger credit automatically;
- change D4-C from `4/9` or D4-wide from `16/26`;
- grant Product/Wave4/production/C3 authority;
- complete or accept D4.

A separate reviewed ledger-promotion PR remains mandatory after this source evidence is independently accepted and merged.
