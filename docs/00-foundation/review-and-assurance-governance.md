# Review and Assurance Governance

**Status:** PROPOSED  
**Authority anchor:** accepted `main@6d8550b67ddeb6ca1ecac71df36a1185cd3b3c92`  
**Scope:** repository-wide review, assurance, automated analysis and merge-gate governance  

## Purpose

This document defines how JLMIRROR produces, evaluates and preserves review and assurance evidence without making any reviewer, AI model, security scanner, CI product or external service a normative authority or a single point of progression failure.

It extends the Engineering Charter, Decision Policy, Document Governance and accepted post-Phase-10 roadmap. It does not weaken any accepted Product, Requirements, Security, Quality, ADR, System Design, Data Architecture, API, event-contract, reliability or recovery invariant.

The goal is deterministic project-state awareness, reproducible exact-HEAD review, adversarial semantic validation, machine-assisted evidence, controlled correction and explicit user/operator merge authorization.

## Core law

```text
TOOL OUTPUT
!=
NORMATIVE AUTHORITY
```

and:

```text
REVIEW OF SHA A
!=
VALIDATION OF SHA B
```

and:

```text
AUTOMATION MAY OBSERVE, ANALYZE, REPORT AND BLOCK
AUTOMATION SHALL NOT SILENTLY MUTATE CANONICAL PROJECT STATE
```

and:

```text
READY FOR MERGE
!=
AUTHORIZED TO MERGE
```

## Authority model

The repository remains the canonical source of truth.

Reviewers and tools produce **evidence**. They do not own Product decisions, requirements, invariants, architecture, security authority, recovery authority, implementation authority or merge authority merely by producing a result.

Accepted repository hierarchy remains authoritative:

1. accepted Product, Requirements and invariants;
2. accepted Security and Quality requirements;
3. accepted ADRs and contracts;
4. accepted System, Data and Platform design;
5. implementation.

A reviewer may discover that an accepted higher-level authority needs correction. The reviewer SHALL NOT silently redefine it in a lower-level document or implementation. The owning authority must be corrected explicitly through governance.

## Tool independence

No named external reviewer, AI model, code-review service, security scanner, CI provider or commercial plan is a mandatory normative authority unless a later accepted decision explicitly establishes such a dependency and justifies its operational cost and failure behavior.

In particular:

- external AI/code-review availability SHALL NOT be a permanent project-progression dependency;
- quota exhaustion, latency, outage, account limitation or vendor policy change is not a clean-review signal;
- absence of one external reviewer does not automatically block progression when the required assurance properties can be proven through the accepted native assurance gate;
- availability of an external reviewer does not permit bypassing deterministic repository-state checks, panoramic review or merge authorization;
- a later valid external finding remains evidence that must be evaluated even if a prior native gate was clean.

External review is therefore **additional evidence**, not the only path to assurance. It is described as independent evidence only when review provenance actually demonstrates the relevant independence; use of a different service name, model endpoint or execution time does not by itself prove organizational, implementation or decision independence.

## Exact project-state law

Every material review, audit, acceptance recommendation and merge-readiness statement SHALL identify the exact repository state it covers.

At minimum, the evidence record identifies:

- repository;
- base branch and base SHA;
- review branch;
- exact HEAD SHA;
- changed-file scope;
- commit count or equivalent delta identity;
- mergeability/status where relevant;
- applicable upstream authorities;
- review/audit timestamp or ordered repository evidence;
- unresolved valid findings and review threads.

Before continuing work based on a previous review, current repository state is re-read from the repository. Conversation memory, local notes, screenshots, a prior PR body or an earlier review are not sufficient proof of current HEAD.

If HEAD changes after a clean review, the prior clean result remains historical evidence only.

## State-transition discipline

The assurance system distinguishes:

```text
OBSERVED HEAD
REVIEWED HEAD
CORRECTED HEAD
FINAL-REVIEWED HEAD
READY FOR MERGE
MERGE AUTHORIZED
MERGED
```

No state is inferred from another without evidence.

`mergeable=true` is a Git hosting condition, not project merge authorization.

An open socket, successful CI run, clean scanner result, AI statement, reaction emoji, quota message or stale review cannot advance normative state by itself.

