# D2 — OPEN-REL-030 Monitoring Conformance Evidence

**Status:** evidence complete — ready for exact-HEAD decision review; no production authority  
**Canonical base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Branch:** `evidence/open-rel-030-monitoring-conformance`  
**Decision under test:** `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`  
**Track B acceptance:** not granted  
**Wave 4 implementation authorization:** not granted

## Purpose

This package supplies reproducible, falsifiable evidence for the physical-mechanism questions left open by `OPEN-REL-030` without implementing the Monitoring product vertical:

1. **Tier 1:** prove the selected PostgreSQL transactional durable-acceptance pattern against real concurrent database sessions and recovery/relocation faults;
2. **Tier 2:** attack the TimescaleDB candidate under JLMIRROR's accepted tenant-isolation model and identify which concrete feature profiles are eligible or ineligible.

The package is an evidence laboratory only. It creates ephemeral databases, runs assertions, emits logs/results, and exits. It has no production connectivity, product API, long-lived production state or product mutation authority.

## Non-negotiable boundaries

- Product/domain/API/event semantics remain unchanged.
- Current Monitoring state remains a Tier 1 responsibility.
- TimescaleDB remains a **candidate recommendation**, not canonical, until exact-final-HEAD review is clean and Track B is explicitly accepted.
- A single demonstrated cross-tenant row leak fails the candidate profile under test.
- A failed or unsupported Timescale feature combination is evidence, not something the harness may hide.
- Provider event time is metadata, never the Tier 1 current-state ordering authority.
- `OPEN-REL-020` remains the owner of production telemetry capacity/numeric envelopes.
- The evidence-only SHA-256/HMAC-SHA-256 checkpoint does not select a production KMS/HSM/secret-management topology.
- `ts_automation_owner` is a LOGIN cross-tenant privileged infrastructure principal in the evaluated Timescale profile; absence of a password credential is not equivalent to `NOLOGIN` and is not proof of production authentication/admission isolation.
- Production database connection/authentication topology must prevent tenant/application principals from authenticating as or assuming `ts_automation_owner`; widening that boundary requires fresh security/conformance review.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE` continues to apply.

## Reproducibility profile

The CI harness uses immutable container-image index digests and records the database/extension versions observed at runtime.

Evaluation images are deliberately **evidence dependencies**, not production stack selections:

- PostgreSQL 17.11 Alpine — Tier 1 real-database semantics, ambiguity, reconciliation, PITR and relocation;
- TimescaleDB 2.29.2 on PostgreSQL 17 — Tier 2 isolation, jobs, fresh-cluster restore, authenticated target checkpoint/freeze, relocation and bounded capacity evaluation.

Changing either image requires new evidence and does not silently inherit a previous conclusion.

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

## Tier 1 coverage

The executable package proves or falsifies:

- atomic create-or-observe under independent PostgreSQL connections;
- immutable canonical observation content under stable identity;
- exactly one durable historical-projection obligation per first accepted observation;
- active source generation and poll epoch resolved from owner-controlled state inside the transaction;
- exact durable `live` poll claim required for current-state candidacy;
- current-state compare-and-set by owner ordering authority, never provider event time;
- repeated-current semantic idempotence;
- history-first/current-later independence;
- stale/predecessor source authority rejection;
- transaction rollback across injected crash points;
- durable Tier 2-down backlog responsibility;
- post-COMMIT ambiguity/retry convergence;
- history reconciliation that proves contiguous coverage from `supported_history_floor`, not merely the greatest sweep endpoint;
- minimum reconciliation/provider snapshot currentness before history finalization;
- explicit durable `gap` rather than false completeness when history cannot be recovered;
- physical PostgreSQL PITR to a committed `R` with surviving `(R,F]` reconciliation;
- relocation source fencing that locks authority before deriving `F`;
- verification of a target-owned authenticated sealed canonical-payload checkpoint before target activation.

## Late-history completeness

`max(reconciliation window_to)` is explicitly not a completeness watermark.

The evidence model stores each reconciliation run's exact interval and provider snapshot. Continuous coverage is derived only from runs that begin at or cover the owner's `supported_history_floor` and then overlap/touch without a hole. The first unswept interval stops coverage advancement.

The negative matrix proves that:

- a high-only `11:55..12:00` sweep cannot finalize because it is not anchored at the supported history floor;
- `supported_history_floor..10:00` plus `11:55..12:00` cannot finalize even though `max(window_to)=12:00`, because `10:00..11:55` remains unswept;
- bridging `10:00..12:00` recovers the delayed row and creates continuous coverage through `12:00`;
- covering sweeps at provider snapshot `12:15` cannot satisfy a finalization that requires reconciliation evidence current through `12:16`;
- unrecoverable retention loss stays `gap`, never `complete`.

The accepted evidence path therefore requires both **contiguous interval coverage** and **sufficient reconciliation snapshot currentness**.

## Tier 2 classification

### Rejected direct pooled feature profiles

On the evaluated Timescale profile:

- direct pooled `RLS + columnstore` is rejected with SQLSTATE `0A000`;
- direct pooled `RLS + continuous aggregate` is rejected with SQLSTATE `0A000`.

These are capability outcomes, not bypassable test failures.

### Conformant candidate — mediated shared history

The surviving candidate profile requires:

- no direct tenant-facing privilege on shared raw history, continuous aggregates or internal materialization;
- tenant binding outside caller-writable SQL state;
- hardened `SECURITY DEFINER` reader with fixed safe `search_path`;
- `ts_owner` as NOLOGIN mediation/mapping/checkpoint/function owner;
- separate least-privilege LOGIN `ts_automation_owner` where Timescale automation requires it;
- explicit classification of `ts_automation_owner` as **cross-tenant privileged infrastructure**, because it owns shared job-bearing objects;
- no password credential or elevated role attributes on the evidence automation owner, while explicitly recognizing that `PASSWORD NULL` is not `NOLOGIN` and does not by itself prevent authentication under every `pg_hba`/socket topology;
- production connection/authentication admission that prevents tenant/application principals from authenticating as or assuming the automation owner;
- no runtime/reporting membership in either owner;
- repeated direct-read, role, membership, tenant-crossing, `SET`/`set_config`, session-authorization, BYPASSRLS and search-path attacks.

The evidence container validates database role attributes, memberships, object ownership and attack behavior. It does **not** claim that its ephemeral local authentication configuration proves a future production `pg_hba`, local socket, peer/trust or network-admission topology. That admission boundary is a required deployment invariant of this conformed profile.

Assigning an application-usable credential, widening connection admission, granting tenant/application membership, or otherwise exposing `ts_automation_owner` to ordinary application/tenant principals invalidates the profile until fresh review/evidence.

## Fresh-cluster restore

Restore evidence uses a **new PostgreSQL/Timescale cluster**, not another database in the source cluster.

The test proves zero JLMirror `ts_*` roles exist first, reconstructs exactly the minimum evidence role topology, restores the source database, verifies object/function/job ownership, verifies the automation owner still has no password credential, and repeats the full attack matrix after restore and again after a restored background job runs.

This prevents inherited source-cluster `pg_authid`/`pg_auth_members` state from masquerading as restore correctness.

## Relocation completeness and currentness

Relocation uses two independently controlled fences:

1. **Source fence:** source placement authority is locked before `F` is derived, so an acceptance already holding source authority completes first and is included in `F`.
2. **Target checkpoint:** target cutover requires a target-owned authenticated checkpoint that is sealed against further mutation at or below `F` before Tier 1 activation.

### Canonical complete-set fingerprint

Source and target compare an ordered SHA-256 fingerprint over the canonical numeric observation evidence profile:

- accepted ordinal;
- observation identity;
- metric definition identity;
- normalized UTC observation timestamp;
- normalized numeric value.

This deliberately fixes the prior identity-only weakness. A negative vector keeps identity/ordinal coverage intact but changes `observed_at`; the target remains `incomplete`.

Future implementation for other accepted Monitoring payload kinds must define deterministic canonical serialization over **all immutable accepted payload fields**. The numeric evidence profile is not permission to omit string/text/log/boolean/integer payload semantics later.

### Authenticated target checkpoint

The target measures its actual count, maximum ordinal and SHA-256 canonical-payload digest under target-owned authority. The checkpoint facts are authenticated with domain-separated HMAC-SHA-256 (`open-rel-030-target-checkpoint-v1`). Tier 1 verifies the attestation and compares the target set to the frozen authoritative source set.

A fabricated target field with a genuine old HMAC is rejected. Caller-provided target facts alone can never create `complete`.

The HMAC key in this harness is ephemeral evidence plumbing. Production key custody, KMS/HSM/TEE backend, distribution and rotation are **not selected by D2**.

### Seal and freeze

The target checkpoint has an `open -> sealed -> activated` lifecycle with no unseal path.

Target-history DML acquires shared target-control authority. Seal acquires exclusive target-control authority **before** calculating the digest. This removes the measure→seal race:

- a DML transaction already holding authority finishes before seal measurement and is included;
- a DML transaction starting after seal authority is acquired blocks, then observes the sealed state and is rejected for data at/below `F`.

The freeze validates both OLD and NEW tenant scopes for UPDATE, preventing a protected row from being moved out of a sealed tenant. Target history/checkpoint authority is owned by NOLOGIN `ts_owner`; the projection writer cannot disable the freeze or read the attestation key.

### Negative matrix

The executable relocation matrix includes:

- `max(target)=F` with internal gap → `incomplete`;
- same identities/ordinals with canonical payload mismatch → `incomplete`;
- fabricated checkpoint facts → attestation rejected;
- seal racing target mutation → mutation blocks then rejects;
- sealed DELETE → rejected;
- sealed cross-tenant UPDATE → rejected;
- projection writer reads attestation key → rejected;
- projection writer disables freeze → rejected;
- stale source after cutover → rejected;
- tenant-facing direct relocation-history read → rejected.

Only the authenticated sealed checkpoint with complete canonical-payload equivalence permits cutover.

## Empirical reviewer anchor

Before reviewer-document mutation, the hardened executable package passed:

```text
HEAD
747e0bb84a7b617e7ca97eb835ea0f0d64ac804d

JLMIRROR Deterministic Assurance #1965
run id 33200595850
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #51
run id 33200595957
SUCCESS
```

This anchor is provenance only. The exact final package HEAD created by documentation/classification changes must independently pass both workflows again.

## Capacity boundary

The same mediated security profile is exercised with 100,004 historical rows, columnstore conversion, continuous aggregate, background policies, fresh-cluster restore and a mediated query path.

Those measurements are bounded C2 mechanism-fitness evidence only. Production throughput, retention, cardinality, buffer/loss/checkpoint, cost, chunk/compression/refresh schedules, SLOs and topology remain `OPEN-REL-020` C3.

## Governance state

Every mandatory D2 vector is represented in the reproducible package, but evidence completion does not accept the decision.

The authoritative classification/recommendation lives in:

- `EVIDENCE_MANIFEST.json`
- `STATE.md`
- `DECISION_REVIEW.md`

Every classification-changing commit must rerun both exact-HEAD gates before review or acceptance. Only a later explicit Track B acceptance can make `OPEN-REL-030` selected/conformed, and Wave 4 product implementation still requires a separate explicit authorization after that.
