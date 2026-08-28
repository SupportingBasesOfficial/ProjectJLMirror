# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD review and explicit Track B acceptance:

1. select the existing ADR-008 PostgreSQL transactional acceptance pattern as the canonical Tier 1 durable customer-observation acceptance/current-state mechanism for `OPEN-REL-030`;
2. select TimescaleDB as the Tier 2 historical-projection mechanism **only under the mediated shared-history security profile proven by this spike**;
3. explicitly reject a design that assumes pooled PostgreSQL RLS can be combined directly with or automatically inherited by Timescale columnstore/continuous-aggregate surfaces;
4. preserve `OPEN-REL-020` as the owner of production telemetry buffer/loss/checkpoint/retention/cardinality/cost and other capacity numerics;
5. treat the pinned PostgreSQL/Timescale versions and image digests as reproducible evidence dependencies, not production version selections;
6. preserve the telemetry projection seam and require any future Tier 2 replacement to re-prove the same identity, idempotency, isolation, recovery and relocation semantics.

## Exact successful evidence anchor before classification mutation

The final pre-classification empirical package ran on:

```text
HEAD
89d8f724ae76ab74a5abf8cb0ae60e8dcc8ed95d

JLMIRROR Deterministic Assurance
run #1900
run id 33188581043
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #18
run id 33188581098
SUCCESS
```

Classification/documentation commits after that SHA must rerun both gates on their own exact HEAD. The anchor above is provenance for the measurements below, not permission to reuse a green result across changed commits.

## Tier 1 classification — conformant

The real PostgreSQL harness established:

- atomic create-or-observe under 24 independent database sessions with exactly one logical acceptance winner;
- first-acceptance historical outbox atomicity;
- current-state compare-and-set under owner ordering authority;
- repeated-current semantic idempotence;
- historical-first/current-later independence;
- provider event time not acting as current-state authority;
- stale ordering not regressing current state;
- rollback after injected failures around observation/history-intent/current-CAS/transition-signal stages;
- durable backlog responsibility while Tier 2 is absent;
- post-COMMIT client ambiguity converging under retry without duplicate observation/history/signal effects;
- Zabbix-style poll epoch/generation recovery fencing;
- late-history reconciliation and explicit durable `gap` rather than false completeness;
- physical PostgreSQL PITR to a committed `R`, with surviving external `F` evidence, fail-closed restored admission, `(R,F]` continuity reconciliation and successor epoch/placement admission without blindly replaying post-`R` business state;
- tenant relocation source fencing, target activation only after projection watermark reaches `F`, and stale-source rejection.

### Physical PITR evidence

The final successful physical PITR vector proved that `R` and `F` are distinct durable transaction/WAL boundaries:

```text
R committed state      state_at_R | epoch 5 | generation 10
F committed state      post_R_business_change | generation 11 | continuity receipt present
R restore point LSN    0/40020B8
F restore point LSN    0/40022A0
archived WAL files     6
```

The restored database contained exactly the state at `R` and no post-`R` continuity receipt. It remained non-authoritative until the surviving `(R,F]` evidence was reconciled, after which it carried successor epoch/placement authority while the rollback-subject business value stayed at `R`.

The spike also discovered and corrected an important recovery-test error: a named restore point inside the same transaction as a preceding mutation does not prove that mutation is durable before the restore point. The final harness therefore commits and independently observes each boundary before emitting the named restore point.

## Tier 2 classification — conformant only under mediated profile

### Rejected feature combination

Against TimescaleDB 2.29.2 / PostgreSQL 17.11:

```text
direct pooled RLS + columnstore
  -> SQLSTATE 0A000
  -> "columnstore cannot be used on table with row security"

direct pooled RLS + continuous aggregate
  -> SQLSTATE 0A000
  -> "cannot create continuous aggregate on hypertable with row security"
```

These are evidence outcomes, not test failures to bypass. The direct pooled feature-bearing profile is ineligible on the evaluated candidate profile.

### Accepted-for-review mediated shape

The surviving candidate profile uses:

```text
shared historical hypertable / columnstore / continuous aggregate
        |
        | no direct tenant-facing privilege
        v
hardened mediated reader
        |
        +-- tenant binding outside caller-writable SQL state
        +-- SECURITY DEFINER
        +-- fixed search_path = pg_catalog, ts_evidence
        +-- separate owner trust classes
        v
tenant-facing/reporting principal
```

Owner split:

- `ts_owner`: NOLOGIN mediation/mapping owner, no SUPERUSER/CREATEDB/CREATEROLE/INHERIT/BYPASSRLS;
- `ts_automation_owner`: LOGIN because Timescale requires the owner of job-bearing objects to be login-capable, but no password assigned and no SUPERUSER/CREATEDB/CREATEROLE/INHERIT/BYPASSRLS;
- `ts_runtime`, `ts_report_a`, `ts_report_b`: no membership in either owner role.