## Automation mutation boundary

Repository automation is an **observer and enforcement surface**, not an autonomous project editor.

Automated systems MAY:

- read repository content and metadata;
- inspect diffs and dependency manifests;
- perform static analysis;
- scan for secrets or vulnerable dependencies;
- execute deterministic validation and tests;
- calculate coverage/consistency evidence;
- publish findings, annotations, alerts and status checks;
- fail a check;
- block advancement where branch/ruleset governance is configured;
- produce non-authoritative diagnostic artifacts.

Automated systems SHALL NOT, without a separate deliberate operator-authorized workflow whose resulting mutation is itself reviewed as a new HEAD:

- edit repository files;
- commit changes;
- push changes to normative branches;
- rewrite branch history;
- rebase branches;
- update dependencies automatically;
- open automated dependency-update or security-fix PRs as the ordinary security posture;
- apply auto-fix patches;
- resolve review threads;
- dismiss findings;
- change normative document status;
- merge pull requests;
- enable auto-merge for normative work.

The default JLMIRROR posture is therefore:

```text
SCAN -> REPORT/BLOCK -> DELIBERATE CORRECTION -> NEW HEAD -> RE-RUN ALL APPLICABLE GATES
```

not:

```text
SCAN -> AUTO-FIX -> SILENTLY CONTINUE
```

## Dependency-security automation

Dependency tooling is split into observation and mutation capabilities.

Allowed by default:

- dependency inventory/graph;
- vulnerability alerts;
- advisory correlation;
- dependency risk reports;
- deterministic dependency-policy checks.

Disabled by default unless a future accepted governance change explicitly authorizes a bounded workflow:

- automatic version-update PR generation;
- automatic vulnerability-fix PR generation;
- automatic dependency commits;
- automatic merge of dependency changes.

A vulnerable dependency creates a finding. It does not authorize a version choice.

The correction is evaluated for compatibility, supply-chain trust, behavior change, migration/rollback impact and relevant architectural constraints before the resulting new HEAD is accepted.

## Security-scanner posture

Static analysis, secret scanning, push protection, dependency alerts and similar repository-native or open-source scanners are evidence producers.

They MAY reject unsafe input or block progression when configured.

They SHALL NOT be interpreted as complete security proof.

A clean scanner result means only that the scanner did not report a covered finding for the analyzed state/profile. It does not prove absence of architectural, semantic, authorization, tenant-isolation, recovery, concurrency, business-logic or unknown vulnerability classes.

Security scanning therefore complements, rather than replaces, threat-model, contract, fault, recovery and adversarial review.

## Mandatory validation companion

`docs/00-foundation/review-and-assurance-validation.md` is the mandatory falsification and enforcement companion to this governance contract.

The governance contract and its validation companion form one assurance authority package. A change SHALL NOT claim conformance to this governance while omitting, bypassing or silently weakening applicable validation vectors, automation privilege boundaries, evidence-integrity rules or acceptance blockers defined by that companion.

Changes to either document require review of the other for semantic and coverage impact, even when only one file changes.

## Native Assurance Gate

When a bounded change requires adversarial review, the JLMIRROR Native Assurance Gate SHALL be executable without reliance on a particular external AI/code-review service.

The gate contains deterministic state verification plus deliberately separated adversarial review passes over the exact HEAD. Separation of passes improves falsification discipline but SHALL NOT be presented as external/organizational independence unless provenance proves that property.

### Pass 1 — Repository state and scope

Verify:

- exact base and HEAD;
- branch identity;
- changed-file scope;
- unexpected upstream/downstream modifications;
- current mergeability/status context;
- applicable accepted authorities;
- current valid review threads/findings.

Unexpected state divergence is resolved before semantic acceptance proceeds.

### Pass 2 — Authority and hierarchy

Attempt to prove that the change:

- modifies the correct owning authority;
- does not silently reinterpret a higher-level accepted decision;
- preserves Product/Requirement/Security/Quality precedence;
- does not convert implementation or tooling behavior into accidental architecture;
- keeps intentionally OPEN mechanism/vendor/numeric decisions OPEN where evidence is insufficient.

