# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR DECISION REVIEW  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted  
**Track B acceptance authorization:** not granted  
**Tier 1 recommendation:** PostgreSQL transactional acceptance/outbox/current-state mechanism only with immutable canonical observation content + owner-controlled source generation/poll epoch + durable live poll claim resolved in-transaction + contiguous/current reconciliation coverage anchored at the supported history floor + lock-before-`F` relocation fencing + verification of a target-owned authenticated sealed canonical-payload checkpoint — conformed; recommended for C2 acceptance  
**Tier 2 recommendation:** TimescaleDB historical projection only under the conformed mediated shared-history profile, including fresh-cluster role reconstruction, explicit privileged-infrastructure treatment of `ts_automation_owner`, deployment admission isolation for that LOGIN owner, and target-owned authenticated sealed relocation checkpoints — recommended for C2 acceptance  
**Production versions/numerics:** not selected; production telemetry envelopes remain `OPEN-REL-020` C3

## Gate state

```text
D1 ratified canonical base
  main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b
        |
        v
D2 bounded evidence harness
        |
        +-- Tier 1 real PostgreSQL proof                     COMPLETE
        +-- identity-content conflict rejection              COMPLETE
        +-- owner source/epoch + poll-claim proof            COMPLETE
        +-- crash / ambiguity / recovery matrix              COMPLETE
        +-- late-history contiguous coverage/currentness      COMPLETE
        +-- physical PITR (R,F] reconciliation               COMPLETE
        +-- source relocation fence ordering/race            COMPLETE
        +-- target authenticated sealed checkpoint           COMPLETE
        +-- canonical-payload SHA-256 equivalence            COMPLETE
        +-- target seal-vs-DML / tenant-scope freeze         COMPLETE
        +-- Tier 2 isolation / escalation matrix             COMPLETE
        +-- Timescale fresh-cluster restore / roles          COMPLETE
        +-- restored Timescale jobs + attack matrix          COMPLETE
        +-- privileged automation-owner trust boundary       EXPLICIT
        +-- bounded capacity under safe profile               COMPLETE FOR C2
        |
        v
C2 decision recommendation                                  READY FOR EXACT-HEAD REVIEW
        |
        +-- production capacity numerics                      STILL OPEN / OPEN-REL-020 C3
        +-- production version pinning                         NOT SELECTED
        +-- production key/KMS topology                        NOT SELECTED HERE
        +-- production DB authentication/admission topology    DEPLOYMENT INVARIANT / NOT CLAIMED BY SPIKE
        +-- Wave 4 implementation authorization                NOT GRANTED
        |
        v
OPEN-REL-030 acceptance                                      REQUIRES REVIEW + EXPLICIT TRACK B ACCEPTANCE
```

## Exact empirical anchor before reviewer-document mutation

The hardened executable package reached the current reviewer-classification point on:

```text
HEAD
747e0bb84a7b617e7ca97eb835ea0f0d64ac804d

JLMIRROR Deterministic Assurance
run #1965
run id 33200595850
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #51
run id 33200595957
SUCCESS
```

This is provenance, not a reusable final gate. Any commit that changes this STATE, the manifest, the decision review or other package content must rerun both workflows on its own exact HEAD.

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
- a low sweep `supported_history_floor..10:00` plus the high sweep retains the real `10:00..11:55` hole; `max(window_to)=12:00` does not help;
- a bridging sweep `10:00..12:00` at provider snapshot `12:15` closes the interval and recovers the delayed `10:30` observation;
- the same interval evidence cannot satisfy a later finalization that requires reconciliation current through `12:16`;
- provider retention loss remains an explicit durable `gap` and can never fabricate `complete`.

Thus `max(reconciliation window_to)` and stale reconciliation evidence are both explicitly rejected as authorities for completeness.

## Relocation authority and authenticated completeness profile

Relocation has two independently fenced authorities: the Tier 1 source acceptance set and the Tier 2 target checkpoint set.

### Source fence

The source fence locks tenant placement authority **before** deriving `F`. A source acceptance already holding that lock must finish first and is included in `F`; a later acceptance waits and then observes the fenced source state, so it cannot become authoritative beyond `F`.

The empirical race finishes with `F=3` and proves the in-flight acceptance is included.

### Target checkpoint

Target activation no longer trusts caller-provided count/digest/max facts and no longer treats an identity-only digest as payload equivalence.

The target side owns a checkpoint authority under NOLOGIN `ts_owner`. The projection writer `ts_automation_owner` may project data but:

- cannot read the target checkpoint attestation key;
- cannot own or disable the target-history freeze trigger;
- cannot modify/delete a row at or below `F` after the target checkpoint is sealed;
- cannot move a sealed pre-`F` row to another tenant.

A target checkpoint is measured from the **actual target state** and contains count, maximum ordinal and an ordered SHA-256 fingerprint of the canonical observation payload represented by the evidence profile:

- accepted ordinal;
- observation identity;
- metric definition identity;
- normalized UTC observation timestamp;
- normalized numeric value.

