# D2 / OPEN-REL-030 — Bounded Conformance Evidence

This directory contains the governed C2 evidence package for `OPEN-REL-030`.

The bounded C2 Track B mechanism/profile has been **explicitly accepted**. This directory still does not constitute the Monitoring production implementation, production deployment authority, Wave 4 authorization, production topology selection, OPEN closure authorization, or merge authorization.

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
Material finding classes    53
History hardening modules   7 (004–010)
Merge authorization         not_granted
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

Because recording acceptance changes the Git HEAD, every accepted-state successor HEAD must itself pass exact-head CI + Native + fresh Codex assurance before merge-readiness can be asserted.

## Empirical anchors

History/mechanism anchor through material class #51:

```text
51cddbca4258a78ed8f4a3254ff54a01a332e933
Deterministic Assurance #2261 — SUCCESS — run 33283602526
OPEN-REL-030 Conformance #198 — SUCCESS — run 33283602532
```

Governance repair anchor for material class #52:

```text
0f0d72ca443ff2c87f44409e65f893c99b530aed
Deterministic Assurance #2295 — SUCCESS — run 33285211010
OPEN-REL-030 Conformance #215 — SUCCESS — run 33285210993
```

#52 makes `merge_authorization` explicit governed state. The extended runner derives the terminal `merge=...` output from the manifest, and the workflow guard rejects hard-coded merge authorization output.

Timescale fresh-restore repair anchor for material class #53:

```text
d20e83780d1c370e96a5a960f27a6a959f7a320c
Deterministic Assurance #2309 — SUCCESS — run 33286313003
OPEN-REL-030 Conformance #222 — SUCCESS — run 33286312997
```

#53 requires source↔restore policy-job cardinality agreement, coverage of both expected restored job targets, execution of every restored policy job, and only then the full post-job tenant/escalation attack matrix.

## Accepted evidence architecture

### Tier 1 / history

Track B accepts immutable canonical observation identity/content, owner-controlled source/poll authority, platform-order current-state CAS, owner-current reconciliation, dataset-revision fencing, retained-watermark revalidation, NULL-cutoff rejection, and one canonical authority lock order `provider_authority → stream_state` across mutation/sweep/finalization. Worker paths cannot bypass the wrappers. Modules `004–010` remain ordered and anti-orphan guarded.

### Physical PITR / restored authority

Recovery authority remains external to restored database state, effect-bound, active-authority-bound and single-winner per canonical recovery boundary. PGDATA copying alone cannot duplicate effective authority. Claim alone leaves local truth at R. Verified surviving material is required before effect/successor application. Claim/verify/fetch and post-enrollment clone paths use bounded async response semantics, real established TCP blackhole tests and one-shot session retirement without synchronous timeout cleanup.

### Timescale / Tier 2

The accepted Track B profile is the mediated shared-history Timescale candidate. Tenant/application principals do not directly access shared raw history, CAGGs or internal materialization. Privileged automation remains a separate cross-tenant trust boundary. Fresh-cluster restore remains mandatory evidence. Its restored policy-job inventory must match the source evidence cardinality and cover `shared_history` plus `shared_hourly`; every restored policy job must execute successfully before the post-job tenant/escalation attack matrix is evaluated.

### Relocation

Relocation preserves total/injective typed canonicalization, target-originated checkpoint authority, verifier-without-mint separation, restricted capability state, source lock-before-F, exact target completeness, atomic placement+activation-grant commitment, exact-grant target activation, caller-local response deadlines, no synchronous timeout cleanup, and real TCP blackholes in both directions.

### Governance state

Decision, acceptance, closure, Wave 4, production authority and merge authorization are machine-readable governed state. Conformance may not invent or hard-code those current authorization values; the terminal governed-decision statement must derive them from the manifest.

## Material findings

All **53 material finding classes** remain closed/documented. `DECISION_REVIEW.md` is the normative enumeration. The latest five are:

- **#49:** retained finalized watermark requires current-revision revalidation through the retained historical bound;
- **#50:** NULL finalization cutoff is rejected with SQLSTATE `22004`;
- **#51:** mutation/sweep/finalization use one canonical `provider_authority → stream_state` lock order with concurrent deadlock falsification;
- **#52:** merge authorization can no longer be hard-coded by conformance; `merge_authorization=not_granted` is explicit governed state and terminal output is manifest-derived;
- **#53:** fresh restore can no longer validate only one Timescale policy job; all restored jobs are enumerated and executed before post-job security validation.

## Files

- `STATE.md` — accepted decision state and authorization boundaries.
- `DECISION_REVIEW.md` — normative acceptance record and all 53 material findings.
- `EVIDENCE_MANIFEST.json` — machine-readable accepted state, evidence and authorization basis.
- `sql/d2-open-rel-030/*` — executable Tier 1/history/Timescale evidence mechanisms.
- `tools/open_rel_030/*` — orchestration, recovery, clone, restore, relocation, concurrency and governed-state conformance harnesses.
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