### Pass 3 — Semantic consistency

Review terminology, identities, states, transitions, invariants, ownership and cross-document meaning.

Search specifically for equivalent concepts with conflicting semantics, hidden aliases, conditional prose without machine-evaluable selectors, and one document permitting behavior another document forbids.

### Pass 4 — Security and privacy

Review:

- trust boundaries;
- principal and authority derivation;
- tenant isolation;
- confused-deputy paths;
- revocation/current-authority behavior;
- data classification/minimization;
- secrets/key material;
- disclosure/oracle/amplification risk;
- privileged operations;
- fail-closed behavior under unavailable trust evidence.

### Pass 5 — Failure, concurrency and ambiguity

Review:

- concurrent admission/execution;
- duplicate delivery;
- timeout;
- partial failure;
- crash boundaries;
- lease expiry;
- stale executors;
- retry/redelivery;
- external outcome ambiguity;
- poison/unsupported input;
- overload/backpressure and noisy-neighbor effects.

Timeout, restart, absence of local state or process death SHALL NOT be accepted as proof that a protected external effect did not occur.

### Pass 6 — Recovery continuity

Review restore/PITR, `(R,F]`, reconciliation, fencing, generation continuity, historical evidence interpretation and authority retirement.

Missing or older restored evidence SHALL NOT become proof of absence, safe duplicate, authorization, retry eligibility or effect eligibility.

### Pass 7 — Compatibility and mixed-version behavior

Review schema-identical semantic changes as well as representation changes.

Consider:

- rolling/mixed version;
- historical readers/profiles;
- replay;
- canonicalization changes;
- authority-generation changes;
- downgrade/rollback;
- deprecation/retirement;
- migration continuity.

### Pass 8 — Capacity, cost and abuse

Review all relevant bounded-resource dimensions, including tenant skew, concurrency, bytes, queued work, retry work, speculative work, replay/redrive, KMS/secret-store work, parser work, external calls and storage growth.

Unvalidated input SHALL NOT select a cheaper budget, a different tenant, a larger privileged scope or a more permissive workload class.

### Pass 9 — Governance and OPEN discipline

Verify:

- no unsupported generic waiver;
- every OPEN has owner, evidence and closure gate where required;
- `not_applicable`/`no_applicable_case` is evidence-backed and scoped;
- blocker dispositions are from accepted vocabularies;
- normative vs implementation/runtime evidence is not conflated;
- AI/tool output is not used as approval, waiver, vote or authority.

### Pass 10 — Cross-document propagation

For each material finding/correction, ask what **property** was missing rather than only which line was wrong.

Where applicable, propagate the property through the owning specialized contract and related:

- overview;
- semantic manifest/profile;
- validation matrix;
- security/privacy model;
- recovery model;
- compatibility classification;
- fault/abuse vectors;
- release/advancement blockers;
- OPEN registry;
- traceability/evidence model.

A local edit that leaves the same property absent from another enforcement surface is not complete.

### Pass 11 — Adversarial/falsification pass

Attempt to violate the proposed design through hostile or pathological scenarios rather than merely confirming intended behavior.

Test conceptual attacks and failures such as:

- cross-tenant identity collision;
- stale authority resurrection;
- conflicting same-ID content;
- ambiguous external effect followed by retry;
- parser/canonicalization skew;
- restore before surviving effect/evidence;
- compromised trust dependency becoming reachable again;
- overload classification before trusted canonical meaning;
- historical profile/verifier loss;
- mixed-version semantic split;
- automation/tool result being mistaken for authority.

### Pass 12 — Exact-final-HEAD clean-room pass

After all corrections, re-read the exact final HEAD from accepted upstream authority forward and attempt to identify material P0/P1/P2 issues without relying on the rationale that produced the corrections.

The purpose is to reduce author/reviewer confirmation bias.

This pass SHALL NOT claim independence equivalent to a separate human organization or separate external reviewer when the same reviewing system performs both roles. It is procedural adversarial separation, not fabricated organizational independence.

## Finding severity

Unless a more specialized accepted policy owns severity, assurance findings use:

