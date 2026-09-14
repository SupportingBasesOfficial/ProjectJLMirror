# JLMirror AI E2E Delivery Constitution

Status: proposed normative execution governance

## Purpose
JLMirror will be implemented primarily by generative AI agents. This document defines how implementation work must be decomposed, executed, proven and promoted so speed does not trade away correctness, security, operability or product completeness.

The goal is not maximum code throughput. The goal is maximum **accepted end-to-end capability throughput**.

## Prime directive
No feature is complete because one layer is complete.

A feature/slice is complete only when the accepted user/operator behavior is proven through every applicable layer:

`schema/migration -> persistence authority -> domain logic -> application/service -> API/BFF -> frontend -> user flow -> tests -> security/tenant isolation -> observability -> container/runtime -> deployment evidence`

If a layer is not applicable, the implementation record must explicitly say why.

## AI implementation contract
Every coding task given to an AI agent SHALL contain:
1. exact accepted authority/invariants;
2. exact vertical-slice identifier;
3. allowed files/surfaces;
4. forbidden scope;
5. input/output contracts;
6. database effects and migration rule;
7. API/BFF contract where applicable;
8. frontend states where applicable;
9. tests that must exist before completion;
10. security/tenant/authorization checks;
11. failure/retry/recovery behavior;
12. observability requirements;
13. local execution command;
14. container execution command;
15. acceptance evidence;
16. stop conditions requiring a new governance decision.

An AI agent may not silently invent product authority, lifecycle semantics, permissions, data ownership, topology, provider identity rules or deferred architectural choices.

## Vertical-slice rule
Implementation SHALL proceed in small vertical slices, not horizontal layer batches.

Bad sequence:
- build all tables;
- then all backend;
- then all APIs;
- then all frontend;
- then test later.

Required sequence:
- choose one observable product capability;
- implement only the minimum database/domain/API/UI needed for that capability;
- prove it E2E;
- harden it;
- integrate it;
- then advance to the next dependency-safe slice.

This maximizes feedback speed while preserving architecture.

## Definition of Done: E2E-16
A slice cannot be marked DONE until every applicable item passes.

1. **Authority** — implementation matches accepted canonical decision/contract.
2. **Data model** — schema, constraints, indexes and ownership are explicit.
3. **Migration** — forward migration is deterministic and tested; rollback/recovery posture is explicit.
4. **Tenant isolation** — tenant/source/generation boundaries are enforced at the authoritative layer.
5. **Domain** — business semantics are implemented independently of transport/UI/vendor details.
6. **Application** — orchestration preserves idempotency, concurrency and current authority.
7. **API/BFF** — contracts are versioned/bounded and authorization order is correct.
8. **Frontend** — loading/empty/success/error/stale/forbidden states are intentional where applicable.
9. **Unit tests** — domain invariants and boundary behavior are covered.
10. **Integration tests** — real database and cross-component behavior are exercised.
11. **E2E tests** — a representative actor traverses the real admitted path.
12. **Adversarial tests** — cross-tenant, stale authority, duplicate/retry, malformed and privilege-abuse paths are falsified.
13. **Observability** — logs/metrics/traces/health expose failure without becoming business authority.
14. **Runtime** — service starts from a clean checkout using documented commands and containers where applicable.
15. **Deployment** — target environment admission/runbook is reproducible; no workstation-only success.
16. **Evidence** — CI binds PASS to the exact reviewed HEAD and no material finding remains unresolved.

## Fast-but-safe rule
Speed SHALL come from:
- stable templates;
- pre-approved architecture;
- generated scaffolding;
- deterministic validators;
- reusable test harnesses;
- containerized dependencies;
- small pull requests;
- dependency-safe parallelism;
- machine-readable execution manifests;
- AI prompts derived from repository truth.

Speed SHALL NOT come from:
- skipping tests;
- delaying integration;
- bypassing tenant/security boundaries;
- committing placeholder production behavior;
- broad AI-generated refactors without bounded scope;
- merging red CI;
- accepting manual-only validation;
- building frontend against fake semantics that differ from the backend contract.

## Database-first, not database-only
For every stateful slice:
1. define business identity and authority;
2. define schema and constraints;
3. prove least-privilege access and tenant isolation;
4. implement domain/service behavior;
5. expose the accepted contract;
6. consume that contract in frontend/operator surfaces;
7. execute E2E against the real database.

The database is durable truth, but a table alone is not a delivered capability.

## Frontend is part of the slice
A user-facing capability is not done until the frontend uses the real accepted API/BFF contract and handles its canonical states. Temporary mocks may support local UI development, but mocks cannot satisfy DONE and must be contract-generated or contract-checked.

## Test pyramid for AI-generated code
Every slice should prefer many fast tests and a smaller set of high-value real integration/E2E tests:
- static/schema/contract validators;
- unit/domain tests;
- database conformance tests;
- service/API integration tests;
- browser E2E for critical user journeys;
- adversarial/security/recovery probes.

Generated tests must prove properties, not merely reproduce implementation branches.

## PR sizing
Default target: one independently understandable vertical capability per PR.

A PR must be split when:
- it changes multiple unrelated domain authorities;
- review cannot reason about failure/rollback as one unit;
- frontend/backend/database changes cannot be tied to one user-visible capability;
- the diff requires unrelated accepted decisions.

Large mechanical generated code is allowed only when its generator/schema/proof is itself reviewable and bounded.

## Dependency-safe parallelism
AI agents may work in parallel only on slices whose write surfaces and authorities do not conflict.

Parallel work must declare:
- dependency inputs;
- files/directories owned for the task;
- generated contracts consumed;
- merge order when one slice depends on another.

Two agents must not independently redefine the same contract/state machine/schema authority.

## Product-running milestone
A milestone counts as "running" only when a clean environment can:
1. start required infrastructure;
2. migrate the database;
3. start backend/BFF/frontend workers/services;
4. seed or connect authorized test data/provider evidence;
5. execute the milestone's critical user journey;
6. observe expected state in UI/API/database;
7. exercise at least one controlled failure/recovery path;
8. pass exact-head CI.

## Merge rule
READY_FOR_MERGE is not merge authorization. Merge remains separately authorized by the project owner and should be squash-based unless a specific accepted exception requires otherwise.
