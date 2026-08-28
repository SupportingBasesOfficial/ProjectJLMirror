# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD review and explicit Track B acceptance:

1. select the ADR-008 PostgreSQL transactional acceptance pattern as Tier 1 only with **immutable canonical observation content**, **owner-controlled active source generation and poll epoch resolved inside the acceptance transaction**, an exact **durable live poll claim**, **contiguous/current history-reconciliation evidence anchored at `supported_history_floor`**, **lock-before-`F` relocation fencing**, and independent verification of a **target-owned authenticated sealed canonical-payload checkpoint**;
2. select TimescaleDB as Tier 2 historical projection **only under the mediated shared-history security profile proven by this spike**, including fresh-cluster role reconstruction and the target-owned checkpoint/freeze boundary;
3. reject direct pooled RLS assumptions for Timescale columnstore/continuous-aggregate surfaces on the evaluated profile;
4. reject same-cluster database restore as sufficient proof of cluster-global role-topology recovery;
5. reject `max(target_ordinal)=F` as proof of target completeness;
6. reject caller-provided target count/digest/max as proof of the target's actual current state;
7. require complete-set equivalence to include immutable canonical payload, not identity/ordinal alone;
8. require the target checkpoint to serialize against target DML before it measures and seals the set;
9. require the target freeze to preserve both OLD and NEW tenant authority scopes across UPDATE;
10. reject `max(reconciliation window_to)` as proof that history has been continuously reconciled from the supported history floor;
11. require history finalization to use reconciliation evidence whose provider snapshot is at least as current as the finalization requires;
12. preserve `OPEN-REL-020` as owner of production telemetry buffer/loss/checkpoint/retention/cardinality/cost and other production capacity numerics;
13. treat pinned PostgreSQL/Timescale versions and image digests as reproducible evidence dependencies, not production version selections;
14. treat SHA-256/HMAC-SHA-256 here as bounded mechanism evidence, **not** as a production KMS/HSM/secret-topology selection;
15. preserve the telemetry projection seam and require any future Tier 2 replacement to re-prove identity/payload equivalence, idempotency, continuous reconciliation, independently trustworthy target checkpoint/freeze, isolation, recovery and relocation semantics.

## Exact empirical anchor before this classification mutation

The hardened evidence package ran on:

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

The conformance run includes baseline plus ambiguity, owner-source/poll authority, contiguous/current late-history reconciliation, recovery, physical PITR, Timescale background jobs, fresh-cluster restore and role reconstruction, post-restore attacks, source-fence concurrency, deliberate gap-at-`F`, canonical-payload mismatch, target-checkpoint authentication, seal-vs-DML concurrency, cross-tenant freeze protection and final authenticated cutover.

Any classification/documentation commit after that SHA must rerun both gates on its own exact HEAD. This anchor is provenance, not permission to reuse a green result across changed commits.

## Review provenance

### Codex review on `9a1f471d6a1f37b5f394bebd203ecf9715c70001`

Review ID `5053787158` raised two material P1 findings:

1. **Target state was not authenticated/current at activation.** The previous receipt accepted target count/digest/max supplied across the evidence boundary and revalidated only the source set. A target could therefore change after measurement, or the supplied target facts could be fabricated.
2. **Target digest omitted immutable canonical payload.** Identity/ordinal equality alone did not prove that timestamp/value and the rest of the accepted observation content matched the source.

Both are valid and are repaired by the current empirical package. That Codex review is not a clean review and cannot serve as the final gate.

### Native Assurance panoramic extension

The review class was widened rather than patched line-by-line. Three additional material requirements were identified and encoded:

1. **Seal-vs-DML ordering.** Even an authentic target checkpoint is stale if target DML can commit between target measurement and seal. Every target-history DML transaction now acquires shared target-control authority; checkpoint seal acquires exclusive target-control authority before calculating the digest.
2. **OLD/NEW tenant authority.** An UPDATE must not escape a sealed tenant by changing `tenant_id`. The freeze locks both OLD and NEW target-control scopes in deterministic tenant order and rejects a protected pre-`F` row if either relevant sealed authority would be violated.
3. **Freeze ownership.** The projection writer must not own the table/checkpoint authority or be able to disable the trigger that makes the sealed checkpoint current through cutover. The target history/checkpoint functions are owned by NOLOGIN `ts_owner`; `ts_automation_owner` gets projection DML/limited execute rights but cannot read the attestation key or disable the freeze.

## Tier 1 classification — conformant under owner-controlled authority profile

The real PostgreSQL harness established:

