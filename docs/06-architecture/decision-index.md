# Architecture Decision Index

**Status:** accepted

The following ADRs form the accepted architecture baseline and its accepted successor decisions. They constrain one another and must not be interpreted in isolation.

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
| ADR-021 | Monitoring Source-Instance Replacement: staged candidate and atomic cutover | accepted |
| ADR-022 | Organization, provider and commercial operating model | accepted |

## Acceptance evidence

The first baseline was reviewed for consistency with the accepted `FR-*`, `INV-*`, `QA-*`, `SEC-*` and `TM-*` authorities, including the ownership corrections recorded during formal governance acceptance. Detailed initial-baseline scope, evidence and intentionally OPEN decisions are recorded in `docs/06-architecture/baseline-acceptance-2026-08-18.md`.

ADR-021 is the accepted Monitoring source-instance replacement decision ratified by the Wave 4 Monitoring Track A records. ADR-022 is the accepted successor architecture decision produced from the separately accepted organization/provider/commercial product model. ADR-022's exact acceptance provenance is recorded in `governance/product-model/organization-provider-commercial/STATE.md` and `DECISION_MANIFEST.json`.

Architecture diagrams and later design/implementation MUST derive from these accepted ADRs rather than silently inventing new cross-cutting behavior. A semantic change to an accepted decision requires the repository's ADR/RFC governance process.