- **P0 — catastrophic/fundamental:** direct compromise of core invariant or authority with catastrophic impact or acceptance impossible;
- **P1 — major/foundation:** material structural correctness, security, tenant-isolation, recovery or governance defect that blocks acceptance;
- **P2 — significant:** material gap capable of producing unsafe/inconsistent implementation, incomplete enforcement or important operational failure; blocks the relevant gate until resolved;
- **P3 — minor:** non-foundational clarity, maintainability or low-risk issue that may be tracked without blocking only when no accepted blocker rule says otherwise.

Severity is based on property/impact, not reviewer identity.

## Finding lifecycle

Canonical lifecycle:

```text
finding
-> identify missing property
-> identify owning authority
-> correct
-> panoramic propagation review
-> new HEAD
-> re-run applicable assurance passes
-> exact-final-HEAD clean-room review
-> only then close historical review evidence where justified
```

A finding is not considered closed merely because a line changed.

## Historical review threads

Historical threads remain evidence.

They SHALL NOT be resolved merely because current text appears different.

Resolution occurs only after:

1. the relevant correction exists in the current HEAD;
2. a later exact-HEAD validation confirms the property;
3. panoramic propagation finds no remaining material instance;
4. the thread is no longer needed to represent an unresolved valid finding.

A thread may be obsolete because scope changed, but that disposition must be evidence-backed rather than silently hidden.

## External-review unavailability

When an external reviewer is unavailable because of quota, outage, latency, product limitation or access loss:

- record the unavailability as operational context only;
- do not record it as clean, approved or failed semantic evidence;
- execute the Native Assurance Gate on the exact HEAD;
- preserve any previously discovered valid external findings;
- block acceptance if the native gate identifies any unresolved material P0/P1/P2;
- allow progression to `READY_FOR_MERGE` only when the required native gate and panoramic audit are clean and all other accepted prerequisites are satisfied;
- still require separate explicit merge authorization.

If a later external review reports a valid material finding before merge, the change returns to hardening and the final gate restarts on the new HEAD.

## Evidence classes

Assurance records distinguish:

### Normative design evidence

Proof that required semantics, ownership, constraints, test obligations, blockers and OPEN discipline are defined coherently.

### Implementation conformance evidence

Proof that future code/configuration implements the accepted design.

### Release evidence

Proof that a particular releasable artifact/version passed required controls.

### Production/runtime evidence

Proof produced by an executing environment, such as SLI measurements, restore exercises, runtime security evidence or operational outcomes.

A document review cannot fabricate implementation, release or production evidence.

## Deterministic repository checks

As repository structure becomes machine-evaluable, CI SHOULD increasingly verify properties such as:

- required manifest fields;
- allowed enum/disposition values;
- OPEN owner/evidence/closure-gate completeness;
- blocker mappings;
- profile/fault-vector bindings;
- traceability references;
- duplicate keys/identities;
- forbidden generic waiver values;
- invalid `not_applicable`/`no_applicable_case` use;
- unversioned semantic profiles;
- missing compatibility/security/recovery classifications;
- generated-schema/catalog consistency.

Deterministic checks reduce reviewer workload but do not replace semantic adversarial review.

## Future implementation-code scanning

When implementation code is authorized and introduced, security/static-analysis tooling SHOULD run against PRs and accepted branches where applicable.

Initial tooling may use repository-native no-cost capabilities available to public repositories or reviewed open-source scanners, subject to the same observer-only mutation boundary.

The exact scanner/vendor remains an implementation/tooling choice unless later accepted governance makes a specific mechanism mandatory.

Security workflow dependencies/actions SHALL be version-controlled and reviewed; security automation must not create an unreviewed supply-chain path with write authority over normative branches.

## Branch and merge posture

Normative branches SHOULD be treated as immutable-by-automation working states.

The project SHALL NOT rely on auto-merge for normative gates.

A merge-ready record identifies the exact reviewed HEAD.

If HEAD changes between `READY_FOR_MERGE` and merge authorization, readiness is invalidated until the new exact HEAD satisfies the applicable gate.

Where the merge API supports an expected-head condition, merge SHOULD be pinned to the reviewed HEAD.

Branch deletion is a separate lifecycle decision and is not automatically authorized by merge.

## Native gate result profile

