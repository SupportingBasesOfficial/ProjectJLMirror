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
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE` continues to apply.

## Reproducibility profile

The CI harness uses immutable container-image index digests and records the database/extension versions observed at runtime.

Evaluation images are deliberately **evidence dependencies**, not production stack selections:

- PostgreSQL 17.11 Alpine — Tier 1 real-database semantics, ambiguity, reconciliation, PITR and relocation;
- TimescaleDB 2.29.2 on PostgreSQL 17 — Tier 2 isolation, jobs, fresh-cluster restore, relocation and bounded capacity evaluation.

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

The final executable package proves or falsifies:

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
- relocation source fencing that locks authority before deriving `F`.

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
- `ts_owner` as NOLOGIN mediation/mapping/function owner;
- separate least-privilege LOGIN `ts_automation_owner` for Timescale background-job ownership, with no password credential or elevated role attributes;
- no runtime/reporting membership in either owner;
- repeated direct-read, role, membership, tenant-crossing, `SET`/`set_config`, session-authorization, BYPASSRLS and search-path attacks.

## Fresh-cluster restore

Restore evidence uses a **new PostgreSQL/Timescale cluster**, not another database in the source cluster.

The test proves zero JLMirror `ts_*` roles exist first, reconstructs exactly the minimum evidence role topology, restores the source database, verifies object/function/job ownership, verifies the automation owner still has no password credential, and repeats the full attack matrix after restore and again after a restored background job runs.

This prevents inherited source-cluster `pg_authid`/`pg_auth_members` state from masquerading as restore correctness.

## Relocation completeness

Relocation uses two independent protections:

1. source placement authority is locked before `F` is derived, so an acceptance already holding the source-authority lock completes first and is included in `F`;
2. target cutover requires a durable complete-set receipt over authoritative count + ordered observation-identity digest + target count + target digest + target maximum ordinal.

A negative vector deliberately makes `max(target)=F` while lower authoritative rows are missing. The receipt remains `incomplete` and activation is rejected. `max=F` is explicitly not accepted as completeness evidence.

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
