# D2 — OPEN-REL-030 Monitoring Conformance Evidence

**Status:** experimental C2 bounded-spike harness; no production authority  
**Canonical base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Branch:** `evidence/open-rel-030-monitoring-conformance`  
**Decision under test:** `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`

## Purpose

This package supplies reproducible, falsifiable evidence for the two physical-mechanism questions left open by `OPEN-REL-030` without implementing the Monitoring product vertical:

1. **Tier 1:** prove the selected PostgreSQL transactional durable-acceptance pattern against real concurrent database sessions rather than the Wave 2 in-process reference ledgers;
2. **Tier 2:** attack the TimescaleDB candidate under JLMIRROR's accepted tenant-isolation model and identify which concrete feature profiles are eligible or ineligible.

The package is an evidence laboratory only. It creates ephemeral databases, runs assertions, emits logs/results, and exits. It has no credentials, production connectivity, product API, long-lived state or mutation authority over the repository.

## Non-negotiable boundaries

- Product/domain/API/event semantics remain unchanged.
- Current Monitoring state remains a Tier 1 responsibility.
- TimescaleDB remains a **candidate**, not canonical, until the complete required matrix is green and the decision record is separately updated/reviewed/accepted.
- A single demonstrated cross-tenant row leak fails the candidate profile under test.
- A failed or unsupported Timescale feature combination is evidence, not something the harness may hide with `continue-on-error`.
- Provider event time is metadata, never the Tier 1 current-state ordering authority.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE` continues to apply to every PR carrying this evidence.

## Reproducibility profile

The CI harness uses immutable container-image index digests and records the database/extension versions observed at runtime.

Evaluation images are deliberately **evidence dependencies**, not production stack selections:

- PostgreSQL 17.11 Alpine — Tier 1 real-database semantics;
- TimescaleDB 2.29.2 on PostgreSQL 17 — Tier 2 candidate evaluation.

Changing either image is a new evidence run and does not silently inherit a previous conclusion.

## Evidence layout

```text
implementation/d2-open-rel-030/
  README.md
  STATE.md
  EVIDENCE_MANIFEST.json
sql/d2-open-rel-030/
  001_tier1_acceptance.sql
  002_tier1_assertions.sql
  010_timescale_candidate.sql
tools/open_rel_030/
  tier1_concurrency.py
  run_conformance.sh
.github/workflows/
  open-rel-030-conformance.yml
```

## Tier 1 coverage in this harness

The first executable slice proves or falsifies:

- atomic create-or-observe under independent PostgreSQL connections;
- exactly one durable historical-projection obligation per first accepted canonical observation;
- current-state compare-and-set by owner ordering token, never `observed_at`;
- repeated-current semantic idempotence while allowing the ordering fence to advance;
- an already-accepted historical observation remaining eligible to become current later;
- stale/out-of-order candidates not regressing current state;
- transaction rollback at injected crash points around observation, history intent, current-state CAS and transition signal;
- durable backlog accumulation while Tier 2 is absent.

This deliberately closes the real-multi-connection hole recorded in `implementation/wave-2/KNOWN_DEFERRED_ITEMS.md`; it does **not** retroactively turn Wave 2 reference models into a production runtime.

## Tier 2 profiles under test

### Profile A — direct pooled hypertable with RLS

The harness proves ordinary rowstore RLS behavior for a normal trusted application runtime and then probes the Timescale feature combinations that make the candidate attractive.

Current Timescale documentation states that columnstore chunks do not support RLS, and continuous-aggregate guidance excludes RLS-enabled source hypertables. The harness therefore treats direct pooled `RLS + columnstore` and direct pooled `RLS + continuous aggregate` as capability probes that must be proven rather than assumed.

### Profile B — mediated aggregate/query surface

If a shared Timescale object cannot itself preserve the accepted RLS boundary, the only eligible pooled alternative in this spike is a separately hardened mediated surface where tenant-facing reporting principals:

- have no direct privilege on the raw hypertable, continuous aggregate or internal materialization;
- are tenant-bound outside caller-writable SQL state;
- cannot `SET ROLE` into an owner/bypass role;
- cannot use `SET`, `set_config`, `search_path` or helper shadowing to change tenant authority;
- can execute only a narrowly scoped `SECURITY DEFINER` reader with fixed safe `search_path` and explicit tenant binding.

Passing this profile would establish only that the **mediation class** is technically viable for the pinned candidate version. It would not yet settle production topology, capacity numerics, operational ownership or whether JLMIRROR should choose that complexity over another telemetry store.

## Still required before OPEN-REL-030 can close

This initial executable harness is intentionally staged. The final D2 gate still requires the full `OPEN-REL-030` evidence set, including:

- client-ack ambiguity/replay around commit;
- PITR / restore fence `R,F]` evidence;
- Zabbix poll-epoch continuity across recovery and relocation;
- explicit late-history gap/watermark reconciliation;
- relocation with one authoritative Tier 1 path and reconciled Tier 2 watermark;
- Timescale background-job, migration/restore and role-change attack matrix;
- capacity/query evidence under the exact same security profile used for isolation.

Until those are present, `STATE.md` must remain `OPEN / PARTIAL EVIDENCE` and `OPEN-REL-030` must remain unclosed.
