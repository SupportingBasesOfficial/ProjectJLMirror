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

1. select the ADR-008 PostgreSQL transactional acceptance pattern as Tier 1 only with immutable canonical observation content, owner-controlled active source generation/poll epoch, exact durable live poll claims and current-state CAS by platform ordering authority;
2. require late-history finality/currentness to come from durable provider-owner authority, never worker/caller timestamps;
3. require physical PITR recovery admission to consume authenticated surviving `(R,F]` evidence external to the restored authority; a locally recreated receipt is never sufficient;
4. select TimescaleDB as Tier 2 historical projection only under the mediated shared-history profile proven by this spike;
5. classify `ts_automation_owner` as a LOGIN cross-tenant privileged infrastructure principal and require production connection/admission controls to exclude tenant/application use of that role;
6. reject direct pooled RLS assumptions for Timescale columnstore/CAGG on the evaluated profile;
7. require genuine fresh-cluster reconstruction of database-global role topology;
8. require source relocation placement authority to be locked before deriving `F`;
9. require target-owned authenticated sealed canonical-payload checkpoints before target activation;
10. reject any target data above `F` before activation unless it is excluded by the target lifecycle: seal fails if such data already exists, sealed state rejects all DML, and activated state permits only new append above `F` while existing history remains immutable;
11. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
12. treat database versions, image digests and evidence crypto as reproducibility dependencies, not automatic production selections.

## Exact empirical anchor before this review-document mutation

```text
HEAD
f205fe823f9f7635ffb27debb2a2d980fe8cc35f

JLMIRROR Deterministic Assurance
run #1990
run id 33202904143
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #63
run id 33202904081
SUCCESS
```

This SHA proves the executable mechanism after the latest three P1 repairs. It becomes provenance after this document mutation; the exact final package HEAD must rerun both gates.

## Tier 1 acceptance authority

The PostgreSQL harness establishes:

- 24 independent sessions competing on atomic create-or-observe with one logical first-acceptance winner;
- stable canonical identity with immutable canonical source/metric/generation/timestamp/value conflict rejection;
- source generation and poll epoch read and locked from owner state in the acceptance transaction;
- exact durable live poll claim required for current-state candidacy;
- predecessor source generation and retired/fabricated poll authority rejected;
- current-state CAS independent from provider event time;
- first-acceptance historical outbox atomicity;
- repeated-current semantic idempotence and history-first/current-later independence;
- rollback across observation/history/current/signal crash stages;
- post-COMMIT client ambiguity converging without duplicate accepted observation, historical obligation or semantic signal.

## Late-history owner-currentness authority

### Former weakness

Earlier evidence accepted `p_provider_finality_floor` and `p_min_reconciliation_snapshot_at` from the caller of finalization. That made a stale/faulty worker capable of self-asserting the very currentness used to declare history complete.

### Current mechanism

The evidence now has a durable owner-controlled `provider_authority` record with:

```text
authority_generation
current_snapshot_at
finality_floor
required_reconciliation_snapshot_at
```

The owner role is NOLOGIN. The reconciliation worker receives no EXECUTE privilege on the owner authority transition.

`sweep(...)` takes only:

```text
stream
window_from
window_to
expected_authority_generation
```

Inside the same transaction it locks provider authority, rejects stale generations and uses the owner snapshot as the durable `provider_snapshot_at` of the run.

`try_finalize(...)` takes only:

```text
stream
finalize_through
```

It locks current provider authority and derives `finality_floor` plus `required_reconciliation_snapshot_at` internally.

### Negative proof

The run proves:

- worker cannot advance provider authority;
- stale worker generation is rejected;
- high-only/disjoint reconciliation cannot fabricate continuous coverage;
- generation-2 runs at snapshot `12:15` cannot satisfy a generation-3 owner requirement `12:16`;
- a fresh generation-3 covering sweep is required before finalization;
- provider retention loss remains durable `gap`.

This closes the caller-self-asserted finality/currentness P1.

## Physical PITR and surviving `(R,F]` evidence

