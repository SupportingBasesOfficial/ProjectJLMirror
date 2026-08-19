# Data and Capability Ownership Matrix

**Status:** accepted

| Context | Owns mutable/state authority | May consume | Must not directly mutate |
|---|---|---|---|
| Platform Management | tenants, lifecycle, placement metadata contract, global catalog/config | Identity refs, Commercial customer linkage | tenant domain state |
| Identity | principals, auth bindings, MFA, sessions/recovery | external identity-provider assertions | memberships, domain resources |
| Organization & Access | memberships, roles, permissions, tenant settings/branding/flags | principal IDs, tenant IDs | auth credentials, domain resources |
| Monitoring | sources, devices/resources, external refs, metric definitions, current state, normalized problems, sync state, canonical customer monitoring telemetry/history semantics and accepted historical observations/samples | provider input | ITSM, alerts, AIOps findings |
| Alerting | alerts, notification policy/state, escalation/subscriptions | Monitoring/Infrastructure facts | Monitoring resources/history, ITSM tickets |
| ITSM | incidents/tickets, changes, SLA, maintenance, knowledge | alert/resource references | Monitoring/Infrastructure owned state |
| Automation | definitions, schedules/tasks, workflows, executions | authorized targets/triggers | source resource state, identity secrets |
| Infrastructure | assets/topology, discovery, posture/capacity/drift/patch state | Monitoring/provider evidence | Monitoring current/history state |
| AIOps | analysis config and derived findings | operational evidence | source monitoring/infrastructure evidence |
| FinOps | costs, budgets, forecasts, optimizations | resource/service identity, accepted pricing inputs | Commercial invoice/payment state |
| Commercial | contracts/plans, billing cycles, invoices/payments, reconciliation | tenant/customer linkage, payment-provider results | infrastructure cost evidence |
| Reporting & Experience | report definitions/delivery/artifacts, read/public projections | owner queries/events | source domain entities |
| Integrations & Extensibility | API credential metadata, webhooks/deliveries, integration/installation state | integration events, provider APIs | arbitrary domain tables |
| Data Administration | export/import/query operation state and artifacts | authorized domain data through governed paths | source domain ownership |
| Compliance & Governance | controls/evidence/governance workflow state, immutable append-only accountability ledger/audit-evidence authority | required audit and domain evidence | direct remediation of owned source state |

## Ownership rules

1. Every mutable aggregate or durable authoritative record class has one logical owner.
2. Read access does not imply write ownership.
3. Cross-context references use stable logical IDs/contracts and are not assumed to have physical foreign keys.
4. Physical co-location in one database does not weaken logical ownership.
5. Physical separation of historical telemetry behind a telemetry port does not transfer its domain semantics away from Monitoring.
6. Domain owners produce required audit evidence, but Compliance & Governance owns the immutable accountability ledger/evidence authority and its retention/query semantics; this does not grant it direct mutation authority over source business state.
7. If a context is extracted into a service, the ownership model should remain valid without redefining business semantics.