The harness attacks direct raw/CAGG/materialization reads, caller-controlled tenant GUCs, `SET ROLE` to both owners, session authorization, owner-membership grants, direct privilege grants, BYPASSRLS escalation and `search_path` shadowing. The same attack class repeats after Timescale background jobs, after logical restore, and after a restored background job executes.

No cross-tenant row leak was observed in the accepted-for-review profile.

## Timescale jobs and restore evidence

The tested shared profile produced and executed:

```text
job 1000  policy_compression                  owner ts_automation_owner
job 1001  policy_refresh_continuous_aggregate owner ts_automation_owner
```

Both foreground `run_job()` executions passed. Logical `pg_dump`/`pg_restore` using Timescale pre/post-restore procedures preserved:

- PostgreSQL/Timescale versions for the evidence environment;
- 100,004 / 100,004 historical rows;
- both background jobs;
- owner trust classes;
- mediated tenant binding;
- denial of tenant-facing access to raw/CAGG/internal materialization.

## Tier 1 <-> Tier 2 relocation evidence

The cross-store relocation vector established:

```text
source accepted pre-cutover observations      2
fence F                                        2
source acceptance after fence                  rejected
target activation below F                      rejected
target activation at F                         accepted
target post-cutover observation                accepted
stale source after target activation            rejected
authoritative accepted observations            3
target historical observations                 3
target distinct observation identities          3
retired-source post-cutover projection rows     0
final authority                                 target / placement version 2
```

The target historical projection was not allowed to become authoritative before reaching the Tier 1 fence watermark, and tenant-facing direct access to the internal relocation history remained denied.

## Bounded capacity classification

The spike measured the **same security profile**, not a privileged bypass profile:

```text
historical rows                 100,004
rowstore relation bytes         11,886,592
columnstore relation bytes         655,360
continuous aggregate bytes         163,840
mediated query returned rows            57
representative query duration    71,833,455 ns
```

One small chunk emitted a poor-compression-ratio warning (32 KiB before, 40 KiB after), which is retained as tuning evidence rather than hidden.

These measurements demonstrate bounded mechanism/query fitness sufficient for C2 selection review. They do **not** establish a production throughput target, latency SLO, retention horizon, supported cardinality, chunk interval, compression schedule, aggregate refresh schedule, cost envelope, loss budget, checkpoint horizon or fleet topology. Those remain `OPEN-REL-020` C3 / production-capacity work.

## Findings discovered by the spike

The evidence program did more than confirm the initial design. It falsified and corrected four material assumptions/harness defects:

1. **Readiness transport mismatch** — initial readiness checked a Unix socket while tenant-facing probes used TCP. The harness now requires the same TCP path to be stably ready rather than masking startup/transport races with per-test retries.
2. **Timescale background-owner requirement** — job-bearing hypertables require a LOGIN-capable owner. Instead of weakening the mediation owner, the design split `ts_owner` from narrowly privileged `ts_automation_owner` and attacked the new escalation surface.
3. **RLS feature incompatibility** — direct RLS plus columnstore/CAGG is not supported on the evaluated Timescale profile. The candidate architecture changed to an explicitly mediated shared-history profile rather than weakening tenant isolation.
4. **PITR transaction-boundary error** — a restore point created before the surrounding mutation transaction commits restores the earlier state. The final physical PITR harness makes `R` and `F` committed and independently observed before creating their restore points.

These findings strengthen the recommendation because the final profile survived the falsification paths that invalidated the earlier assumptions.

## What acceptance would and would not mean

If the exact-final-HEAD package is reviewed clean and Track B is explicitly accepted:

```text
OPEN-REL-030
  -> selected + conformed for the accepted profile

impl.customer-telemetry@1
  -> eligible for a later, separate explicit implementation authorization

Wave 4 implementation
  -> NOT automatically authorized
```

Acceptance would **not**:

- select PostgreSQL 17.11 or TimescaleDB 2.29.2 as immutable production version pins;
- close `OPEN-REL-020` production capacity/numeric decisions;
- authorize deployment or production data authority;
- authorize unrelated Monitoring, Alerting, ITSM, realtime, webhook or broker capabilities;
- allow tenant-facing direct access to shared Timescale feature-bearing relations;
- permit future Timescale upgrades/config changes to bypass compatibility/security revalidation.

## Review disposition

```text
Evidence completeness        COMPLETE
C2 recommendation            READY FOR REVIEW
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                         NOT AUTHORIZED BY THIS RECORD
```
