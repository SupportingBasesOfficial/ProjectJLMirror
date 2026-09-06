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

1. authoritative business mutation and its required outbox fact commit atomically;
2. claim takeover is fenced so stale owners cannot remain semantic owners;
3. retries preserve immutable fact meaning;
4. broker ACK ambiguity retries the same message identity and semantic content;
5. broker outage preserves committed backlog;
6. dispatcher restart preserves stable message identity/content and notification remains only a wake-up hint;
7. cleanup cannot remove the last recovery authority before terminal evidence plus the safe horizon.

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
