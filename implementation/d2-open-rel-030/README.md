# D2 / OPEN-REL-030 — Bounded Conformance Evidence

This directory contains the governed C2 evidence package for `OPEN-REL-030`.

The bounded C2 Track B mechanism/profile has now been **explicitly accepted**. This directory still does not constitute the Monitoring production implementation, production deployment authority, Wave 4 authorization, production topology selection, OPEN closure authorization, or merge authorization.

## Governed state

```text
Evidence state              complete
Decision disposition        accepted_track_b
Track B acceptance          granted
Closure claim               false
Wave 4 authorization        not_granted
Production authority        none
Production versions         not selected
Production capacity         OPEN-REL-020
Material finding classes    51
History hardening modules   7 (004–010)
Merge                       not authorized
```

## Acceptance basis

Explicit Track B authorization was granted after this exact stationary decision-review HEAD passed every required gate:

```text
622c094c9274a778d1c21c5976dd3b2ca7b4cedf
Deterministic Assurance #2273 — SUCCESS — run 33283807517
OPEN-REL-030 Conformance #204 — SUCCESS — run 33283807551
Native Assurance review 5059581679 — P0=0 / P1=0 / P2=0
Fresh Codex comment 5465822591 — CLEAN / no major issues
Inline review threads — 0 unresolved
PR mergeable — true
```

Because recording acceptance changes the Git HEAD, the accepted-state commit must itself pass the same exact-head CI + Native + fresh Codex assurance cycle before merge-readiness can be asserted.

## Empirical mechanism anchor

```text
51cddbca4258a78ed8f4a3254ff54a01a332e933
Deterministic Assurance #2261 — SUCCESS — run 33283602526
OPEN-REL-030 Conformance #198 — SUCCESS — run 33283602532
```

That anchor executes all mandatory vectors, all seven history hardening modules, physical PITR/recovery, post-enrollment clone, Timescale restore/jobs and Tier1↔Tier2 relocation, ending with `open_rel_030_extended_conformance=PASS`.

## Accepted evidence architecture

### Tier 1 / history

Track B accepts immutable canonical observation identity/content, owner-controlled source/poll authority, platform-order current-state CAS, owner-current reconciliation, dataset-revision fencing, retained-watermark revalidation, NULL-cutoff rejection, and one canonical authority lock order `provider_authority → stream_state` across mutation/sweep/finalization. Worker paths cannot bypass the wrappers. Modules `004–010` remain ordered and anti-orphan guarded.

### Physical PITR / restored authority

Recovery authority remains external to restored database state, effect-bound, active-authority-bound and single-winner per canonical recovery boundary. PGDATA copying alone cannot duplicate effective authority. Claim alone leaves local truth at R. Verified surviving material is required before effect/successor application. Claim/verify/fetch and post-enrollment clone paths use bounded async response semantics, real established TCP blackhole tests and one-shot session retirement without synchronous timeout cleanup.

### Timescale / Tier 2

The accepted Track B profile is the mediated shared-history Timescale candidate. Tenant/application principals do not directly access shared raw history, CAGGs or internal materialization. Privileged automation remains a separate cross-tenant trust boundary. Fresh-cluster restore and tenant/escalation/job matrices remain mandatory evidence.

### Relocation

Relocation preserves total/injective typed canonicalization, target-originated checkpoint authority, verifier-without-mint separation, restricted capability state, source lock-before-F, exact target completeness, atomic placement+activation-grant commitment, exact-grant target activation, caller-local response deadlines, no synchronous timeout cleanup, and real TCP blackholes in both directions.

## Material findings

All **51 material finding classes** remain closed/documented by the accepted mechanism. `DECISION_REVIEW.md` is the normative enumeration. The latest three are:

- **#49:** retained finalized watermark requires current-revision revalidation through the retained historical bound;
- **#50:** NULL finalization cutoff is rejected with SQLSTATE `22004`;
- **#51:** mutation/sweep/finalization use one canonical `provider_authority → stream_state` lock order with concurrent deadlock falsification.

## Files

- `STATE.md` — accepted decision state and authorization boundaries.
- `DECISION_REVIEW.md` — normative acceptance record and all 51 material findings.
- `EVIDENCE_MANIFEST.json` — machine-readable accepted state, evidence and authorization basis.
- `sql/d2-open-rel-030/*` — executable Tier 1/history/Timescale evidence mechanisms.
- `tools/open_rel_030/*` — orchestration, recovery, clone, restore, relocation and concurrency falsification harnesses.
- `.github/workflows/open-rel-030-conformance.yml` — exact-head structural + empirical conformance gate.

## Post-acceptance gate rule

The accepted-state exact HEAD must independently pass:

1. JLMIRROR Deterministic Assurance;
2. JLMIRROR OPEN-REL-030 Conformance;
3. Native Assurance with P0/P1/P2 all zero;
4. a fresh adversarial Codex review on that exact stationary SHA;
5. zero unresolved review threads.

Passing those gates validates the exact accepted-state commit. It still does **not** authorize Wave 4, production deployment/topology, OPEN closure, or merge.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
