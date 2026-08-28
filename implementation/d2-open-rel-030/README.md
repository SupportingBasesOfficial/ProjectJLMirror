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
- Worker/caller assertions never substitute for source, poll, provider-finality, recovery or target-checkpoint authority.
- Every structured message protected by a hash or HMAC must first have a deterministic **unambiguous/self-delimiting** canonical representation.
- A strong cryptographic primitive does not repair ambiguous structured serialization.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- SHA-256/HMAC-SHA-256 and the evidence canonical encoding do not select production KMS/HSM/secret topology or a mandatory production wire format.
- `ts_automation_owner` is a LOGIN cross-tenant privileged infrastructure principal; `PASSWORD NULL` is not equivalent to `NOLOGIN` or proof of production connection admission.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Tier 1 authority coverage

The executable package proves:

- atomic create-or-observe across independent PostgreSQL connections;
- immutable canonical observation content under stable identity;
- owner-controlled source generation and poll epoch resolved inside the transaction;
- exact durable `live` poll claim required for current candidacy;
- current-state CAS by platform source/poll authority;
- repeated-current semantic idempotence and history-first/current-later independence;
- stale/predecessor source and retired/fabricated poll authority rejection;
- rollback at injected crash stages;
- post-COMMIT ambiguity convergence without duplicate history/signal effects;
- durable Tier 2-down backlog responsibility.

## Owner-derived late-history finality/currentness

Reconciliation workers do not supply provider snapshot/finality timestamps as authority.

Durable `provider_authority` owns `authority_generation`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. `sweep(...)` takes only window + expected generation, locks the owner record and records the actual owner snapshot. `try_finalize(...)` takes no caller finality/currentness timestamp and locks current owner authority.

The matrix proves stale generation rejection, worker inability to mutate owner authority, contiguous coverage from the supported history floor, required snapshot currentness and durable `gap` on unrecoverable retention loss.

## Physical PITR with surviving structured recovery authority

PITR uses three distinct authorities:

```text
source PostgreSQL
  -> creates committed R and F WAL boundaries

restored PostgreSQL at R
  -> contains rollback-safe local state only

surviving external control PostgreSQL
  -> excluded from source backup/restore
  -> owns recovery signing key
  -> issues authenticated structured recovery grant after F
```

The recovery grant is stored in typed columns: domain, `R`, `F`, successor epoch, placement version, required receipt and nonce, plus canonical payload and attestation. The HMAC key exists only in the surviving authority.

Every signed field is encoded as:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

The shell reads the structured columns independently. It does **not** split an authenticated delimiter-framed text blob to recover authority.

The negative/positive matrix proves:

```text
physical_pitr_grant_delimiter_collision_closed=PASS
physical_pitr_grant_receipt_contains_pipe=PASS
physical_pitr_local_self_mint_cannot_admit=PASS
physical_pitr_tampered_external_grant_rejected=PASS
physical_pitr_external_grant_verified=PASS
physical_pitr_post_reconcile_admission=PASS
```

The receipt is deliberately `effect|after-r`, proving a literal former delimiter cannot alter structured boundaries. Only the authenticated surviving grant permits successor facts to be applied; rollback-subject business state is not replayed.

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

## Canonical representation before cryptography

The bounded evidence representation uses the same field encoding for all structured crypto boundaries:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

It is applied to:

1. immutable observation fields before the relocation SHA-256 digest;
2. target-checkpoint facts before the target HMAC-SHA-256 attestation;
3. recovery-grant facts before the PITR HMAC-SHA-256 attestation.

### Observation digest

The current evidence profile covers accepted ordinal, observation ID, metric definition ID, normalized UTC `observed_at` at microsecond precision and normalized numeric value. A dedicated negative proves the old `0x1f/0x1e` delimiter framing was ambiguous with unrestricted text; the self-delimiting representation remains distinct.

### Target checkpoint attestation

Both Timescale issuer and PostgreSQL verifier independently construct `canonical_checkpoint_payload` from:

- domain;
- tenant;
- `F`;
- checkpoint ID;
- checkpoint generation;
- sealed flag;
- target count;
- target digest;
- target max ordinal.

Exact-head evidence proves:

```text
relocation_checkpoint_hmac_payload_cross_store=PASS
```

Thus the HMAC protects an identical structured byte representation on both sides of the storage seam instead of a delimiter-concatenated string.

### Production boundary

The exact UTF-8 length+hex encoding is a bounded evidence mechanism, not a mandatory production serialization. Another accepted representation is allowed only if it is deterministic, versioned, injective or equivalently unambiguous for every protected structured field and is independently revalidated.

## Relocation target lifecycle

Tier 1 locks placement before deriving `F`. `max(target)=F` is not treated as completeness. The target-owned checkpoint measures actual current target count/max/digest and is authenticated before activation.

Target lifecycle:

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

The matrix covers internal gaps, canonical payload mismatch, fabricated attestation, seal-vs-DML race, pre-seal/post-seal `>F`, DELETE, tenant move, activated pre-fence mutation and stale source rejection.

## Fresh-cluster restore and capacity boundary

Restore occurs in a new PostgreSQL/Timescale cluster. The harness proves zero JLMirror roles before bootstrap, reconstructs the minimum five-role topology, restores 100,004 history rows and both Timescale jobs, validates ownership and repeats isolation/escalation attacks after restore and after restored-job execution.

The same security profile is exercised for bounded capacity mechanism fitness. Production throughput, retention, cardinality, cost, loss/buffer/checkpoint budgets, chunk/compression/refresh schedules, SLOs and topology remain `OPEN-REL-020` C3.

## Exact empirical anchor before reviewer documentation

```text
HEAD
3ffc96073b54fe7a8b5d002523733947ee59ba57

JLMIRROR Deterministic Assurance #2012
run id 33208029855
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #74
run id 33208029866
SUCCESS
```

The #74 extended run includes the new structured-serialization evidence plus all previous authority/isolation/recovery/relocation vectors. This anchor is provenance only: documentation changes create a new HEAD and require both workflows again.

## Governance state

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment topology or authorize merge. Exact-final-HEAD CI, Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