- atomic create-or-observe under 24 independent database sessions with exactly one logical acceptance winner;
- immutable canonical observation identity/content: conflicting source, metric, source generation, timestamp or value under the same canonical identity is rejected before current-state effects;
- active source generation and poll epoch are read from owner-controlled database state inside the transaction, not asserted by the caller;
- current candidacy additionally requires the exact durable poll claim in `live` state;
- fabricated/missing claims, retired claims and predecessor-generation authority after replacement are rejected;
- only the admitted successor generation/epoch/claim can advance current state;
- first-acceptance historical outbox atomicity;
- repeated-current semantic idempotence and history-first/current-later independence;
- provider event time cannot become current-state authority;
- crash rollback around observation, history intent, current CAS and transition signal stages;
- Tier 2 outage backlog remains durable rather than falsely acknowledged as projected;
- post-COMMIT client ambiguity converges under retry without duplicate observation/history/signal effects;
- late-history completeness requires continuous and sufficiently current reconciliation evidence rather than a maximum sweep endpoint;
- physical PostgreSQL PITR restores exactly to committed `R`, remains fail-closed, consumes surviving `(R,F]` evidence and admits successor authority without replaying the rollback-subject post-`R` business mutation.

The concurrency oracle reports `authority=owner_source_plus_live_poll_claim` and the ambiguity vector converges to one durable observation, one historical obligation and one semantic signal.

## Late-history reconciliation evidence

History reconciliation distinguishes **provisional high-water evidence** from **continuous completeness evidence**.

The durable evidence consists of reconciliation runs with exact `window_from`, `window_to` and `provider_snapshot_at`. `contiguous_covered_through` begins only at the stream owner's `supported_history_floor`, orders eligible runs by interval, extends coverage only through overlapping/touching windows, and stops at the first hole.

Finalization additionally supplies `min_reconciliation_snapshot_at`. Runs older than that currentness bound do not count toward final completeness.

The adversarial matrix proves:

```text
supported_history_floor                 2026-08-27T00:00:00Z
fast/high-only sweep                    11:55..12:00
anchored coverage after high-only       NONE
high-only finalization                  REJECTED

low sweep                               floor..10:00
existing high sweep                     11:55..12:00
max(window_to)                          12:00
actual contiguous coverage              only through 10:00
disjoint-sweep finalization             REJECTED

bridging sweep                          10:00..12:00 @ snapshot 12:15
delayed observation                     10:30 recovered
continuous coverage                     floor..12:00
finalization requiring snapshot 12:16   REJECTED
finalization requiring snapshot 12:15   ACCEPTED
```

The final state remains:

```text
zabbix:item:42
  state                           complete
  reconciliation_covered_from     2026-08-27 00:00:00+00
  reconciliation_covered_through  2026-08-28 12:00:00+00
  finalized_through               2026-08-28 12:00:00+00

zabbix:item:retention-loss
  state                           gap
  finalized_through               NULL
```

Therefore a high sweep, a disjoint set of sweeps, `max(window_to)`, or stale reconciliation evidence cannot manufacture a complete watermark. Provider retention loss remains explicit `gap`, never inferred absence/complete.

## Physical PITR evidence

The physical PITR vector proves distinct durable transaction/WAL boundaries:

```text
R committed state      state_at_R | epoch 5 | generation 10
F committed state      post_R_business_change | generation 11 | continuity receipt present
R restore point LSN    0/40020B8
F restore point LSN    0/40022A0
```

The restored database contains exactly the state at `R`, no post-`R` continuity receipt, and remains non-authoritative until surviving `(R,F]` evidence is reconciled. After reconciliation it receives successor epoch/placement authority while rollback-subject business state remains at `R`.

## Tier 2 classification — conformant only under mediated profile

Against TimescaleDB 2.29.2 / PostgreSQL 17.11:

```text
direct pooled RLS + columnstore
  -> SQLSTATE 0A000
  -> columnstore cannot be used on table with row security

direct pooled RLS + continuous aggregate
  -> SQLSTATE 0A000
  -> cannot create continuous aggregate on hypertable with row security
```

Those direct feature-bearing profiles are ineligible on the evaluated candidate. The surviving shape is:

```text
shared history / columnstore / continuous aggregate
        |
        | no direct tenant-facing privilege
        v
hardened mediated reader / projection boundary
        |
        +-- tenant binding outside caller-writable SQL state
        +-- SECURITY DEFINER with fixed search_path
        +-- NOLOGIN ts_owner for mediation/checkpoint authority
        +-- least-privilege ts_automation_owner for bounded automation/projection
        v
tenant-facing/reporting principal
```

Owner classes:

- `ts_owner`: NOLOGIN mediation/mapping/function/checkpoint owner; no SUPERUSER/CREATEDB/CREATEROLE/INHERIT/BYPASSRLS;
- `ts_automation_owner`: LOGIN where required by evaluated Timescale automation; no password assigned and no SUPERUSER/CREATEDB/CREATEROLE/INHERIT/BYPASSRLS;
- `ts_runtime`, `ts_report_a`, `ts_report_b`: no membership in either owner role.

