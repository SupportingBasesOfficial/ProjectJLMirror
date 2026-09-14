# JLMirror Day-1 Implementation Bootstrap

Status: proposed normative execution bootstrap

## Purpose
This is the starting procedure for the first day of product-integrated coding and for every new AI implementation session thereafter.

## Rule zero
Do not begin by asking the AI to "build JLMirror" or "implement the backend". Begin by selecting one accepted vertical slice and projecting repository truth into a bounded task packet.

## Step 1 — Recover current truth
Before coding:
1. verify exact `main` SHA;
2. read canonical project-memory corpus when accepted;
3. read the execution constitution and current roadmap;
4. identify accepted domain authority for the target slice;
5. inspect existing implementation that must be reused;
6. inspect open PRs that may conflict;
7. identify exact blocked/open decisions.

Output: a one-page implementation context with no invented assumptions.

## Step 2 — Select one vertical slice
Choose the smallest dependency-safe capability that produces observable progress.

Selection criteria:
- all material product semantics are authorized;
- dependencies already exist or are part of the same bounded slice;
- database/API/frontend/test effects can be described explicitly;
- completion can be proven automatically.

If these cannot be stated, coding is premature.

## Step 3 — Generate the AI task packet
The orchestrating agent writes the complete task packet defined in `VERTICAL-SLICE-DELIVERY-MODEL.md`.

The packet is committed or attached to the PR when the slice is material enough that later reconstruction matters.

## Step 4 — Contract before implementation
Before large implementation changes, establish the slice's contract surfaces:
- table/state identity and invariants;
- command/query shapes;
- API/BFF request/response/error contract;
- frontend state model;
- event contract if asynchronous;
- exact test scenarios.

Contracts must use accepted vocabulary and canonical IDs.

## Step 5 — Implement persistence and domain together
For a stateful slice:
- write migration/constraints/indexes;
- add database conformance tests;
- write domain types/state transitions;
- add unit/property tests;
- wire application orchestration;
- test concurrency/idempotency/authority before UI polish.

Do not build a large data model for future hypothetical features.

## Step 6 — Expose real API/BFF
- use the real database/domain behavior;
- current authorization precedes protected effects;
- API version/error/bounds follow accepted contracts;
- no direct browser trust of provider IDs or tenant IDs supplied by the client;
- include integration tests against real persistence.

## Step 7 — Connect the real frontend
Frontend must consume the real BFF/API contract in the same slice.

Minimum state coverage where relevant:
- loading;
- empty;
- success;
- stale/incomplete;
- recoverable error;
- unavailable;
- forbidden;
- validation error.

The UI may explain authority/evidence state but may not synthesize business truth.

## Step 8 — Run the slice locally E2E
From a clean enough environment:
1. start dependencies;
2. migrate database;
3. seed/establish test tenant and identity;
4. start backend/BFF/frontend/workers;
5. inject or obtain provider/test evidence;
6. execute the user journey;
7. verify UI/API/database/async evidence;
8. exercise one failure/recovery scenario.

If a human must manually patch the database or change source code during this sequence, the bootstrap is not reproducible yet.

## Step 9 — Container proof
Every component introduced for the product runtime must have a reproducible container/runtime path before the slice can claim deployability. Development-only direct process execution may coexist, but cannot be the only proof.

## Step 10 — CI and HARDEN
Required cycle:
`implement -> test -> exact-head CI -> adversarial review -> fix root property -> add regression guardrail -> rerun exact-head CI -> panoramic review -> merge gate`

A later commit invalidates earlier exact-head clean evidence.

## Step 11 — Update project truth
When the slice changes product maturity or next-step dependency:
- update implementation state;
- update roadmap/slice ledger;
- update decision register if a new material decision was accepted;
- update project memory after that system is canonical;
- preserve blocked scope explicitly.

## Step 12 — Stop at merge gate
Do not auto-merge. Report:
- exact HEAD;
- capability now executable;
- test matrix;
- CI state;
- review state;
- unresolved risks;
- exact next dependency-safe slice.

Merge requires separate explicit owner authorization.

## First integrated product target
The recommended first full-stack target is **G1 Identity + tenant + protected application shell**, unless current accepted authority or repository state proves a prerequisite must be completed first.

This target is valuable because every later UI/API capability needs a trustworthy actor/tenant/session boundary. It should not rebuild accepted Wave 1 substrate; it should expose/reuse it through the product stack.

## Second target
After G1, execute **G2 Monitoring Source onboarding** so the product can connect/configure a real monitoring source and visibly show validation state. This creates the first compelling customer-facing bridge between platform access and the already-implemented Monitoring foundations.
