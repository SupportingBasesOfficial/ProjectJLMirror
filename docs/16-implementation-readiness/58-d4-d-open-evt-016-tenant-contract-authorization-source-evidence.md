# D4-D OPEN-EVT-016 — Tenant/Contract Producer/Consumer Authorization Source Evidence

## Scope

This package provides source evidence for the D4-D axis `tenant_and_contract_scoped_producer_consumer_authorization` derived from OPEN-EVT-016.

It is intentionally non-promoting. It does not credit the D4-D ledger, select a D4-D candidate, grant selection authority, or change D4/Product/Wave4/production/C3 authority.

## Source-time boundary

Canonical source base: `9f20d9238407589eb3882bd08647cdf36e8cc6f5`.

At source time:

- D4-A: 7/7 selected;
- D4-B: 5/5 selected;
- D4-C: 9/9, candidate unselected;
- D4-D: 1/5, candidate unselected;
- D4-wide: 22/26;
- D4 remains scoped;
- `current_run_auto_credit=false`;
- `ledger_credit=[]`.

## Authority model under test

Broker producer/consumer authorization is a projection of current platform authority. Broker ACLs, policy-engine identities, scoped broker credentials, topics, groups, queues, or subscriptions do not become platform tenant authority.

The evidence model binds a broker projection to:

- exact tenant;
- exact service;
- exact domain;
- exact producer or consumer role;
- exact contract;
- exact current platform authorization generation.

The projection is invalid when platform authority is revoked, stale, cross-tenant, cross-service/domain, wildcard/broad, or outside the current contract allowlist.

## Must-prove obligations

1. producer authorization is contract-scoped and least privilege;
2. consumer authorization is constrained by service, domain, and tenant;
3. broker ACL/policy identity does not replace platform tenant authority;
4. cross-tenant produce and consume attempts fail closed;
5. authorization revocation or generation change blocks stale broker access;
6. wildcard or broad broker permissions cannot bypass contract scope;
7. authorization projection is reconcilable from current platform authority.

## Executable probes

The harness exercises positive producer/consumer projections and negative cases for:

- cross-tenant produce;
- cross-tenant consume;
- producer contract outside authority;
- consumer contract outside authority;
- stale authorization generation;
- revoked current authority;
- wildcard requested contract;
- broad wildcard platform grant;
- service mismatch;
- domain mismatch;
- stale projection after authority generation change;
- reconciliation to the new current generation;
- removal of a contract on reconciliation.

## Governance invariants

A successful source run proves only that the source package satisfies the axis contract. It does not promote `tenant_and_contract_scoped_producer_consumer_authorization` into `evidence_completed`.

A future promotion must independently bind the exact reviewed source HEAD, workflow run/attempt, job, uploaded provenance artifact and digest, source-manifest digest, and exact promotion base before D4-D may move from 1/5 to 2/5.

Candidate selection remains a separate gate after evidence execution. Full D4 acceptance remains separate after all tracks satisfy their own requirements.