### Former weakness

Earlier PITR evidence restored to `R`, then locally recreated `effect-after-r` and set reconciliation/successor authority in the restored database. That showed a recovery sequence but did not prove that the restore consumed evidence surviving outside the rollback boundary.

### Current mechanism

The PITR harness now has a separate surviving control PostgreSQL that is neither source nor restore target.

It owns:

- expected `R/F` boundary semantics;
- successor epoch and placement;
- required continuity receipt;
- a random HMAC key stored only in the surviving authority.

The source database/basebackup/restored database never contains that key.

Only **after `F` exists** does the surviving authority issue a recovery grant:

```text
open-rel-030-recovery-v1
R
F
successor epoch
successor placement
required receipt
fresh nonce
```

The grant is HMAC-SHA-256 authenticated by the surviving authority.

### Negative proof

After exact restore to `R`:

- no post-`R` receipt/grant metadata exists;
- locally recreating `effect-after-r` leaves admission false;
- a tampered grant payload with the genuine old attestation is rejected.

### Positive proof

The exact external grant is verified by the surviving authority; only authenticated successor facts are applied to the restored local state. The rollback-subject business mutation remains at `R` and is not replayed.

Final admission is explicitly the conjunction of:

- reconciled local state derived from the authenticated grant; and
- fresh successful verification by the surviving external authority.

This closes the self-minted recovery-receipt P1 and preserves the accepted rule that uncertainty after restore is not absence/authority.

## Tier 2 Timescale profile

Against TimescaleDB 2.29.2 / PostgreSQL 17.11:

```text
direct pooled RLS + columnstore          -> SQLSTATE 0A000
direct pooled RLS + continuous aggregate -> SQLSTATE 0A000
```

Those direct profiles are ineligible on the evaluated candidate.

The surviving mediated profile requires:

- no direct tenant-facing raw/CAGG/internal-materialization privilege;
- tenant binding outside caller-writable SQL state;
- fixed-search-path `SECURITY DEFINER` reader;
- `ts_owner` NOLOGIN mediation/mapping/checkpoint owner;
- `ts_automation_owner` as a separate least-privilege LOGIN owner for job-bearing objects where required by Timescale;
- tenant/runtime principals with no membership in either owner;
- attack matrix across `SET`/`set_config`, search-path shadowing, `SET ROLE`, session authorization, direct grants, owner membership and BYPASSRLS escalation.

### Privileged automation boundary

`ts_automation_owner` is explicitly a **cross-tenant privileged infrastructure principal**. It has no password credential, SUPERUSER, CREATEDB, CREATEROLE, INHERIT or BYPASSRLS in the evidence profile.

`PASSWORD NULL`, however, is not `NOLOGIN` and is not proof that every future `pg_hba`/socket/network topology denies authentication. Production instantiation must prevent application/tenant principals from authenticating as or assuming this role. Widening that boundary invalidates the conformed profile until fresh evidence/review.

## Fresh-cluster restore

The Timescale restore vector starts a genuinely new cluster and first proves zero JLMirror roles exist. It reconstructs exactly five minimum evidence roles, restores 100,004 history rows and two Timescale jobs, validates object/function/job ownership and repeats the isolation/escalation matrix:

- immediately after restore; and
- after a restored background job executes.

A same-cluster database restore is not accepted as role-topology recovery evidence.

## Tier 1 ↔ Tier 2 relocation

### Source fence

The source placement row is locked before deriving `F`. A source acceptance already holding that lock commits first and its ordinal is included in `F`; an acceptance after the fence is rejected.

Empirical boundary:

```text
F = 3
```

### Canonical target checkpoint

The target checkpoint is owned by the target-side NOLOGIN authority and measures the actual target state. It binds:

- count;
- maximum ordinal;
- deterministic SHA-256 over ordered canonical immutable payload represented by this evidence profile.

The checkpoint is domain-separated HMAC-SHA-256 authenticated. Tier 1 verifies the attestation and recomputes its frozen authoritative digest before activation.

