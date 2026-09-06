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

1. authoritative business mutation and its required outbox fact commit atomically, with business state recursively snapshotted and mapping keys restricted to exact supported built-in immutable scalar types;
2. claim takeover is fenced so stale owners cannot initiate a broker handoff after losing authority, while a takeover that occurs only after a valid handoff has already crossed the authority boundary is treated as delivery ambiguity rather than retroactive cancellation;
3. retries preserve immutable fact meaning, including rejection of a coherent post-commit content+digest rewrite;
4. broker ACK ambiguity retries the same message identity and semantic content, while ambiguous, foreign, or conflicting-content evidence cannot grant terminal meaning;
5. broker outage preserves committed backlog and an unavailable publish cannot become terminal delivery evidence;
6. dispatcher restart preserves stable message identity/content and notification remains only a wake-up hint;
7. cleanup cannot remove the last recovery authority before terminal evidence plus the safe horizon.

The database claim and broker acceptance are distinct authorities. This package therefore does **not** claim an impossible distributed atomic transaction between them. Before the broker handoff begins, the dispatcher revalidates current, unexpired claim authority. If authority is lost before that handoff, the publish is rejected. If authority is lost only after the broker call is already in flight, the broker outcome is uncertain from the claim authority's perspective: the call cannot be retroactively cancelled and its eventual ACK does not restore current claim authority.

That post-handoff ambiguity is contained by stable message identity and immutable content plus a broker-side atomic idempotent acceptance operation. Lookup, conflict decision, stable message-ID/content insertion, and semantic acceptance are serialized together. Concurrent same-ID/same-content attempts collapse to one semantic acceptance, while same-ID/different-content fails closed. A stale worker's resulting ACK cannot grant terminal-delivery or cleanup authority; only the current, unexpired claim may consume a matching ACK into terminal evidence.

Terminal-delivery admission independently re-establishes current, unexpired claim authority when the ACK is consumed. The modeled terminal transition serializes owner/fence/lease comparison, transformation, final comparison, and state replacement inside one conditional commit boundary. A concurrent takeover cannot be overwritten by the stale worker, and an ACK obtained while current cannot be reused after lease expiry or takeover. Terminal evidence additionally requires an `acked` receipt bound to the same message identity and content digest as the immutable outbox fact.

Authoritative business state is detached from caller aliases. Supported nested values are recursively frozen; mapping keys must be exact built-in supported immutable scalar types. Mutable/hashable objects and mutable subclasses of supported `str`, `int`, and `float` keys are rejected before the business/outbox commit.

The machine validator pins an exact seven-proof / thirty-three-check semantic inventory. In addition, it runs independent adversarial probes outside the evaluator result map for synchronized same-ID/different-content broker races and mutable subclasses of every supported subclassable scalar key type (`str`, `int`, `float`). These probes complement the semantic inventory and prevent evaluator/test co-editing from making those broader guarantees green for the wrong reason. Together the suite also covers pre-handoff fencing, post-handoff ambiguity containment, concurrent same-content broker deduplication, terminal-write serialization, business snapshot isolation, stale-terminal fencing, receipt binding, and immutable-fact protection.

The numeric times, thread counts, sleeps, and lease durations used by the harness are evidence fixtures only. They do not select production retry, lease, retention, cleanup, partition, concurrency, or topology numerics.

## Non-authority boundary

This package does **not**:

- select an OPEN-EVT-012 candidate;
- select SQL locking, CAS storage, notification technology, broker behavior, retry numerics, cleanup horizon, or production topology;
- create a cross-authority transaction between the durable store and broker;
- grant OPEN-EVT-012 ledger credit automatically;
- change D4-C from `4/9` or D4-wide from `16/26`;
- grant Product/Wave4/production/C3 authority;
- complete or accept D4.

A separate reviewed ledger-promotion PR remains mandatory after this source evidence is independently accepted and merged.
