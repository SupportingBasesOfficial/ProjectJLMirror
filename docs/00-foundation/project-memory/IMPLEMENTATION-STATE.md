# JLMirror Implementation State

Status: canonical project-memory source
Last reconstructed: 2026-09-23
Canonical main SHA at this snapshot: `518cacdb8f37a1a2d56e01c4da793b0e3c38ef19`
Latest accepted PR at this snapshot: `#176`

## Important status vocabulary
- **DEFINED**: concept described, not implementation authority.
- **AUTHORIZED**: accepted contract/semantics permit a bounded future implementation.
- **IMPLEMENTED**: runtime/code/SQL/tests exist and passed accepted gates.
- **PROPOSED**: decision record written; under review before AUTHORIZED status.
- **FOUNDATION**: partial substrate exists; feature is not complete E2E.
- **BLOCKED**: intentionally prohibited until prerequisite authorization/implementation exists.
- **PRODUCTION-READY**: requires separate production/C3 evidence; IMPLEMENTED does not imply this.

## Gate completion matrix (G1–G14)

| Gate | Capability | Status | Auth PR | Impl PR |
|---|---|---|---|---|
| G1 | Identity + Tenant + Protected Shell (BFF) | IMPLEMENTED | #153 | #157 |
| G2 | Monitoring Source Onboarding | IMPLEMENTED | — | #155 |
| G3 | Resource Inventory | IMPLEMENTED | — | #159 |
| G4 | Metrics (Definitions + Current State) | IMPLEMENTED | — | #161 |
| G5 | Problem State + Health Projection | IMPLEMENTED | — | #163 |
| G6 | Monitoring → Alerting Transport | IMPLEMENTED | #146/#148 | #165 |
| G7 | Alert Policy Lifecycle | IMPLEMENTED | #147 | #167 |
| G8 | Human Operations (ACK / Responsibility) | IMPLEMENTED | — | #169 |
| G9 | Notification Delivery | IMPLEMENTED | — | #171 |
| G10 | ITSM Incident Golden Path | IMPLEMENTED | #172 | #173/#176 |
| G11 | Automation (Runbooks / Executions) | FUTURE | — | — |
| G12 | AIOps (Correlation / Anomaly / Root Cause) | FUTURE | — | — |
| G13 | Commercial / FinOps | FUTURE | — | — |
| G14 | Production Release Gate | BLOCKED | — | — |

## Current capability matrix

