# Domain Map

**Status:** accepted

JLMIRROR separates business domains, platform capabilities, and cross-cutting system capabilities. A bounded context is not automatically a microservice.

## Business / control domains

### Platform Management
Owns tenant lifecycle, placement intent, global catalog/configuration and controlled platform administration. Physical placement mechanism is an architecture concern; tenant lifecycle semantics belong here.

### Identity
Owns principal identity, authentication bindings, MFA, sessions/credential lifecycle, external identity links and principal profile.

### Organization & Access
Owns tenant memberships, tenant users as membership views, roles, permissions, custom roles, tenant configuration/branding/feature enablement, and tenant authorization policy.

### Monitoring
Owns Monitoring Sources, platform resource/device identity, metric definitions, current operational state, problems/observations normalized for platform use, health, synchronization semantics, and canonical customer monitoring telemetry/history semantics including accepted metric samples and observation history. Historical telemetry may be physically specialized behind the telemetry port without transferring logical ownership.

### Alerting
Owns alerts, notification policy, delivery intent/history, escalation and real-time operational notification semantics.

### ITSM
Owns incidents/tickets, comments, change/RFC, approvals/tasks, services, SLA, maintenance and knowledge-management semantics.

### Automation
Owns scripts, parameters, automation definitions, schedules/tasks, workflows, execution records and execution policy hooks.

### Infrastructure
Owns asset/infrastructure inventory and relationships, discovery/topology, certificate/firewall/backup/Kubernetes/capacity/drift/patch governance state.

### AIOps
Owns derived anomalies, predictions, correlations and operational findings; source monitoring state remains owned by Monitoring/Infrastructure.

### FinOps
Owns infrastructure/service cost entries, budgets, cost analysis/forecast and optimization opportunities.

### Commercial
Owns customer commercial relationship, contracts/plans, billing cycles, invoices/payment state and payment-provider reconciliation.

## Platform capabilities with owned state

### Reporting & Experience
Owns report definitions/schedules/deliveries/artifacts, executive read models, public status projections, TV/NOC presentation projections and client-facing presentation state. It does not own source operational entities.

### Integrations & Extensibility
Owns API credential metadata, webhooks/deliveries, integration instances/configuration references, marketplace installations and integration synchronization state. Global marketplace catalog belongs to Platform Management.

### Data Administration
Owns governed export/import/direct-query operation records and policies. It is a privileged capability, not a general-purpose domain for arbitrary data ownership.

## Cross-cutting capabilities

### Security
Authentication enforcement, authorization enforcement, secrets protection, cryptographic policy, abuse prevention, secure runtime/network posture and security telemetry apply across boundaries. Domain ownership remains with the corresponding domains.

### Observability
Logs, metrics, traces, errors, health and operational correlation are emitted by all runtimes. Platform observability storage is operational infrastructure, not a source of business ownership and does not own customer Monitoring telemetry history.

### Compliance & Governance
Owns compliance controls/evidence, retention/legal policy, data-rights workflows, and the immutable append-only accountability ledger/audit-evidence authority. It consumes required evidence from domain owners while respecting their source-state ownership and routes remediation through owning-domain commands.

## Decomposition principle

A context is extracted into an independently deployed service only when independent scale, failure isolation, runtime, release cadence, security boundary, or team ownership justifies the distribution cost.