# D2 — OPEN-REL-030 Monitoring Conformance Evidence

**Status:** evidence complete — ready for exact-HEAD decision review; no production authority  
**Canonical base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Branch:** `evidence/open-rel-030-monitoring-conformance`  
**Decision under test:** `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`  
**Track B acceptance:** not granted  
**Wave 4 implementation authorization:** not granted

## Purpose

This package is a bounded, reproducible falsification laboratory for `OPEN-REL-030`. It does not implement the Monitoring product vertical and has no production authority.

It evaluates:

1. **Tier 1 PostgreSQL:** acceptance/idempotency, source/poll authority, current-state CAS, ambiguity, late-history reconciliation, physical PITR and relocation fencing.
2. **Tier 2 TimescaleDB:** tenant isolation, feature compatibility, privileged background-job ownership, fresh-cluster restore, relocation checkpoint/freeze semantics and bounded mechanism capacity.

## Non-negotiable boundaries

- Provider event time is metadata, never current-state authority.
- Worker/caller assertions are never allowed to substitute for source, poll, provider-finality, recovery or target-checkpoint authority.
- Canonical equivalence requires a deterministic, **unambiguous/self-delimiting** byte representation before hashing; delimiter-framed unrestricted text is not sufficient.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- SHA-256/HMAC-SHA-256 used by the evidence harness do not select production KMS/HSM/secret topology.
- `ts_automation_owner` is a LOGIN cross-tenant privileged infrastructure principal; `PASSWORD NULL` is not equivalent to `NOLOGIN` or proof of production connection admission.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Evidence layout

```text
implementation/d2-open-rel-030/
  README.md
  STATE.md
  EVIDENCE_MANIFEST.json
  DECISION_REVIEW.md
sql/d2-open-rel-030/
  001_tier1_acceptance.sql
  002_tier1_assertions.sql
  003_tier1_recovery_authority.sql
  004_history_reconciliation.sql
  010_timescale_candidate.sql
  011_timescale_jobs_capacity.sql
  012_timescale_restore_role_bootstrap.sql
tools/open_rel_030/
  tier1_concurrency.py
  tier1_commit_ambiguity.sh
  physical_pitr.sh
  timescale_jobs_restore.sh
  tenant_relocation.sh
  run_conformance.sh
  run_conformance_extended.sh
.github/workflows/
  open-rel-030-conformance.yml
```

## Tier 1 authority coverage

The executable package proves:

- atomic create-or-observe across independent PostgreSQL connections;
- immutable canonical observation content under stable identity;
- owner-controlled source generation and poll epoch resolved inside the transaction;
- exact durable `live` poll claim required for current candidacy;
- current-state CAS by platform source/poll authority;
- repeated-current semantic idempotence and history-first/current-later independence;
- stale/predecessor source and retired/fabricated poll authority rejection;
- transaction rollback at injected crash stages;
- post-COMMIT ambiguity convergence without duplicate history/signal effects;
- durable Tier 2-down backlog responsibility.

## Owner-derived late-history finality/currentness

Reconciliation workers no longer supply provider snapshot/finality timestamps as authority.

The durable owner-controlled `provider_authority` record contains:

- `authority_generation`;
- `current_snapshot_at`;
- `finality_floor`;
- `required_reconciliation_snapshot_at`.

A worker calls `sweep(stream, window_from, window_to, expected_generation)`. The function locks `provider_authority`, rejects a stale expected generation and records the actual owner snapshot internally.

`try_finalize(stream, finalize_through)` accepts no finality/currentness timestamp from the worker. It locks current owner authority and accepts only reconciliation runs sufficiently current for the durable owner requirement.

The negative matrix proves:

- the worker cannot execute the owner authority transition;
- stale generation cannot sweep;
- a high-only or disjoint set of windows cannot create anchored completeness;
- generation-2 coverage at provider snapshot `12:15` cannot satisfy a generation-3 required snapshot of `12:16`;
- only a new covering sweep under generation 3 permits finalization;
- retention loss remains durable `gap`, never false `complete`.

## Physical PITR with surviving external recovery authority

PITR uses three distinct authorities:

```text
source PostgreSQL
  -> creates committed R and F WAL boundaries

restored PostgreSQL at R
  -> contains rollback-safe local state only

surviving external control PostgreSQL
  -> excluded from source backup/restore
  -> owns recovery signing key
  -> issues authenticated recovery grant after F
```

The external control authority stores a random HMAC key that is never copied into the source database, base backup or restored database. It issues a domain-separated recovery grant after `F` containing the required successor epoch, placement and continuity receipt.

Negative vectors prove:

- exact restore to `R` has no post-`R` receipt/grant metadata;
- locally recreating `effect-after-r` does **not** admit the restore;
- tampering with the external grant payload while replaying its attestation fails verification.

Only after the surviving authority verifies the exact grant are its authenticated successor facts applied. Final admission requires both reconciled local state and fresh successful verification by the surviving authority. The post-`R` rollback-subject business mutation is not replayed.

## Tier 2 classification

### Rejected direct profiles

On TimescaleDB 2.29.2 / PostgreSQL 17.11:

- direct pooled `RLS + columnstore` is rejected with SQLSTATE `0A000`;
- direct pooled `RLS + continuous aggregate` is rejected with SQLSTATE `0A000`.

### Surviving mediated profile

The candidate requires:

- no direct tenant-facing privilege on shared raw history, continuous aggregates or internal materialization;
- tenant binding outside caller-writable SQL state;
- fixed-search-path `SECURITY DEFINER` mediation;
- NOLOGIN `ts_owner` for mediation/mapping/checkpoint authority;
- LOGIN `ts_automation_owner` only as privileged infrastructure where evaluated Timescale job ownership requires it;
- no tenant/runtime membership in either owner;
- repeated escalation/isolation attacks after jobs, after genuinely fresh-cluster restore and after restored-job execution.

`ts_automation_owner` is explicitly **cross-tenant privileged infrastructure**. Its evidence role has no password credential, SUPERUSER, CREATEROLE or BYPASSRLS, but `PASSWORD NULL` is not an authentication barrier. Production `pg_hba`, socket/network exposure, role membership and credential provisioning must prevent application/tenant principals from authenticating as or assuming it.

## Relocation: source fence + complete pre-activation target fence

### Source

Tier 1 locks placement authority before deriving `F`. An acceptance already holding authority commits before the fence and is included in `F`; later source acceptance is rejected.

### Canonical representation before hashing

The checkpoint digest is only authoritative if the pre-hash representation is unambiguous.

The evaluated profile encodes **each immutable field independently** as:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

The row fields are then concatenated in deterministic row order. Because the payload portion is hex and every field carries its byte length, text content cannot impersonate a field or row boundary.

The current evidence profile covers:

- accepted ordinal;
- observation ID;
- metric definition ID;
- UTC `observed_at` normalized to microsecond precision;
- normalized numeric value.

A dedicated negative demonstrates that the former `0x1f` field / `0x1e` row delimiter scheme is ambiguous when `observation_id` is unrestricted `text`: distinct logical field boundaries can yield the same raw pre-hash bytes. The self-delimiting representation produces different bytes for those logical values, and a cross-store probe proves PostgreSQL and Timescale produce the same canonical field representation for text containing literal `0x1f` and `0x1e` bytes.

Future accepted Monitoring payload kinds must deterministically serialize **every immutable accepted field** with a versioned, injective or equivalently unambiguous representation. A cryptographic digest does not repair ambiguous serialization.

### Target completeness

`max(target)=F` is insufficient. The target-owned checkpoint measures actual current target state and includes:

- row count;
- maximum ordinal;
- deterministic SHA-256 over the self-delimiting canonical immutable observation payload represented by the evidence profile.

The checkpoint is HMAC-authenticated and verified before Tier 1 target activation. A same-identity payload mismatch remains `incomplete`; fabricated checkpoint facts are rejected.

### No uncheckpointed post-fence rows

The target lifecycle is deliberately strict:

```text
open
  -> staging DML allowed
  -> seal fails if ANY row has ordinal > F

sealed
  -> ALL target-history DML rejected
  -> checkpoint set cannot change before activation

activated
  -> existing target history immutable
  -> INSERT <= F rejected
  -> new append > F allowed
```

The negative matrix proves:

- a pre-seal row `>F` blocks checkpoint creation and leaves phase `open`;
- a post-seal row `>F` is rejected;
- a mutation racing seal blocks then rejects;
- sealed DELETE and tenant move reject;
- activated pre-fence UPDATE rejects;
- only after activation does the next authoritative ordinal `F+1` append successfully.

This removes the gap where a row outside the `<=F` digest could otherwise survive cutover unnoticed.

## Fresh-cluster restore and background jobs

Restore occurs in a new PostgreSQL/Timescale cluster. The harness first proves zero JLMirror roles exist, reconstructs exactly the minimum five-role topology, restores 100,004 history rows and two Timescale jobs, validates object/function/job ownership and re-runs the full attack matrix after restore and after restored-job execution.

A same-cluster database restore is not accepted as role-topology recovery evidence.

## Capacity boundary

The same mediated profile is exercised with 100,004 historical rows, columnstore, continuous aggregate, background policies, fresh restore and mediated query measurement.

These measurements are bounded **C2 mechanism-fitness evidence only**. Production throughput, retention, cardinality, cost, loss/buffer/checkpoint budgets, chunk/compression/refresh schedules, SLOs and topology remain `OPEN-REL-020` C3.

## Empirical anchor before reviewer documentation

```text
HEAD
cbd433f09a7568048a45b75cd9abb6760b5687d8

JLMIRROR Deterministic Assurance #2000
run id 33206933772
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #68
run id 33206933620
SUCCESS
```

The #68 extended run includes, on this exact SHA:

```text
relocation_delimiter_collision_closed=PASS value=true|true
relocation_canonical_field_cross_store=PASS
history_owner_currentness_authority=PASS
physical_pitr_local_self_mint_cannot_admit=PASS
physical_pitr_tampered_external_grant_rejected=PASS
physical_pitr_external_grant_verified=PASS
relocation_preseal_future_row_blocks_checkpoint=PASS
relocation_postseal_future_insert_rejected=PASS
relocation_authenticated_complete_projection_receipt=PASS
```

This anchor is provenance only. Documentation changes create a new HEAD and require both workflows again.

## Governance state

The authoritative classification/recommendation is carried by `EVIDENCE_MANIFEST.json`, `STATE.md` and `DECISION_REVIEW.md`.

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment topology or authorize merge. Exact-final-HEAD CI, Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