The checkpoint facts are authenticated with domain-separated HMAC-SHA-256 (`open-rel-030-target-checkpoint-v1`). Tier 1 independently verifies that attestation and requires the sealed target SHA-256 set to equal the frozen authoritative Tier 1 set before recording `complete` or activating the target.

The evidence deliberately proves all of these negative cases:

- `max(target)=F` with missing lower rows remains `incomplete`;
- the same identities/ordinals with a changed canonical payload remain `incomplete`;
- altering target checkpoint facts while replaying a genuine HMAC is rejected;
- a target mutation racing a seal blocks behind the target authority lock and is rejected after the seal commits;
- DELETE and cross-tenant UPDATE of sealed pre-`F` data are rejected;
- the projection writer cannot disable the freeze.

The successful empirical terminal state is:

```text
source fence F                          3
authenticated sealed receipt            complete|3|3|3|true
post-cutover authoritative observations 4
target historical observations          4
stale source write                       rejected
final authority                          active|target|2|3
```

This establishes the required semantic shape: **source lock-before-`F` + target-owned sealed checkpoint + authenticated canonical-payload complete-set equivalence + freeze continuity through cutover**.

### Crypto boundary

SHA-256 and HMAC-SHA-256 are used here to prove the C2 mechanism shape. This evidence does **not** select the production key provider, KMS/HSM/TEE topology, key rotation schedule, provisioning channel or secret-management implementation. Production must preserve equivalent-or-stronger integrity and independently trustworthy target attestation under the separately accepted security/platform architecture.

For non-numeric Monitoring payload kinds, implementation must define the same kind of deterministic canonical serialization over **all immutable accepted payload fields** before this evidence shape can be instantiated; this spike must not be misread as saying numeric serialization is the only production payload profile.

## Tier 2 empirical classification

The bounded spike falsified the assumption that pooled PostgreSQL RLS can simply be combined with every Timescale feature:

- direct `RLS + columnstore` was rejected by TimescaleDB 2.29.2 with SQLSTATE `0A000`;
- direct `RLS + continuous aggregate` was rejected with SQLSTATE `0A000`.

The surviving Tier 2 candidate is the **mediated shared-history profile**:

- tenant-facing/reporting roles have no direct privilege on shared raw history, continuous aggregates or internal materialization;
- tenant binding is not selected by caller-writable SQL state;
- the read boundary is hardened `SECURITY DEFINER` with fixed `search_path`;
- `ts_owner` is a NOLOGIN mediation/mapping/checkpoint owner;
- `ts_automation_owner` is a LOGIN **cross-tenant privileged infrastructure principal** where required by the evaluated Timescale automation shape; it has no password credential, SUPERUSER, CREATEROLE or BYPASSRLS and no tenant-facing/runtime membership;
- `PASSWORD NULL` is not equivalent to `NOLOGIN` and is not treated as proof that the role cannot authenticate;
- production database connection/authentication admission — including `pg_hba`, local socket/peer/trust behavior, network exposure and role-assumption paths — must prevent tenant/application principals from authenticating as or assuming `ts_automation_owner`;
- assigning an application-usable credential, widening database admission, adding tenant/application membership, or otherwise exposing that owner invalidates this conformed profile until fresh security review/evidence;
- escalation, direct-read and tenant-crossing attacks are repeated after background jobs, after restore into a genuinely fresh PostgreSQL/Timescale cluster, and after a restored background job executes.

The fresh restore proves the source cluster's global role state is absent first (`0` JLMirror roles), reconstructs exactly the five minimum evidence roles, restores `100004/100004` history rows and both Timescale jobs, verifies object/function/job ownership, then re-runs the complete isolation/escalation matrix. A same-cluster database restore is not sufficient role-topology evidence.

The spike proves the **database privilege/ownership shape** and the absence of a password credential in its ephemeral profile. It does not claim to prove production `pg_hba`/socket/network admission topology; that topology is a deployment invariant required to instantiate the accepted profile safely.

## C2 versus C3 capacity boundary

The spike demonstrated bounded mechanism fitness under the same security profile using 100,004 historical rows, columnstore conversion, continuous aggregates, background policies, fresh-cluster logical restore and a mediated query path.

This is sufficient evidence to review the **C2 mechanism/profile selection**. It is explicitly **not** a production sizing claim. Throughput, retention, cardinality, buffer/loss, checkpoint, cost, chunk/compression schedules, aggregate refresh intervals and production SLO/capacity envelopes remain owned by `OPEN-REL-020` C3 and cannot be inferred from the spike measurements.

## Acceptance rule

Evidence completion does not itself make either mechanism canonical.

The next gate is exact-final-HEAD review of the evidence and proposed decision classification. Only after that gate is clean may Track B be presented for explicit acceptance authorization. `OPEN-REL-030` becomes accepted/canonical only through that separate authorization/acceptance action.

Even after Track B acceptance, Wave 4 product implementation remains a **separate explicit authorization**. No evidence file, CI result, mergeability state or tool output grants that authorization implicitly.
