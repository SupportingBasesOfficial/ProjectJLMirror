# ADR-001 — Architectural Style: Modular Monolith with Independent Workers

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly but intentionally evolvable

## Context

JLMIRROR contains many bounded contexts but does not yet have evidence that each needs independent deployment. Premature service distribution would introduce network failure, distributed transactions, duplicated platform concerns and operational overhead before scale/team boundaries justify them. A conventional layered monolith without enforced modules would violate ownership boundaries as scope grows.

Relevant drivers: `INV-DATA-001`, `INV-DATA-002`, `AP-02`, `AP-15`, `QA-AVAIL-001`.

## Options considered

### A — Conventional monolith
Simple deployment but weak boundaries and high risk of table/service coupling.

### B — Microservices per bounded context
Strong deployment independence but large immediate complexity: service discovery, network authorization, distributed tracing, contract drift, event infrastructure and cross-service consistency.

### C — Modular monolith plus independent worker runtimes
One primary synchronous business deployment with compile-time/module boundaries, explicit application ports and separately deployable asynchronous workers.

## Decision

Select **Option C**.

The primary business API SHALL begin as a modular monolith. Each bounded context SHALL have explicit ownership, public application contracts and forbidden direct mutation of another context's storage. Worker classes SHALL execute outside the request runtime when their workload, failure behavior or security profile requires isolation.

Modules SHALL be written so that extracting a context later does not require redefining business semantics or public contracts.

## Consequences

### Positive
- simpler transactions for workflows that are still co-located;
- low operational overhead at initial scale;
- easier end-to-end testing and local development;
- domain boundaries exist before network boundaries;
- workers can scale independently from HTTP traffic.

### Negative / cost
- boundaries require lint/build/test enforcement rather than network separation;
- a single API deployment can still have a broader failure/release blast radius than mature extracted services;
- careless shared utilities can create a distributed-monolith problem later.

### Risks
Boundary erosion is the primary risk. Cross-context imports and database access require architectural tests/review.

## Validation

- module dependency graph contains no forbidden direction;
- no cross-domain direct mutation in persistence layer;
- critical worker workloads can deploy/scale independently;
- load testing establishes when API or a context becomes an extraction candidate.

## Exit / revisit conditions

Revisit when a context requires independent scale, failure/security isolation, incompatible runtime, release cadence, or stable team ownership that exceeds modular-monolith benefits.

## Migration / rollout

Initial code structure SHALL make module interfaces explicit. Extraction uses a strangler seam through those contracts/events rather than a rewrite.