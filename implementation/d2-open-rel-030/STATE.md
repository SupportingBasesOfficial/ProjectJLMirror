# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR DECISION REVIEW  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted  
**Track B acceptance authorization:** not granted  
**Tier 1 recommendation:** PostgreSQL transactional acceptance/outbox/current-state mechanism only with immutable canonical observation content + owner-controlled source generation/poll epoch + durable live poll claim resolved in-transaction — conformed; recommended for C2 acceptance  
**Tier 2 recommendation:** TimescaleDB historical projection only under the conformed mediated shared-history profile — recommended for C2 acceptance  
**Production versions/numerics:** not selected; production telemetry envelopes remain `OPEN-REL-020` C3

## Gate state

```text
D1 ratified canonical base
  main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b
        |
        v
D2 bounded evidence harness
        |
        +-- Tier 1 real PostgreSQL proof          COMPLETE
        +-- identity-content conflict rejection   COMPLETE
        +-- owner source/epoch + poll-claim proof COMPLETE
        +-- crash / ambiguity / recovery matrix   COMPLETE
        +-- physical PITR (R,F] reconciliation    COMPLETE
        +-- late-history / explicit-gap matrix     COMPLETE
        +-- Tier 1 <-> Tier 2 relocation matrix   COMPLETE
        +-- Tier 2 isolation / escalation matrix  COMPLETE
        +-- Timescale jobs + restore matrix        COMPLETE
        +-- bounded capacity under safe profile    COMPLETE FOR C2
        |
        v
C2 decision recommendation                       READY FOR EXACT-HEAD REVIEW
        |
        +-- production capacity numerics           STILL OPEN / OPEN-REL-020 C3
        +-- production version pinning              NOT SELECTED
        +-- Wave 4 implementation authorization     NOT GRANTED
        |
        v
OPEN-REL-030 acceptance                           REQUIRES REVIEW + EXPLICIT TRACK B ACCEPTANCE
```

## Tier 1 authority profile

Current-state candidacy is accepted only when all of these are true in the same transaction:

- a canonical observation identity is new, or an existing identity matches its immutable canonical source/metric/generation/timestamp/value content exactly;
- the source generation equals the active generation read from owner-controlled source authority;
- the poll epoch equals the active owner-controlled epoch;
- the exact poll generation has a durable `live` claim;
- the current-state compare-and-set wins under that owner ordering authority.

The final harness explicitly rejects conflicting identity content, fabricated/missing claims, retired claims, predecessor generation after replacement, and caller attempts to self-assert current source authority. The successor generation advances only under its successor owner epoch/claim.

## Tier 2 empirical classification

The bounded spike falsified the naive assumption that pooled PostgreSQL RLS can simply be combined with every Timescale feature:

- direct `RLS + columnstore` was rejected by TimescaleDB 2.29.2 with SQLSTATE `0A000`;
- direct `RLS + continuous aggregate` was rejected with SQLSTATE `0A000`.

The surviving Tier 2 candidate is therefore the **mediated shared-history profile**:

- tenant-facing/reporting roles have no direct privilege on shared raw history, continuous aggregates or internal materialization;
- tenant binding is not selected by caller-writable SQL state;
- the read boundary is hardened `SECURITY DEFINER` with fixed `search_path`;
- `ts_owner` is a NOLOGIN mediation owner;
- `ts_automation_owner` has LOGIN only because Timescale background workers require the job-bearing object owner to have it, with no SUPERUSER/CREATEROLE/BYPASSRLS and no tenant-facing/runtime membership;
- escalation, direct-read and tenant-crossing attacks are repeated after background jobs, logical restore and restored-job execution.

## C2 versus C3 capacity boundary

The spike demonstrated bounded mechanism fitness under the same security profile using 100,004 historical rows, columnstore conversion, continuous aggregates, background policies, logical restore and a mediated query path.

This is sufficient evidence to review the **C2 mechanism/profile selection**. It is explicitly **not** a production sizing claim. Throughput, retention, cardinality, buffer/loss, checkpoint, cost, chunk/compression schedules, aggregate refresh intervals and production SLO/capacity envelopes remain owned by `OPEN-REL-020` C3 and cannot be inferred from the spike measurements.

## Acceptance rule

Evidence completion does not itself make either mechanism canonical.

The next gate is exact-final-HEAD review of the evidence and proposed decision classification. Only after that gate is clean may Track B be presented for explicit acceptance authorization. `OPEN-REL-030` becomes accepted/canonical only through that separate authorization/acceptance action.

Even after Track B acceptance, Wave 4 product implementation remains a **separate explicit authorization**. No evidence file, CI result, mergeability state or tool output grants that authorization implicitly.
