# JLMirror Recovery Playbook for a New Chat or Agent

Status: canonical bootstrap procedure

Use this when a contributor/agent starts with zero reliable memory of JLMirror.

## Bootstrap sequence
1. Read `PROJECT-IDENTITY.md` to understand what JLMirror is and what it is not.
2. Read `IMPLEMENTATION-STATE.md` to determine canonical main, accepted/open work, implemented vs authorized vs blocked capabilities.
3. Read `CANONICAL-INVARIANTS.md` before proposing architecture or code.
4. Read `DOMAIN-AUTHORITY-MAP.md` to identify the owner of every relevant state/decision.
5. Read `E2E-SYSTEM-MAP.md` for the causal end-to-end chain.
6. Read `ROADMAP-DEPENDENCY-GRAPH.md` to determine the next dependency-safe action.
7. Read `DECISION-REGISTER.md` so old decisions are not rediscovered or contradicted.
8. Read `ACCEPTED-PR-CHAIN.md` and inspect the current GitHub `main`/open PRs.
9. Read `OPEN-QUESTIONS-AND-DEFERRED.md` so unresolved topics are not treated as accepted design.
10. If human operations are involved, read `HUMAN-OPERATIONS-MODEL.md` and Issue #149.
11. Reconcile repository truth against any assistant/chat memory. If they differ, repository-backed accepted truth wins.
12. Continue only from exact repository state and respect merge/authorization gates.

## Repository reconciliation checklist
- verify current `main` SHA;
- verify latest accepted PR and squash commit;
- identify all open PRs and their exact heads;
- identify unresolved review threads/findings;
- identify authorization IDs and manifests relevant to the task;
- distinguish docs/authorization from runtime implementation;
- distinguish implementation from production readiness;
- verify dependency order before opening downstream work.

## Execution semantics for this project
- user phrase `pode seguir` authorizes continued execution but not merge;
- merge requires explicit authorization such as `pode fazer squash merge`;
- prefer squash merge;
- preserve branches unless explicitly authorized otherwise;
- use exact-head protections when available;
- after material review findings, perform panoramic HARDEN and convert reusable lessons into durable guards when appropriate.

## Failure rule
If project-memory sources and repository implementation disagree materially, do not guess. Inspect the accepted source/commit/PR and repair the project-memory corpus through a governed change.

## Completion criterion
A new contributor should be able to answer from repository sources alone:
- what JLMirror is;
- why its major separations exist;
- what is implemented;
- what is only authorized;
- what is blocked;
- what invariants cannot be violated;
- where current work is occurring;
- what the next correct action is;
- what the intended product behavior is E2E.

If answering those questions requires recovering an old chat, the project-memory system is incomplete.
