# JLMirror Product Execution Roadmap

Status: proposed normative execution sequence

## Objective
Convert the accepted architecture and existing runtime substrate into a usable B2B product through dependency-safe vertical increments. This is an execution roadmap, not a promise of calendar duration.

## Existing base before this roadmap
The repository already contains accepted implementation substrate and Monitoring runtime code. Therefore the roadmap does not restart from zero and must reuse accepted foundations rather than rebuilding them in a parallel stack.

## Program gates

### G0 — Developer/runtime bootstrap
Outcome: any authorized AI/human can clone the repository and deterministically run the supported local stack.

Must establish/confirm:
- one documented toolchain bootstrap;
- one containerized local dependency stack;
- one database migration entrypoint;
- one backend/service start entrypoint;
- one frontend/BFF start entrypoint when those surfaces are introduced;
- fixture/test tenant bootstrap;
- provider simulator/test fixture where real Zabbix is not required;
- exact-head CI parity commands.

Exit proof: clean checkout -> bootstrap -> migrate -> start -> health/conformance PASS.

### G1 — Identity + tenant + shell golden path
Outcome: a user can authenticate into a tenant-scoped JLMirror shell and current authorization is enforced.

Vertical slices:
- login/session admission;
- tenant selection/current placement;
- current membership/permission read;
- authenticated BFF route;
- protected app shell;
- forbidden/cross-tenant browser E2E.

Exit proof: authenticated user sees only admitted tenant context; revoked/forbidden context fails closed.

### G2 — Monitoring source onboarding golden path
Outcome: an authorized user can register/configure a Monitoring Source and observe validation status.

Vertical slices:
- create source configuration without exposing credentials;
- validate source;
- source generation lifecycle;
- source status/read UI;
- failure/retry/reconciliation presentation.

Exit proof: UI -> BFF/API -> DB -> worker/provider fixture -> DB -> UI completes with success and controlled-failure cases.

### G3 — Resource inventory golden path
Outcome: a tenant can see canonical monitored resources discovered from the provider.

Vertical slices:
- host/resource ingestion;
- canonical resource persistence;
- list/detail API;
- list/detail UI;
- provenance/provider evidence view without treating provider ID as platform identity.

Exit proof: Zabbix fixture -> adapter/ingestion -> canonical resource -> API -> browser UI.

### G4 — Metrics golden path
Outcome: a resource detail shows real current metrics and bounded history.

Vertical slices:
- metric definitions;
- current metric state;
- historical samples foundation/read;
- resource metric API/BFF;
- metric UI components;
- stale/unavailable/incomplete states.

Exit proof: provider fixture -> DB -> backend -> UI displays current + history with correct freshness semantics.

### G5 — Problem + Health golden path
Outcome: the UI explains both what is wrong and the resource's derived overall health.

Vertical slices:
- Problem list/detail/read exposure;
- Health list/detail/read exposure;
- resource association;
- active/resolved transition display;
- evidence-state display;
- browser E2E for problem activation/recovery and health transition.

Exit proof: authoritative provider evidence drives Problem/Health and the UI never interprets incomplete evidence as healthy/resolved.

### G6 — Monitoring -> Alerting transport golden path
Outcome: accepted Monitoring transitions reliably reach Alerting as invalidation/resync responsibility without creating Alerts yet unless policy authority is separately accepted.

Vertical slices:
- transition-bound outbox publication;
- consumer inbox/dedup;
- current-state re-read;
- reconciliation/replay;
- operational diagnostics.

Exit proof: duplicate/redelivery/restart does not duplicate responsibility/effects; historical generation cannot gain current authority.

### G7 — Alert policy + lifecycle golden path
Prerequisite: separate accepted Alert Policy/Evaluation authority.

Outcome: one real policy can convert current Monitoring truth into a platform Alert and later resolve it under accepted Alerting-owned semantics.

Vertical slices:
- policy identity/version persistence;
- one bounded problem-source condition family;
- one bounded health-source condition family;
- policy evaluation;
- Alert create;
- Alert resolve;
- list/detail API/BFF;
- list/detail UI;
- browser E2E.

Exit proof: Monitoring transition -> event -> reread -> policy -> Alert -> UI, with idempotency and terminal resolved identity semantics.

### G8 — Human operations golden path
Prerequisite: accepted authority for responsibility/ACK/visibility state dimensions.

Outcome: operators can assign responsibility, acknowledge an Alert, track current action owner and distinguish delivery/view/response states.

Vertical slices:
- responsibility model;
- ACK model;
- current-action projection;
- internal authoritative visibility path;
- customer-side authoritative visibility path/confirmation surface;
- audit trail;
- UI journey.

Exit proof: the system can truthfully answer who is responsible, who acknowledged, who must act next and whether awareness evidence exists.

### G9 — Notification/delivery golden path
Outcome: one admitted notification channel works from policy intent through delivery evidence and fallback/unknown handling.

Start with one channel only. Add more channels after the delivery state machine and observability are proven.

Exit proof: intent -> provider dispatch -> delivery state -> JLMirror evidence -> UI, without equating sent/delivered/viewed.

### G10 — ITSM golden path
Outcome: an admitted Alert can create/link an incident/ticket through a provider-neutral ITSM adapter while preserving separate identities/lifecycles.

Exit proof: Alert != Incident remains mechanically true and retries do not create duplicate tickets.

### G11 — Automation golden path
Outcome: one approved bounded automation can react to an admitted operational condition with authorization, idempotency, audit and rollback/reconciliation behavior.

### G12 — AIOps golden path
Outcome: AI analysis consumes governed evidence and emits advisory/explainable findings without becoming silent business authority.

### G13 — Commercial/FinOps/product administration
Outcome: tenant/product entitlement, plan/quota/cost/account administration become usable without bypassing domain authorization.

### G14 — Production release gate
Outcome: a reproducible non-production release is promoted through accepted supply-chain/runtime/recovery controls to a production-ready candidate.

Must include:
- production configuration authority;
- secret management;
- backup/restore proof;
- migrations under realistic data volume;
- monitoring/alerting of JLMirror itself;
- security testing;
- load/capacity tests for accepted envelope;
- rollback/forward-recovery drill;
- operational runbooks;
- release provenance;
- customer-critical E2E smoke tests.

## Market-speed rule
Do not wait for G14 to see a usable system. G1 through G7 must progressively produce a locally/staging-executable product. Internal demos and controlled pilot evidence should happen continuously, but no gate may be mislabeled as production readiness.

## Parallel lanes
Only dependency-safe work may run concurrently.

Typical safe concurrency after contracts stabilize:
- migration/domain implementation;
- frontend component implementation against generated contracts;
- test fixture/provider simulator;
- observability dashboards;
provided all lanes consume one canonical contract and merge in a declared order.

Unsafe concurrency:
- two agents independently changing the same state machine;
- frontend inventing fields before contract acceptance;
- database and API independently choosing different identity semantics;
- notification and human-responsibility layers redefining Alert lifecycle.

## Optimization target
Optimize for **lead time from accepted requirement to verified executable user outcome**, not lines of code, commit count or number of parallel agents.