A final assurance result SHOULD materialize at least:

```text
repository
base_sha
head_sha
scope
review_timestamp_or_ordered_evidence

state_scope_integrity
hierarchy_authority
semantic_consistency
security_privacy
tenant_trust
failure_concurrency_ambiguity
recovery_continuity
compatibility_mixed_version
capacity_cost_abuse
governance_open_discipline
cross_document_propagation
adversarial_falsification
final_clean_room

p0_count
p1_count
p2_count
p3_count
unresolved_threads_or_findings
external_review_context
panoramic_result

result = BLOCKED | HARDENING_REQUIRED | READY_FOR_MERGE
```

No result value authorizes merge by itself.

## Gate criteria

A bounded normative change may reach `READY_FOR_MERGE` only when:

- exact base/HEAD/scope are known and current;
- applicable accepted upstream authority is identified;
- deterministic checks required for the scope pass;
- all valid material P0/P1/P2 findings are resolved on the exact final HEAD;
- the required Native Assurance Gate passes;
- final panoramic security/recovery/capacity/compatibility/governance review is clean;
- historical threads/findings are dispositioned only after valid later evidence;
- no tool/AI result is being used as normative authority or generic waiver;
- mergeability/status constraints required by the hosting platform are satisfied;
- a separate explicit merge authorization has not yet been assumed.

After these conditions:

```text
READY_FOR_MERGE
```

Only an explicit authorized merge action may transition to:

```text
MERGED
```

## No generic assurance waiver

This document creates no generic authority to waive a material gate, security finding, recovery uncertainty, invalid OPEN, missing evidence or unresolved P0/P1/P2.

If a future exceptional process is required, it must be explicitly defined at the owning governance authority with scope, principal, evidence, expiry/review and non-bypassable constraints. The absence of such authority means no waiver exists.

## Recovery of assurance state

Lost, stale or incomplete assurance records are not equivalent to a clean review.

If repository history, CI evidence, review state or external evidence becomes unavailable, the project reconstructs what can be proven from canonical repository history and re-executes required checks where necessary.

A missing clean result is `unknown`, not `clean`.

## Relationship to AI-assisted review

AI systems MAY:

- identify candidate findings;
- compare documents;
- perform adversarial analysis;
- suggest tests;
- support panoramic review;
- classify possible propagation surfaces;
- produce non-authoritative assurance evidence.

AI systems SHALL NOT by themselves:

- accept a normative phase;
- approve a waiver;
- grant security/recovery authority;
- authorize merge;
- declare production readiness;
- silently mutate canonical state.

This preserves the accepted roadmap principle that AI-assisted analysis is diagnostic/evidence support rather than normative authority.

## Relationship to current post-Phase-10 work

Until this proposed governance is accepted, existing accepted repository authority remains unchanged.

If accepted, this governance and its mandatory validation companion become the permanent assurance path for current and future normative work, including corrective upstream gates and Phases 11–15, without requiring any particular external reviewer to be available.

Existing valid findings discovered by previous reviewers remain valid evidence and SHALL NOT be discarded merely because the reviewing mechanism changes.

The current Phase 11 ordering and upstream-correction requirements remain intact. This governance changes the **review mechanism dependency**, not the architectural phase sequence or merge authority.

## Fixed properties vs implementation choices

Fixed by this governance:

- exact-HEAD review discipline;
- repository-state-before-memory discipline;
- tool/reviewer non-authority;
- evidence-provenance discipline for any independence claim;
- external-review non-dependency;
- observer/blocker automation default;
- no silent automated mutation;
- mandatory assurance validation companion;
- finding-to-property panoramic correction;
- native multi-pass adversarial gate;
- clean final HEAD requirement;
- separate merge authorization;
- no generic assurance waiver;
- unknown evidence is not clean evidence.

Remain implementation/tooling choices unless accepted elsewhere:

- exact CI provider;
- exact static-analysis scanner;
- exact dependency scanner;
- exact secret-scanning product;
- exact governance-lint implementation language;
- exact evidence storage/reporting format;
- exact branch/ruleset mechanism;
- exact external AI/reviewer products;
- exact scheduling/frequency of non-gating continuous scans.