The general attack matrix covers raw/CAGG/internal materialization reads, caller-writable tenant GUCs, `SET ROLE` to both owners/runtime, session authorization, owner-membership grants, direct privilege grants, BYPASSRLS escalation and `search_path` shadowing.

The relocation-specific matrix additionally proves that the projection writer cannot read the checkpoint attestation key or disable the target-history freeze.

## Fresh-cluster Timescale restore evidence

The restore test creates a genuinely new Timescale/PostgreSQL container and first proves:

```text
JLMirror ts_* roles before bootstrap     0
JLMirror roles after minimum bootstrap   5
```

Only then are the minimum role classes reconstructed and the source database restored with Timescale pre/post-restore procedures. The fresh cluster proves:

```text
restored historical rows                 100004 / 100004
restored background jobs                 2
job owner                                ts_automation_owner
shared_history owner                     ts_automation_owner
shared_hourly owner                      ts_automation_owner
report_principal_tenant owner            ts_owner
read_hourly() owner                      ts_owner
automation-owner password credential     absent
runtime/report membership in owners      0
```

The full isolation/escalation matrix is repeated **after the fresh restore** and again **after a restored background job executes**. No tenant-crossing or privilege-escalation path succeeded.

## Tier 1 ↔ Tier 2 relocation evidence

### Source fence ordering

The source fence locks tenant placement authority before deriving `F`.

The concurrency falsifier starts a source acceptance that acquires the placement lock and then sleeps. The test waits until PostgreSQL reports that exact `PgSleep`, then concurrently requests the fence. The fence cannot overtake the already-authoritative acceptance; it waits, the acceptance commits, and the committed ordinal becomes part of `F`.

```text
relocation_acceptance_lock_race_setup          PASS
relocation_racing_acceptance_committed         PASS
relocation_fence_includes_inflight_acceptance  PASS
F                                              3
```

After the fence, source acceptance is rejected.

### Target-owned authenticated checkpoint

The target complete-set claim is produced from the **actual target history** under target-owned authority; it is not accepted because a shell or caller says the target has a certain count/digest/max.

The target computes:

- target count through `F`;
- target maximum accepted ordinal;
- ordered SHA-256 canonical-payload digest.

The current numeric evidence profile serializes:

- accepted ordinal;
- observation identity;
- metric definition identity;
- normalized UTC `observed_at`;
- normalized numeric value.

The target authenticates checkpoint facts with HMAC-SHA-256 using the evidence-only domain `open-rel-030-target-checkpoint-v1`. Tier 1 verifies that attestation before it can persist a receipt as complete. Altering any checkpoint field while replaying a genuine attestation is rejected.

The target checkpoint is then **sealed**. Target DML acquires `target_control FOR SHARE`; seal acquires `target_control FOR UPDATE` before calculating the set. Therefore:

- DML already holding shared authority must commit before the seal can measure and is included in the measured state;
- DML beginning after the seal lock blocks, then sees `sealed` and is rejected for rows at/below `F`;
- the checkpoint cannot become stale through a measure→seal race.

The freeze checks both OLD and NEW tenant scopes for UPDATE, so a protected row cannot escape a sealed tenant by changing `tenant_id`. The projection writer is not the target table/checkpoint owner and cannot disable the freeze.

### Negative and positive evidence

Run #51 proves:

```text
projection writer reads attestation key          REJECTED
projection writer disables freeze                REJECTED
max(target)=F with lower rows missing             INCOMPLETE
same identities/ordinals, wrong observed_at      INCOMPLETE
seal races concurrent target mutation            mutation BLOCKED then REJECTED
fabricated checkpoint field + genuine HMAC       REJECTED
sealed pre-F DELETE                               REJECTED
sealed pre-F cross-tenant UPDATE                  REJECTED
```

Only the authenticated sealed checkpoint whose canonical-payload SHA-256 matches the frozen Tier 1 set becomes complete:

```text
authenticated receipt                    complete|3|3|3|true
target activation                        accepted only after authenticated sealed checkpoint
post-cutover target acceptance           accepted
total authoritative observations         4
target historical observations           4
target distinct identities               4
stale source post-cutover                rejected
retired-source post-cutover projection   0
final authority                          active|target|2|3
```

Tenant-facing direct access to relocation history remains denied.

### Cryptographic mechanism boundary

The spike uses SHA-256 and HMAC-SHA-256 to prove two properties: collision-resistant canonical-set equivalence and authenticated target checkpoint provenance. The HMAC key is ephemeral evidence plumbing.

This does **not** select:

- production KMS/HSM/TEE provider;
- secret distribution topology;
- key rotation or rollover schedule;
- production key custody or recovery policy.

Those remain governed by the platform/security architecture. A production implementation must preserve an independently trustworthy target attestation authority and equivalent-or-stronger integrity semantics.

