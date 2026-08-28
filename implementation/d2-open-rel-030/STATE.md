# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR DECISION REVIEW  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted  
**Track B acceptance authorization:** not granted  
**Tier 1 recommendation:** PostgreSQL transactional acceptance/outbox/current-state mechanism only with immutable canonical observation content + owner-controlled source generation/poll epoch + durable live poll claim resolved in-transaction + contiguous/current reconciliation coverage anchored at the supported history floor + lock-before-`F` relocation fencing — conformed; recommended for C2 acceptance  
**Tier 2 recommendation:** TimescaleDB historical projection only under the conformed mediated shared-history profile, including fresh-cluster role reconstruction and durable complete-set relocation receipts — recommended for C2 acceptance  
**Production versions/numerics:** not selected; production telemetry envelopes remain `OPEN-REL-020` C3

## Gate state

```text
D1 ratified canonical base
  main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b
        |
        v
D2 bounded evidence harness
        |
        +-- Tier 1 real PostgreSQL proof                    COMPLETE
        +-- identity-content conflict rejection             COMPLETE
        +-- owner source/epoch + poll-claim proof           COMPLETE
        +-- crash / ambiguity / recovery matrix             COMPLETE
        +-- late-history contiguous coverage/currentness     COMPLETE
        +-- physical PITR (R,F] reconciliation              COMPLETE
        +-- relocation authority race / fence ordering      COMPLETE
        +-- relocation complete-set receipt / gap test      COMPLETE
        +-- Tier 2 isolation / escalation matrix            COMPLETE
        +-- Timescale fresh-cluster restore / roles         COMPLETE
        +-- restored Timescale jobs + attack matrix         COMPLETE
        +-- bounded capacity under safe profile              COMPLETE FOR C2
        |
        v
C2 decision recommendation                                 READY FOR EXACT-HEAD REVIEW
        |
        +-- production capacity numerics                     STILL OPEN / OPEN-REL-020 C3
        +-- production version pinning                        NOT SELECTED
        +-- Wave 4 implementation authorization               NOT GRANTED
        |
        v
OPEN-REL-030 acceptance                                     REQUIRES REVIEW + EXPLICIT TRACK B ACCEPTANCE
```

## Tier 1 authority profile

Current-state candidacy is accepted only when all of these are true in the same transaction:

- a canonical observation identity is new, or an existing identity matches its immutable canonical source/metric/generation/timestamp/value content exactly;
- the source generation equals the active generation read from owner-controlled source authority;
- the poll epoch equals the active owner-controlled epoch;
- the exact poll generation has a durable `live` claim;
- the current-state compare-and-set wins under that owner ordering authority.

The harness rejects conflicting identity content, fabricated/missing claims, retired claims, predecessor generation after replacement, and caller attempts to self-assert current source authority. The successor generation advances only under its successor owner epoch/claim.

## Late-history completeness profile

A reconciliation sweep endpoint is **not** a completeness watermark by itself.

History finalization is permitted only when reconciliation evidence forms a continuous interval beginning at the owner's `supported_history_floor` and reaches the requested finalization boundary. Reconciliation runs are ordered/merged only when their intervals overlap or touch; the first unswept hole terminates continuous coverage.

Finalization additionally specifies a minimum provider/reconciliation snapshot currentness. Runs older than that minimum cannot be reused to prove current completeness, even if their interval geometry would otherwise cover the requested range.

The negative matrix proves:

- a high-only sweep `11:55..12:00` leaves anchored coverage absent and cannot finalize;
- a low sweep `supported_history_floor..10:00` plus the high sweep retains the real `10:00..11:55` hole; generic `max(window_to)=12:00` does not help, continuous coverage remains only through `10:00`, and finalization is rejected;
- a bridging sweep `10:00..12:00` at provider snapshot `12:15` closes the interval, recovers the delayed `10:30` observation, and establishes continuous coverage from `2026-08-27T00:00:00Z` through `2026-08-28T12:00:00Z`;
- the same interval evidence cannot satisfy a later finalization that requires reconciliation current through `12:16`; it succeeds only when the required minimum snapshot is no newer than the actual covering evidence;
- provider retention loss remains an explicit durable `gap` and can never fabricate `complete`.