| Capability | Status | Notes |
|---|---|---|
| Tenant isolation / governance foundation | IMPLEMENTED | cross-cutting law; enforced across G1–G10 |
| Human identity / BFF session (G1) | IMPLEMENTED | OIDC PKCE + BFF confidential session; Keycloak (IR-D-001) |
| Workload identity — DB role-per-worker | PROPOSED | IR-D-002 written; implementation not yet gated |
| BFF session fence store | PROPOSED | IR-D-003 written; PostgreSQL + 30 s TTL in-process cache |
| Monitoring Source / source-generation authority | IMPLEMENTED | current/historical generation distinction enforced |
| Canonical monitored resource / host inventory | IMPLEMENTED | provider host ID is not platform resource identity |
| Metric Definitions | IMPLEMENTED | provider item metadata translated under accepted authority |
| Metric Current State | IMPLEMENTED | durable current projection, idempotent semantics |
| Metric History | FOUNDATION | historical substrate exists; complete history product remains future work |
| Problem State | IMPLEMENTED | canonical `active | resolved`, explicit recovery/completeness rules |
| Health Projection | IMPLEMENTED | `unknown | healthy | degraded | unhealthy`, completeness required for healthy |
| Monitoring → Alerting publication | IMPLEMENTED | PR #165; outbox reuse; no Alert state creation at this layer |
| Alert Core Model | IMPLEMENTED | PR #147; identity/lifecycle/source/policy evidence laws |
| Alert Policy / Evaluation | IMPLEMENTED | PR #167; event-driven from ProblemState/HealthProjection transitions |
| ApplicationErrorEvent inbound push | PROPOSED | IR-D-066 written; awaiting authorization + implementation gate |
| IncidentResponsePolicy per-tenant auto-response | PROPOSED | IR-D-066 written; awaiting authorization + implementation gate |
| Automatic Alert create / resolve | IMPLEMENTED | G6+G7; authorized event-driven path only |
| Human responsibility / ACK | IMPLEMENTED | PR #169; actor-attributed, not boolean |
| Notification Intent / Delivery | IMPLEMENTED | PR #171; SmtpAdapter + WebhookAdapter authorized |
| SMS / WhatsApp notification adapters | AUTHORIZED | IR-D-067; implementation deferred to G11 cycle |
| Authoritative view / read evidence | DEFINED future requirement | AuthoritativeViewRecord design not yet authorized |
| Response / waiting state | DEFINED future requirement | notified-awaiting-response, awaiting-customer-position |
| Budget / quote approval | DEFINED future requirement | first-class approval workflow; independent from delivery |
| ITSM Incident | IMPLEMENTED | PR #173/#176; incident/ticket/SLA golden path |
| ITSM advanced state machine | FUTURE | detailed states and cross-domain contracts remain future work |
| Escalation | FUTURE | durable clocks/policies/recovery required |
| Automation (runbooks / executions) | FUTURE (G11) | explicit execution authority required |
| Infrastructure advanced taxonomy/topology | FUTURE / partial | richer device classification / relationship graph remains |
| AIOps | FUTURE (G12) | findings must not silently gain Alert authority |
| FinOps | FUTURE (G13) | costs/budgets/forecasts/optimization |
| Commercial | FUTURE (G13) | plans/contracts/invoices/billing |
| Frontend stack | PROPOSED | 65-frontend-stack-decision-record.md: React 18 + Vite + TypeScript + shadcn/ui + Tailwind + Recharts + TanStack Query |
| Frontend / NOC screens | AUTHORIZED scope defined | 65-frontend-stack-decision-record.md lists 6 initial authorized screens; not yet IMPLEMENTED |
| Production / C3 | BLOCKED | deploy/HA/performance/DR/security operations require separate evidence |
| Canonical project-memory system | IMPLEMENTED | PR #151; repository-backed continuity, validator, recovery playbook |

## Exact dependency-safe next sequence

1. Accept IR-D-002 (workload identity) and IR-D-003 (fence storage); implement per-worker DB roles and cache eviction.
2. Accept IR-D-066 (alert evaluation / ApplicationErrorEvent / IncidentResponsePolicy); implement push ingest API.
3. Accept IR-D-067 (notification channels) as production-eligible; add SMS adapter (Twilio); begin WhatsApp template governance.
4. Implement authorized frontend screens (65-frontend-stack-decision-record.md) — G11 UI track alongside backend work.
5. Authorize and implement Automation / runbook execution (G11); wire `automation_triggers` from IncidentResponsePolicy.
6. Authorize and implement AIOps findings subsystem (G12); establish explicit AIOps → Alert evidence contract.
7. Authorize FinOps / Commercial domain (G13).
8. Complete production / C3 evidence gate (G14): HA PostgreSQL, BFF multi-instance fencing (IR-D-003 Phase B), performance baseline, security operations playbook.

## Scope guard

Do not treat a PROPOSED decision record as AUTHORIZED until it is accepted by the project governance process. Do not treat IMPLEMENTED as PRODUCTION-READY. AIOps findings (G12) must not silently gain authority over Alert lifecycle until the AIOps authority contract is explicitly authorized. ApplicationErrorEvent must not be implemented before IR-D-066 is accepted.

## Update contract

After every accepted merge that changes maturity or next-step dependency order, this file must be updated in the same accepted change or an immediately required governance follow-up. The canonical `main` SHA must match the accepted repository state represented by this snapshot.
