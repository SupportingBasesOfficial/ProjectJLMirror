# JLMirror Vertical Slice Delivery Model

Status: proposed normative execution governance

## Why this exists
The repository already contains substantial architecture, governance, runtime substrate and Monitoring implementation. The next risk is not lack of design; it is implementation fragmentation. This model turns product construction into a sequence of small executable capabilities that can be implemented reliably by AI agents and validated by humans/CI.

## Slice anatomy
Each vertical slice SHALL be represented by a machine-readable execution record plus implementation/test artifacts.

Required fields:
- `slice_id`
- `capability`
- `actor`
- `user_outcome`
- `authority_sources`
- `depends_on`
- `database_scope`
- `domain_scope`
- `api_scope`
- `frontend_scope`
- `runtime_scope`
- `security_properties`
- `failure_properties`
- `observability_properties`
- `tests_required`
- `acceptance_commands`
- `blocked_scope`
- `done_evidence`

## Slice stages
Every slice moves through exactly these execution stages:

### S0 — Authority ready
Accepted decisions/contracts exist. No coding if material product or authority semantics remain undefined.

### S1 — Contract skeleton
Create/update schema contracts, DTOs, API route contract, frontend state model, test fixtures and expected failure cases before broad implementation.

### S2 — Persistence
Implement migration, constraints, indexes, ownership/RLS/least privilege, fixtures and database conformance tests.

### S3 — Domain/application
Implement domain types, state transitions, commands/queries and application orchestration with concurrency/idempotency/current-authority handling.

### S4 — API/BFF
Expose only accepted routes/actions. Validate input bounds, tenant placement and current authorization before effects.

### S5 — Frontend
Connect to the real API/BFF. Implement all relevant UI states and prevent client state from becoming authority.

### S6 — Integration
Run real database + backend + BFF + frontend dependencies. Prove expected writes/reads and exact failure semantics.

### S7 — Browser/user E2E
Automate the critical user journey from authenticated entry through visible result. Do not replace this with isolated component tests.

### S8 — Adversarial/recovery
Falsify cross-tenant access, stale sessions/authority, duplicate delivery, concurrent execution, invalid provider data, partial failure and recovery.

### S9 — Runtime/deployment
Prove clean build/start/migration/container execution in the selected non-production environment profile. Capture version/provenance.

### S10 — HARDEN and merge gate
Run exact-head CI, review findings, panoramic propagation and regression tests. Only then may the slice become READY_FOR_MERGE.

## Required PR structure
Every implementation PR should answer these questions in its body:
1. What exact capability becomes usable after merge?
2. Who is the actor?
3. What was impossible before?
4. Which accepted authority permits it?
5. What database state is added/changed?
6. What backend behavior is added/changed?
7. What API/BFF surface is added/changed?
8. What frontend/user path is added/changed?
9. What can fail and what happens?
10. How is tenant/security authority enforced?
11. Which commands reproduce the proof locally?
12. Which exact CI evidence proves the HEAD?
13. What remains explicitly blocked?

## Slice size heuristic
A slice is correctly sized when one engineer/AI reviewer can explain its entire causal path without switching conceptual domains repeatedly.

Prefer:
- one state transition;
- one query/read experience;
- one configuration flow;
- one operational action;
- one provider ingestion projection;
per slice.

Avoid a single PR that simultaneously invents a policy engine, notification system, ITSM integration and dashboard.

## Golden path before breadth
For a new domain/module, establish one real golden path first. Example for Alerting:

`accepted Monitoring transition -> integration event -> Alerting receipt -> current-state reread -> policy evaluation -> Alert create -> API/BFF read -> alert list/detail UI -> browser E2E`

Only after this path is fully executable should breadth be added: more policies, filters, ACK, suppression, notifications, escalation, ITSM, automation, AIOps.

## Shared foundations
Foundations should be extracted only when at least one real vertical slice needs them or when accepted architecture explicitly requires them before effectful work. Avoid speculative framework-building that has no current consumer.

## AI task packet
Before Codex/another agent writes code, the orchestrator should produce a task packet:

```text
SLICE: <id>
GOAL: <observable outcome>
BASE SHA: <exact sha>
AUTHORITY: <files/ids>
DEPENDENCIES: <accepted slice ids>
ALLOWED PATHS: <exact/prefix paths>
FORBIDDEN: <explicit exclusions>
DB: <schema/migration/constraints>
DOMAIN: <invariants/transitions>
API/BFF: <routes/contracts/auth order>
FRONTEND: <journey/states>
FAILURE: <expected errors/retry/recovery>
SECURITY: <tenant/permission/fencing>
TESTS: <unit/integration/e2e/adversarial>
RUN: <local/container commands>
DONE: <machine-verifiable evidence>
STOP IF: <conditions requiring governance>
```

The packet is not permission to reinterpret authority; it is a bounded execution projection of repository truth.
