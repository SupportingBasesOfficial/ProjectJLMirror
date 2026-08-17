# Product Capabilities

**Status:** proposed baseline

Capabilities are product-level outcomes. They intentionally avoid freezing implementation technologies.

## CAP-PLATFORM — Platform and tenant management
- create, provision, suspend, migrate, and decommission tenants through controlled lifecycle states;
- manage tenant placement independently from tenant business configuration;
- support privileged cross-tenant operations with explicit authorization and audit;
- manage global catalog and platform configuration.

## CAP-IDENTITY — Identity and access
- authenticate human and machine principals;
- support MFA and session lifecycle controls;
- resolve tenant memberships, roles, permissions, and custom roles;
- support external identity providers through adapters;
- revoke or constrain credentials without requiring application redeployment.

## CAP-MONITORING — Monitoring and operational visibility
- ingest and normalize data from monitoring sources;
- maintain current resource/device state separately from historical telemetry;
- expose metric/history, health, problems, and operational dashboards;
- synchronize tenants independently so one failing source does not stall unrelated tenants.

## CAP-ALERTING — Alerting and notification
- create actionable alerts from normalized operational conditions;
- correlate, route, notify, escalate, and record delivery outcomes;
- provide tenant-safe real-time updates and asynchronous channel delivery.

## CAP-ITSM — Service operations
- manage incidents/tickets, changes, approvals, tasks, services, SLAs, maintenance and knowledge;
- integrate with external ITSM platforms without surrendering domain ownership.

## CAP-AUTOMATION — Controlled automation
- define scripts/tasks/workflows and execution parameters;
- schedule or trigger work asynchronously;
- apply authorization, policy, approval, target scope, timeout, result capture, and audit;
- isolate execution from the API runtime when the execution risk requires it.

## CAP-INFRA — Infrastructure governance
- maintain asset and relationship/topology views;
- track security/configuration-related infrastructure state such as certificates, firewall rules, backup posture, drift, patches and capacity;
- support discovery and Kubernetes-related visibility.

## CAP-AIOPS — Operational intelligence
- produce anomalies, predictions, correlations, findings and recommendations from operational inputs;
- preserve input/configuration/model metadata sufficient for operational explanation and audit where applicable.

## CAP-FINOPS — Financial and commercial operations
- represent infrastructure costs, budgets and optimization opportunities;
- support accepted commercial/billing flows and external payment integration through explicit boundaries.

## CAP-REPORTING — Reporting and presentation
- generate reports and scheduled deliveries;
- expose executive projections and NOC/TV views;
- expose public status only through deliberate public projections.

## CAP-INTEGRATION — Integration and extensibility
- provide versioned APIs, API credentials, webhooks, connectors, marketplace capabilities and governed data transfer;
- protect privileged tools such as direct-query consoles with reduced trust boundaries.

## CAP-GOVERNANCE — Governance and compliance
- maintain immutable accountability records for relevant privileged/mutating activity;
- manage compliance controls/evidence and data-rights workflows;
- apply classification, retention and transfer rules.

## CAP-OPERABILITY — Operability
- expose health, structured logs, metrics, traces, errors and queue/worker state;
- support graceful degradation, recovery, capacity analysis and incident diagnosis.