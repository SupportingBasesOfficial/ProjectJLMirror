# JLMirror E2E System Map

Status: canonical project-memory source

## Complete causal chain

`Real infrastructure -> Provider -> Adapter -> Monitoring Source -> Canonical Resource -> Metric Definition -> Metric Current State / Metric History -> Problem State -> Health Projection -> Monitoring publication -> Alerting Policy/Evaluation -> Alert -> Responsibility / ACK -> Notification Intent -> Delivery -> View/Read Evidence -> Response / Approval -> Escalation -> ITSM -> Automation -> AIOps -> UI / Reporting / Operations`

## Authority by step

### Real infrastructure
Physical/virtual systems are reality but are not directly writable business state in JLMirror.

### Provider
Current provider: Zabbix 7.4. Provider data is external evidence. Provider identity, ACK, timestamps and lifecycle semantics do not automatically become JLMirror truth.

### Adapter
Provider-specific translation boundary. It speaks Zabbix now and must allow additional providers later without changing canonical domain identities.

### Monitoring Source
Represents an external monitoring source owned by one tenant. Source generation is used to prevent stale identities/events from regaining current authority after reinstall/rebind/replacement.

### Canonical Resource
Platform-owned representation of a monitored resource. Provider object IDs are scoped evidence only.

### Metrics
- Metric Definition: what is measured.
- Metric Current State: current accepted value/state.
- Metric History: historical accepted observations; foundation exists, full historical product remains incomplete.

### Problem State
Monitoring-owned canonical problem occurrence. Current v1 lifecycle: `active | resolved`. Missing data from an incomplete query is not resolution.

### Health Projection
Monitoring-owned derived state: `unknown | healthy | degraded | unhealthy`. Healthy requires current authoritative completeness; absence of known problems alone is insufficient.

### Monitoring publication
Accepted invalidation contracts:
- `monitoring.problem-state.changed`
- `monitoring.health-projection.changed`

Events are invalidation/resync signals, not replicated semantic truth. Consumers must re-read current owner state.

### Alerting Policy/Evaluation
Determines whether current Monitoring truth is actionable. This remains the next business authorization gate after the Monitoring->Alerting publication runtime is accepted.

### Alert
Alerting-owned actionable occurrence. Accepted v1 lifecycle: `active | resolved`; resolved is terminal for that `alert_id`. Problem, Health and provider events are not Alerts.

### Responsibility / ACK
Future dedicated authority. One or more people may be responsible for a resource/operation. Responsibility, action ownership, ACK, viewer, notification recipient and approver are distinct identities/roles.

### Notification / Delivery / View Evidence
Future dedicated authority. Must distinguish dispatch request, provider acceptance, delivery, authoritative view/read evidence and response. Critical workflows must select mechanisms capable of producing authoritative visibility evidence on both internal and customer sides.

### Response / Approval
Future dedicated workflows such as `already_notified_awaiting_response`, `awaiting_budget_approval`, technical/customer positioning and explicit next-action ownership. Approval state is independent from notification delivery/view state.

### Escalation
Future timer/policy-driven operational escalation with durable clocks, retries, recovery and audit.

### ITSM
Owns incidents/tickets/tasks/SLA/change-style workflows. Alert != Incident.

### Automation
Owns runbooks/actions/executions. Automated action requires explicit authorization and does not redefine Monitoring/Alerting truth.

### AIOps
Owns correlation/anomaly/root-cause/finding-style intelligence over canonical evidence. AIOps finding != Alert != Incident.

### UI / Reporting / Operations
Presentation and interaction layer. UI is never business truth; it projects canonical domain state and immutable audit evidence.

## Current maturity snapshot
Monitoring core is substantially implemented. Monitoring->Alerting publication contracts are authorized and runtime implementation is in PR #148. Alert core semantics are authorized in PR #147. Alert Policy/Evaluation, Alert runtime, ACK/responsibility, authoritative human visibility, approvals, escalation, ITSM, Automation and AIOps remain downstream work.
