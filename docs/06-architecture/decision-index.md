# Architecture Decision Index

**Status:** accepted

The following ADRs form the accepted first architecture baseline. They are accepted together because each constrains the others; none should be interpreted in isolation.

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Modular monolith + independent workers | accepted |
| ADR-002 | Control plane + cell-based data plane | accepted |
| ADR-003 | Tenant isolation model and isolation classes | accepted |
| ADR-004 | Tenant placement, routing and relocation semantics | accepted |
| ADR-005 | Identity, membership and authorization boundaries | accepted |
| ADR-006 | Data topology and transactional storage | accepted |
| ADR-007 | Web BFF and API boundary | accepted |
| ADR-008 | Transaction boundaries and transactional outbox | accepted |
| ADR-009 | Domain/integration event semantics | accepted |
| ADR-010 | Durable background job semantics | accepted |
| ADR-011 | Realtime delivery semantics | accepted |
| ADR-012 | Cache and ephemeral-state semantics | accepted |
| ADR-013 | External provider adapter architecture | accepted |
| ADR-014 | Observability architecture | accepted |
| ADR-015 | Secrets and key-management architecture | accepted |
| ADR-016 | Deployment/runtime architecture beyond edge limits | accepted |
| ADR-017 | Availability, degradation and bulkheads | accepted |
| ADR-018 | Backup, restore and disaster-recovery model | accepted |
| ADR-019 | Scaling, cell expansion and tenant relocation | accepted |
| ADR-020 | Selective evolution to distributed services | accepted |

## Acceptance evidence

The baseline was reviewed for consistency with the accepted `FR-*`, `INV-*`, `QA-*`, `SEC-*` and `TM-*` authorities, including the ownership corrections recorded during formal governance acceptance. Detailed scope, evidence and intentionally OPEN decisions are recorded in `docs/06-architecture/baseline-acceptance-2026-08-18.md`.

Architecture diagrams and later design/implementation MUST derive from these accepted ADRs rather than silently inventing new cross-cutting behavior. A semantic change to an accepted decision requires the repository's ADR/RFC governance process.