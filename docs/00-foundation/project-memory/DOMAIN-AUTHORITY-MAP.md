# JLMirror Domain Authority Map

Status: canonical project-memory source

| Domain | Owns | Explicitly does not own | Current maturity |
|---|---|---|---|
| Platform Management | tenant/platform lifecycle, placement and platform-level governance | domain business state | partially defined / future runtime expansion |
| Identity | identity/session/authentication authorities | tenant business authorization by JWT validity alone | architecture/governance advanced |
| Org & Access | organizations, memberships, roles, permissions, tenant-scoped access | provider identity; Monitoring truth | modeled; runtime expansion remains |
| Monitoring | monitoring sources/generations, canonical resources, metrics, Problem State, Health Projection, monitoring sync/history | Alert lifecycle, notification policy, ITSM incident, AIOps finding | substantially implemented |
| Alerting | Alert lifecycle, future alert policy/evaluation, notification intent/delivery, escalation/subscriptions within accepted slices | raw monitoring history, Monitoring Problem/Health truth, ITSM incident | core model authorized; runtime incomplete |
| ITSM | incidents/tickets/tasks/assignment/SLA/change-style workflows | Alert lifecycle and Monitoring truth | future |
| Automation | runbooks, actions, executions, schedules and automation audit | redefining Monitoring/Alert truth | future |
| Infrastructure | richer asset/topology/configuration/capacity/certificates/backups/patching-style models | provider-native IDs as canonical identity | future/partial foundations |
| AIOps | findings, correlation/anomaly/root-cause intelligence | Monitoring Problem, Alert, Incident identity | future |
| FinOps | costs, budgets, forecasts, optimization | Commercial contracts/invoices as same truth | future |
| Commercial | plans/contracts/customers/invoices/billing semantics | Monitoring/Alert operational state | future |
| Security | trust, least privilege, workload identity, secret/crypto/security controls | product domain ownership | cross-cutting, advanced governance/evidence |
| Observability/SRE | telemetry, reliability evidence, service objectives/operational observability | domain business truth | cross-cutting, advanced foundations |
| Compliance & Governance | acceptance gates, decision authority, review assurance, provenance | runtime domain state | advanced and actively enforced |

## Monitoring authority
Monitoring is the current most mature business domain. It owns canonical observation-derived truth, including:
- source/generation authority;
- provider-neutral monitoring resources;
- host inventory evidence;
- metric definitions;
- metric current state;
- metric history foundation;
- Problem State;
- Health Projection.

Monitoring may publish bounded invalidation/resync events, but those events do not grant Alerting permission to invent or mutate Monitoring truth.

## Alerting authority
Accepted Alert core v1:
- opaque tenant-scoped `alert_id`;
- lifecycle `active | resolved`;
- resolved `alert_id` does not reopen in v1;
- effectful transitions require exact immutable policy identity/version once policy evaluation is authorized;
- source evidence family is explicit: `monitoring_problem | monitoring_health_projection`;
- no policy-less create/resolve path.

Still separate/unaccepted as runtime authority:
- policy evaluation engine;
- automatic Alert creation/resolution;
- ACK/suppression;
- human responsibility/assignment;
- notification/delivery/view evidence;
- approvals;
- escalation;
- realtime/public webhook behavior.

## Human-operations authority model
Future slices must keep these dimensions independent:
1. resource responsibility;
2. current action ownership;
3. acknowledgement;
4. notification recipient/destination;
5. delivery state;
6. view/read evidence;
7. response/waiting state;
8. approval workflow;
9. escalation;
10. ITSM assignment/lifecycle.

No single giant `status` may become the authority for all human operations.
