# Architecture Decision Index

**Status:** proposed

The following ADRs form the first architecture baseline. They are proposed together because each constrains the others; none should be interpreted in isolation.

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | Modular monolith + independent workers | proposed |
| ADR-002 | Control plane + cell-based data plane | proposed |
| ADR-003 | Tenant isolation model and isolation classes | proposed |
| ADR-004 | Tenant placement, routing and relocation semantics | proposed |
| ADR-005 | Identity, membership and authorization boundaries | proposed |
| ADR-006 | Data topology and transactional storage | proposed |
| ADR-007 | Web BFF and API boundary | proposed |
| ADR-008 | Transaction boundaries and transactional outbox | proposed |
| ADR-009 | Domain/integration event semantics | proposed |
| ADR-010 | Durable background job semantics | proposed |
| ADR-011 | Realtime delivery semantics | proposed |
| ADR-012 | Cache and ephemeral-state semantics | proposed |
| ADR-013 | External provider adapter architecture | proposed |
| ADR-014 | Observability architecture | proposed |
| ADR-015 | Secrets and key-management architecture | proposed |
| ADR-016 | Deployment/runtime architecture beyond edge limits | proposed |
| ADR-017 | Availability, degradation and bulkheads | proposed |
| ADR-018 | Backup, restore and disaster-recovery model | proposed |
| ADR-019 | Scaling, cell expansion and tenant relocation | proposed |
| ADR-020 | Selective evolution to distributed services | proposed |

## Acceptance rule

Before this baseline is accepted, review SHALL verify consistency with `FR-*`, `INV-*`, `QA-*`, `SEC-*` and `TM-*`. Architecture diagrams and later implementation MUST derive from accepted ADRs rather than silently inventing new cross-cutting behavior.
