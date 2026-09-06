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

1. authoritative business mutation and its required outbox fact commit atomically, with business state recursively snapshotted and unsupported mutable mapping-key objects rejected before commit;
2. claim takeover is fenced so stale owners cannot remain semantic owners, including workers preempted before broker acceptance, after authorization, and while terminal delivery is being committed;
3. retries preserve immutable fact meaning, including rejection of a coherent post-commit content+digest rewrite;
4. broker ACK ambiguity retries the same message identity and semantic content, while ambiguous, foreign, or conflicting-content evidence cannot grant benign/terminal meaning;
5. broker outage preserves committed backlog and an unavailable publish cannot become terminal delivery evidence;
6. dispatcher restart preserves stable message identity/content and notification remains only a wake-up hint;
7. cleanup cannot remove the last recovery authority before terminal evidence plus the safe horizon.

Effectful publish admission re-establishes the current, unexpired claim fence at the broker acceptance boundary. Database claim authority and broker acceptance remain cross-authority; therefore the broker-side evidence model provides an atomic idempotent acceptance operation whose lookup, conflict decision, stable message-ID/content insertion, and semantic acceptance are serialized together. Concurrent same-ID/same-content publishes collapse to one semantic acceptance, while same-ID/different-content fails closed.

Terminal-delivery admission independently re-establishes current, unexpired claim authority when the ACK is consumed. The modeled terminal transition serializes owner/fence/lease comparison, transformation, final comparison, and state replacement inside one conditional commit boundary. A concurrent takeover cannot be overwritten by the stale worker, and an ACK obtained while current cannot be reused after lease expiry or takeover. Terminal evidence additionally requires an `acked` receipt bound to the same message identity and content digest as the immutable outbox fact.

Authoritative business state is detached from caller aliases. Supported nested values are recursively frozen; mapping keys are limited to supported immutable scalar keys, while arbitrary mutable/hashable key objects are rejected before the business/outbox commit.

The machine validator pins an exact seven-proof / thirty-two-check inventory. It independently requires concurrent broker atomicity, conflicting-content rejection, concurrent terminal-write serialization, mutable-key rejection, business snapshot isolation, stale-terminal fencing, receipt binding, in-flight takeover fencing, and immutable-fact protection, so removing those guards cannot remain green by changing the evaluator alone.

The numeric times, thread counts, sleeps, and lease durations used by the harness are evidence fixtures only. They do not select production retry, lease, retention, cleanup, partition, concurrency, or topology numerics.

## Non-authority boundary

This package does **not**:

- select an OPEN-EVT-012 candidate;
- select SQL locking, CAS storage, notification technology, broker behavior, retry numerics, cleanup horizon, or production topology;
- grant OPEN-EVT-012 ledger credit automatically;
- change D4-C from `4/9` or D4-wide from `16/26`;
- grant Product/Wave4/production/C3 authority;
- complete or accept D4.

A separate reviewed ledger-promotion PR remains mandatory after this source evidence is independently accepted and merged.
