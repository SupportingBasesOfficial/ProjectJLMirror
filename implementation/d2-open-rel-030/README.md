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

1. **Tier 1 PostgreSQL:** acceptance/idempotency, source/poll authority, current-state CAS, ambiguity, late-history reconciliation, physical PITR and relocation fencing/activation authority.
2. **Tier 2 TimescaleDB:** tenant isolation, feature compatibility, privileged background-job ownership, fresh-cluster restore, target-owned relocation checkpoint/freeze semantics and bounded mechanism capacity.

## Non-negotiable boundaries

- Provider event time is metadata, never current-state authority.
- Worker/caller assertions never substitute for source, poll, provider-finality, recovery or target-checkpoint authority.
- Every structured message protected by a hash or HMAC must first have a deterministic **unambiguous/self-delimiting** canonical representation.
- A strong cryptographic primitive does not repair ambiguous structured serialization.
- A verifier must not inherit issuer/mint capability merely because it can validate an attestation.
- Cross-authority activation requires explicit durable authority from both sides; target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- SHA-256/HMAC-SHA-256 and the evidence canonical encoding do not select production KMS/HSM/secret topology or a mandatory production wire format.
- The evidence `dblink`/LOGIN verifier transport does not select production database-authentication, network or RPC topology.
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

Both storage authorities independently construct the same `canonical_checkpoint_payload` shape from:

- domain;
- tenant;
- `F`;
- checkpoint ID;
- checkpoint generation;
- sealed flag;
- target count;
- target digest;
- target max ordinal.

Exact evidence proves:

```text
relocation_checkpoint_hmac_payload_cross_store=PASS
```

The target alone holds the HMAC signing key. Tier 1 has no copy of that key; it consumes a target-side yes/no verification capability. Therefore equal canonical bytes support verification without collapsing the issuer/verifier authority boundary.

### Production boundary

The exact UTF-8 length+hex encoding is a bounded evidence mechanism, not a mandatory production serialization. Another accepted representation is allowed only if it is deterministic, versioned, injective or equivalently unambiguous for every protected structured field and is independently revalidated.

## Relocation cross-authority protocol

Tier 1 locks placement before deriving `F`. `max(target)=F` is not treated as completeness. The target-owned checkpoint measures actual current target count/max/digest and is authenticated before Tier 1 can commit cutover authority.

Target lifecycle:

```text
open
  -> staging DML allowed
  -> seal fails if ANY row has ordinal > F

sealed
  -> ALL target-history DML rejected
  -> checkpoint set cannot change
  -> target cannot self-activate

Tier 1 activation commit
  -> target checkpoint verified through target-owned verifier capability
  -> no remote call while Tier 1 authority locks are held
  -> placement moves to target and exact activation_grant is committed atomically

activated
  -> only after target verifies the exact Tier 1 grant
  -> existing target history immutable
  -> INSERT <= F rejected
  -> new append > F allowed
```

The target signing key never exists in Tier 1. The target verification principal cannot read the target key; the Tier 1 grant-verification principal cannot read grant/placement tables. The evidence verifier roles expose only bounded yes/no functions.

The Tier 1 grant is bound to:

```text
tenant
F
checkpoint id
checkpoint generation
target attestation
successor placement version
committed state
```

The matrix explicitly proves:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_target_verifier_cannot_read_attestation_key=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_target_cannot_self_activate_before_tier1_grant=PASS
relocation_premature_mark_keeps_future_insert_blocked=PASS
relocation_tier1_activation_grant_committed=PASS
```

It also injects a conflicting grant **after the placement UPDATE path has begun**. The duplicate-key failure rolls the transaction back and proves:

```text
relocation_activation_commit_conflict_rolls_back=PASS
relocation_activation_conflict_preserves_fenced_placement=PASS
relocation_activation_conflict_did_not_replace_grant=PASS
relocation_conflicting_grant_cannot_activate_target=PASS
relocation_activation_conflict_keeps_target_sealed=PASS
relocation_activation_grant_placement_atomicity=PASS
```

Thus no partial successor authority is admitted if the local Tier 1 commit fails.

### Evidence transport boundary

This C2 harness uses random verifier LOGIN credentials and PostgreSQL `dblink` with bounded connection/statement timeouts to exercise independent authorities. Remote verification occurs before local authority locks, and uncertainty/failure returns false. This is **not** a production topology decision. Production may use a service/API, asymmetric signature verifier, KMS-backed verification or another mechanism only if it preserves:

- target-only mint/sign authority;
- verifier without mint capability;
- bounded fail-closed cross-authority verification;
- no long local transaction around a remote call;
- exact durable activation-grant binding;
- atomic Tier 1 grant + placement commitment;
- target activation only after the committed grant is independently verified.

The wider relocation matrix still covers internal gaps, canonical payload mismatch, fabricated attestation, seal-vs-DML race, pre-seal/post-seal `>F`, DELETE, tenant move, activated pre-fence mutation and stale source rejection.

## Fresh-cluster restore and capacity boundary

Restore occurs in a new PostgreSQL/Timescale cluster. The harness proves zero JLMirror roles before bootstrap, reconstructs the minimum five-role topology, restores 100,004 history rows and both Timescale jobs, validates ownership and repeats isolation/escalation attacks after restore and after restored-job execution.

The same security profile is exercised for bounded capacity mechanism fitness. Production throughput, retention, cardinality, cost, loss/buffer/checkpoint budgets, chunk/compression/refresh schedules, SLOs and topology remain `OPEN-REL-020` C3.

## Exact empirical anchor before reviewer documentation

```text
HEAD
e082cca72c13c725b0ffa837693ba73eb92ceb7e

JLMIRROR Deterministic Assurance #2034
run id 33223301992
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #85
run id 33223301930
SUCCESS
```

The #85 extended run includes the target-only signing authority, verifier/mint separation, Tier 1 durable activation grant, premature-target-activation negatives, grant/placement atomic rollback injection, structured-serialization evidence and all previous authority/isolation/recovery/relocation vectors. This anchor is provenance only: documentation changes create a new HEAD and require both workflows again.

## Governance state

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication topology or authorize merge. Exact-final-HEAD CI, Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