The evidence currently instantiates numeric observation payload serialization. Other accepted Monitoring payload kinds (`integer`, `boolean`, `string`, `text`, `log`) must define deterministic canonical serialization over every immutable accepted payload field before the same proof is instantiated for them.

## Bounded capacity classification

The same accepted-for-review mediated security profile was exercised with:

```text
historical rows                 100004
rowstore relation bytes         11886592
columnstore relation bytes        655360
continuous aggregate bytes        163840
mediated query returned rows           57
representative query duration    67263218 ns
```

A small chunk emitted a poor-compression-ratio warning, retained as tuning evidence rather than hidden.

These measurements demonstrate bounded C2 mechanism/query fitness only. They do **not** establish production throughput, latency SLO, retention, supported cardinality, chunk interval, compression schedule, aggregate refresh schedule, cost envelope, loss budget, checkpoint horizon or fleet topology. Those remain `OPEN-REL-020` C3.

## Findings discovered and closed by the spike

The program falsified and corrected sixteen material design/evidence assumptions:

1. **Readiness transport mismatch** — Unix-socket readiness did not prove the TCP path used by tenant-facing probes; readiness now uses the same TCP path.
2. **Timescale background-owner requirement** — job-bearing objects require a login-capable owner; `ts_owner` and narrowly privileged `ts_automation_owner` were separated.
3. **RLS feature incompatibility** — direct RLS + columnstore/CAGG is unsupported on the evaluated Timescale profile; the design moved to mediated shared history instead of weakening isolation.
4. **PITR transaction-boundary error** — a restore point emitted before the surrounding mutation commits does not contain that mutation; `R`/`F` now commit before their restore points.
5. **Codex P1 — conflicting observation content** — existing canonical identity with different content was formerly treated as duplicate; immutable content is now compared and mismatch rejected.
6. **Codex P1 — caller-asserted active source generation** — caller input could self-assert current authority; owner source/epoch are now resolved and locked in-transaction.
7. **Panoramic poll-authority extension** — the same trust flaw existed for poll ordering; an exact durable live poll claim is now mandatory.
8. **Native Assurance — same-cluster restore false assurance** — restoring to another database inside the same cluster preserved global roles and could not prove role reconstruction; restore now uses a new cluster with zero pre-existing JLMirror roles.
9. **Codex P1 — fence derived before authority lock** — relocation could omit an in-flight accepted row from `F`; the fence now locks placement before deriving `F`, with a real concurrent race test.
10. **Codex P1 — max-only target completeness** — `max(target)=F` could hide internal gaps; gap-at-`F` is explicitly falsified.
11. **Codex P1 — max-only history reconciliation coverage** — a high or disjoint sweep could formerly advance apparent reconciliation past an unswept interval. Coverage is now anchored, continuous and currentness-bounded.
12. **Codex P1 — unauthenticated/stale target complete-set claim** — target count/digest/max supplied across the boundary did not prove current actual target state. Completion now requires a target-owned authenticated sealed checkpoint.
13. **Codex P1 — identity-only target fingerprint** — identity/ordinal equality did not prove immutable observation content. Source and target now compare SHA-256 over the canonical payload evidence profile.
14. **Native Assurance — target measure→seal race** — target DML could otherwise commit after measurement and before the checkpoint became immutable. Shared/exclusive target-control locks now serialize DML with seal, with a real concurrency falsifier.
15. **Native Assurance — cross-tenant freeze escape** — UPDATE could otherwise move a protected row from a sealed tenant if only the new scope were checked. OLD and NEW tenant authority are both locked and validated.
16. **Native Assurance — freeze ownership/tamper boundary** — a projection writer that owned the target table could disable the trigger and invalidate checkpoint currentness. Target history/checkpoint authority is owned by NOLOGIN `ts_owner`; the projection writer cannot disable the freeze or read the attestation key.

Execution-only harness defects discovered while implementing these repairs — such as explicit `pgcrypto` schema qualification and a PL/pgSQL output-column ambiguity — were corrected but are not counted as architectural findings because they did not alter the selected semantic mechanism.

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
- select the production key-management/KMS/HSM/secret topology;
- claim that numeric canonicalization is sufficient for every Monitoring metric payload kind;
- close `OPEN-REL-020` production capacity/numeric decisions;
- authorize deployment or production data authority;
- authorize unrelated Monitoring, Alerting, ITSM, realtime, webhook or broker capabilities;
- allow tenant-facing direct access to shared Timescale feature-bearing relations;
- permit future Timescale upgrades/config changes to bypass compatibility/security/recovery revalidation.

## Review disposition

```text
Evidence completeness        COMPLETE
C2 recommendation            READY FOR EXACT-HEAD REVIEW
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                         NOT AUTHORIZED BY THIS RECORD
```