Negative vectors include internal gaps at `F`, canonical-payload mismatch and fabricated checkpoint facts.

### Former `>F` weakness

Earlier checkpoint digest/count filtered `<=F`, while target staging could contain a row `>F`. Such a row could be invisible to the checkpoint yet survive cutover.

### Current full pre-activation fence

Target lifecycle is now:

```text
open
  staging allowed
  seal checks that target contains zero rows > F
  any >F row -> seal rejected, phase remains open

sealed
  ALL target-history DML rejected
  checkpoint set is frozen through Tier 1 activation

activated
  existing history immutable
  INSERT <= F rejected
  new append > F allowed
```

The executable matrix proves:

- a pre-seal future row `F+1` blocks checkpoint creation;
- failed seal leaves phase `open` so staging can repair the target;
- a mutation racing final seal blocks and then rejects;
- a post-seal future insert is rejected;
- sealed DELETE and tenant move are rejected;
- after activation, pre-fence history update is rejected;
- the first new authoritative target acceptance receives ordinal `4 = F+1` and appends successfully.

This closes the uncheckpointed post-fence target-row P1.

## Recovery, crypto and trust boundaries

The evidence uses HMAC-SHA-256 for two distinct bounded mechanisms:

1. target checkpoint attestation;
2. surviving external PITR recovery grant.

These are evidence mechanisms used to demonstrate independently held integrity/freshness authority. They do **not** select production key provider, KMS/HSM/TEE topology, key provisioning or rotation. Production must preserve equivalent-or-stronger semantics under separately accepted security/platform architecture.

## Capacity classification

The mediated profile is exercised with:

```text
historical rows                 100004
rowstore relation bytes         11886592
columnstore relation bytes        655360
continuous aggregate bytes        163840
mediated query returned rows           57
representative query duration    74558370 ns
```

This is bounded mechanism-fitness evidence only, not production sizing/SLO evidence. `OPEN-REL-020` remains owner of production capacity numerics.

## Material findings closed by the D2 program

The evidence program has materially corrected the following classes:

1. readiness transport mismatch;
2. Timescale background-job owner requirement;
3. direct RLS + Timescale feature incompatibility;
4. PITR restore-point transaction-boundary error;
5. conflicting observation content accepted as duplicate;
6. caller-asserted source authority;
7. poll authority needed the same owner-currentness treatment;
8. same-cluster restore falsely implied role reconstruction;
9. relocation `F` derived before source authority lock;
10. max-only target completeness;
11. max-only/disjoint history reconciliation completeness;
12. target receipt not authenticated against actual target state;
13. relocation digest omitted immutable payload;
14. target seal needed serialization against DML;
15. target freeze needed cross-tenant/owner hardening;
16. Timescale LOGIN automation owner trust class needed explicit production admission boundary;
17. PITR restored authority could self-mint its recovery receipt;
18. history worker could self-assert provider finality/currentness;
19. target could carry uncheckpointed `>F` history through cutover.

Each material finding triggered a class-level/panoramic repair, not a line-only patch.

## What acceptance would and would not mean

If the exact-final-HEAD package is reviewed clean and Track B is explicitly accepted:

```text
OPEN-REL-030
  -> selected + conformed for the accepted mechanism/profile

Wave 4 implementation
  -> still NOT automatically authorized
```

Acceptance would not:

- make PostgreSQL 17.11 or TimescaleDB 2.29.2 immutable production pins;
- choose production KMS/HSM/secret topology;
- choose production database authentication/network topology;
- close `OPEN-REL-020` capacity numerics;
- authorize product implementation, deployment or production authority;
- permit direct tenant access to shared Timescale feature-bearing relations;
- permit future upgrades/topology changes to inherit this conformance without relevant revalidation.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  f205fe823f9f7635ffb27debb2a2d980fe8cc35f / #1990 / #63
Final documentation HEAD     REQUIRES FRESH EXACT-HEAD CI
Codex final review           REQUIRED
Native Assurance             REQUIRED
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                         NOT AUTHORIZED BY THIS RECORD
```