Thus `max(reconciliation window_to)` and stale reconciliation evidence are both explicitly rejected as authorities for completeness.

## Relocation authority and completeness profile

Relocation does not treat `F` or a target maximum ordinal as self-proving authority.

The source fence procedure locks the tenant placement authority **before** deriving `F`. A concurrent acceptance that already holds the placement lock must finish first and is included in `F`; an acceptance arriving after the fence waits and then observes the fenced source state, so it cannot create an authoritative row beyond `F`.

Target activation consumes a durable `projection_receipt` bound to the exact frozen source set through `F`. The receipt records and compares:

- authoritative row count;
- ordered canonical observation-identity digest;
- target row count;
- target digest;
- target maximum ordinal.

The negative vector deliberately makes the target reach `max=F` while omitting lower authoritative rows. That state is recorded as `incomplete`, and cutover is rejected. Only after count + digest + max all match the frozen source set does the receipt become `complete` and target activation become eligible.

The empirical fence race finished with `F=3`, a complete receipt `complete|3|3|3`, four total authoritative observations after the target's post-cutover acceptance, and stale-source writes rejected.

## Tier 2 empirical classification

The bounded spike falsified the assumption that pooled PostgreSQL RLS can simply be combined with every Timescale feature:

- direct `RLS + columnstore` was rejected by TimescaleDB 2.29.2 with SQLSTATE `0A000`;
- direct `RLS + continuous aggregate` was rejected with SQLSTATE `0A000`.

The surviving Tier 2 candidate is the **mediated shared-history profile**:

- tenant-facing/reporting roles have no direct privilege on shared raw history, continuous aggregates or internal materialization;
- tenant binding is not selected by caller-writable SQL state;
- the read boundary is hardened `SECURITY DEFINER` with fixed `search_path`;
- `ts_owner` is a NOLOGIN mediation/mapping owner;
- `ts_automation_owner` has LOGIN only because Timescale background workers require the job-bearing object owner to have it, with no password, SUPERUSER, CREATEROLE or BYPASSRLS and no tenant-facing/runtime membership;
- escalation, direct-read and tenant-crossing attacks are repeated after background jobs, after restore into a genuinely fresh PostgreSQL/Timescale cluster, and after a restored background job executes.

The fresh restore proves the source cluster's global role state is absent first (`0` JLMirror roles), reconstructs exactly the five minimum evidence roles, restores `100004/100004` history rows and both Timescale jobs, verifies object/function/job ownership, then re-runs the complete isolation/escalation matrix. A same-cluster database restore is not sufficient role-topology evidence.

## C2 versus C3 capacity boundary

The spike demonstrated bounded mechanism fitness under the same security profile using 100,004 historical rows, columnstore conversion, continuous aggregates, background policies, fresh-cluster logical restore and a mediated query path.

This is sufficient evidence to review the **C2 mechanism/profile selection**. It is explicitly **not** a production sizing claim. Throughput, retention, cardinality, buffer/loss, checkpoint, cost, chunk/compression schedules, aggregate refresh intervals and production SLO/capacity envelopes remain owned by `OPEN-REL-020` C3 and cannot be inferred from the spike measurements.

## Acceptance rule

Evidence completion does not itself make either mechanism canonical.

The next gate is exact-final-HEAD review of the evidence and proposed decision classification. Only after that gate is clean may Track B be presented for explicit acceptance authorization. `OPEN-REL-030` becomes accepted/canonical only through that separate authorization/acceptance action.

Even after Track B acceptance, Wave 4 product implementation remains a **separate explicit authorization**. No evidence file, CI result, mergeability state or tool output grants that authorization implicitly.
