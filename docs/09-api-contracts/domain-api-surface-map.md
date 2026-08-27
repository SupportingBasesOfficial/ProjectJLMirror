# Domain API Surface Map

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

This map reserves coherent public contract vocabulary for the accepted domain model without requiring every listed resource family to be implemented in the first product release.

The map answers: **if/when a capability exists, which domain owns its external contract and under what resource vocabulary should it evolve?**

Listing a resource family here does not itself create a Product requirement beyond the accepted upstream scope.

## Platform Management

Owner: **Platform Management**

Candidate platform-global families:

```text
/api/v1/platform/tenants
/api/v1/platform/tenants/{tenant_id}
/api/v1/platform/tenant-lifecycle-operations
/api/v1/platform/catalog
/api/v1/platform/feature-catalog
```

Lifecycle commands may include:

```text
POST .../tenants/{tenant_id}:provision
POST .../tenants/{tenant_id}:suspend
POST .../tenants/{tenant_id}:resume
POST .../tenants/{tenant_id}:relocate
POST .../tenants/{tenant_id}:decommission
```

Normal tenant-facing contracts SHALL NOT expose cell/database placement as caller-controlled configuration. Platform administration MAY expose safe placement/residency policy metadata without making physical topology part of tenant business identity.

## Identity

Owner: **Identity**

Candidate families:

```text
/api/v1/me/profile
/api/v1/me/sessions
/api/v1/me/security-methods
/api/v1/platform/principals          (privileged)
/api/v1/platform/identity-links      (privileged/administrative)
```

Browser login/session establishment may be BFF/profile-specific rather than a public machine API.

Identity-provider-native IDs remain external references.

## Organization & Access

Owner: **Organization & Access**

```text
/api/v1/tenants/{tenant_id}/memberships
/api/v1/tenants/{tenant_id}/roles
/api/v1/tenants/{tenant_id}/permissions
/api/v1/tenants/{tenant_id}/access-policies
/api/v1/tenants/{tenant_id}/settings
/api/v1/tenants/{tenant_id}/branding
/api/v1/tenants/{tenant_id}/features
```

Role/permission management SHALL preserve future resource-scope refinement. The initial route shape must not imply every permission is permanently tenant-global.

## Monitoring

Owner: **Monitoring**

```text
/api/v1/tenants/{tenant_id}/monitoring-sources
/api/v1/tenants/{tenant_id}/monitoring-resources
/api/v1/tenants/{tenant_id}/metric-definitions
/api/v1/tenants/{tenant_id}/metric-current-states
/api/v1/tenants/{tenant_id}/metric-observations
/api/v1/tenants/{tenant_id}/problems
/api/v1/tenants/{tenant_id}/health-projections
/api/v1/tenants/{tenant_id}/monitoring-sync-operations
```

`metric-current-states` is the bounded current-value projection owned by Monitoring and remains distinct from metric-definition metadata and historical observations. Historical telemetry queries require bounded resource/metric/time scope and cursor/export semantics. Provider-specific resource IDs never replace canonical monitoring resource IDs.

## Alerting

Owner: **Alerting**

```text
/api/v1/tenants/{tenant_id}/alerts
/api/v1/tenants/{tenant_id}/alert-policies
/api/v1/tenants/{tenant_id}/notification-policies
/api/v1/tenants/{tenant_id}/notification-deliveries
/api/v1/tenants/{tenant_id}/escalation-policies
```

Alert state is distinct from raw monitoring problem/observation state and from ITSM incidents.

## ITSM

Owner: **ITSM**

```text
/api/v1/tenants/{tenant_id}/incidents
/api/v1/tenants/{tenant_id}/incidents/{incident_id}/comments
/api/v1/tenants/{tenant_id}/changes
/api/v1/tenants/{tenant_id}/approvals
/api/v1/tenants/{tenant_id}/tasks
/api/v1/tenants/{tenant_id}/services
/api/v1/tenants/{tenant_id}/slas
/api/v1/tenants/{tenant_id}/maintenance-windows
/api/v1/tenants/{tenant_id}/knowledge-articles
```

Human-readable ticket/change numbers are lookup/display attributes independent from opaque IDs.

Policy-bearing transitions use explicit commands such as `:assign`, `:resolve`, `:approve` when a generic PATCH would bypass workflow invariants.

## Automation

Owner: **Automation**

```text
/api/v1/tenants/{tenant_id}/automation-definitions
/api/v1/tenants/{tenant_id}/scripts
/api/v1/tenants/{tenant_id}/schedules
/api/v1/tenants/{tenant_id}/workflows
/api/v1/tenants/{tenant_id}/automation-executions
```

Starting or cancelling execution uses explicit command/operation semantics. Script/secret content is subject to the smaller privileged trust envelope and does not appear in broad list responses by default.

## Infrastructure

Owner: **Infrastructure**

Candidate families expand without changing canonical asset/resource identity:

```text
/api/v1/tenants/{tenant_id}/assets
/api/v1/tenants/{tenant_id}/topology
/api/v1/tenants/{tenant_id}/certificates
/api/v1/tenants/{tenant_id}/firewall-posture
/api/v1/tenants/{tenant_id}/backup-posture
/api/v1/tenants/{tenant_id}/capacity
/api/v1/tenants/{tenant_id}/discovery
/api/v1/tenants/{tenant_id}/configuration-drift
/api/v1/tenants/{tenant_id}/patch-posture
/api/v1/tenants/{tenant_id}/kubernetes-resources
```

The exact resource decomposition is accepted incrementally with product scope; this map prevents a future provider-specific schema from becoming canonical by accident.

## AIOps

Owner: **AIOps**

```text
/api/v1/tenants/{tenant_id}/aiops-findings
/api/v1/tenants/{tenant_id}/anomalies
/api/v1/tenants/{tenant_id}/predictions
/api/v1/tenants/{tenant_id}/correlations
```

Findings reference source Monitoring/Infrastructure identities and expose explanation/configuration/model-version/confidence metadata where required. They do not redefine ownership of source state.

## FinOps

Owner: **FinOps**

```text
/api/v1/tenants/{tenant_id}/cost-entries
/api/v1/tenants/{tenant_id}/budgets
/api/v1/tenants/{tenant_id}/cost-forecasts
/api/v1/tenants/{tenant_id}/optimization-opportunities
```

Money/period/source/version semantics follow the Phase 09 representation rules.

## Commercial

Owner: **Commercial**

Platform/customer-global contracts may use:

```text
/api/v1/platform/customers
/api/v1/platform/contracts
/api/v1/platform/plans
/api/v1/platform/billing-cycles
/api/v1/platform/invoices
/api/v1/platform/payment-operations
```

If future commercial state is tenant-scoped for a specific product model, that is an explicit ownership/scope decision rather than copying FinOps route patterns.

External payment effects use required idempotency/operation reconciliation.

## Reporting & Experience

Owner: **Reporting & Experience**

```text
/api/v1/tenants/{tenant_id}/report-definitions
/api/v1/tenants/{tenant_id}/report-runs
/api/v1/tenants/{tenant_id}/artifacts
/api/v1/tenants/{tenant_id}/dashboard-projections
/api/v1/tenants/{tenant_id}/noc-projections
/public/v1/status-pages/...
```

Reports/dashboards are deliberate projections. They never grant Reporting mutation ownership over source domain state.

## Integrations & Extensibility

Owner: **Integrations & Extensibility**

```text
/api/v1/tenants/{tenant_id}/integrations
/api/v1/tenants/{tenant_id}/api-credentials
/api/v1/tenants/{tenant_id}/webhook-subscriptions
/api/v1/tenants/{tenant_id}/webhook-deliveries
/api/v1/tenants/{tenant_id}/marketplace-installations
/api/v1/tenants/{tenant_id}/sync-operations
```

API credential reads expose metadata only after creation. Outbound webhook message/event envelope belongs to Phase 10; Phase 09 owns management resources and delivery-status API semantics.

## Data Administration

Owner: **Data Administration**

```text
/api/v1/tenants/{tenant_id}/exports
/api/v1/tenants/{tenant_id}/imports
/api/v1/tenants/{tenant_id}/data-query-operations
```

Large work uses operation + artifact contracts. Direct SQL is not a generic API query language and uses a separately privileged endpoint/profile with strict bounds and tenant binding.

## Compliance & Governance

Owner: **Compliance & Governance** for governance/evidence state

```text
/api/v1/tenants/{tenant_id}/compliance-controls
/api/v1/tenants/{tenant_id}/compliance-evidence
/api/v1/tenants/{tenant_id}/data-rights-operations
/api/v1/tenants/{tenant_id}/legal-holds
/api/v1/tenants/{tenant_id}/audit-records
```

Audit records are append-only accountability projections under authorization/retention policy. Their presence does not grant governance routes direct mutation authority over source-domain state.

Governed deletion/anonymization/erasure is represented as explicit durable operations rather than arbitrary table deletion.

## Cross-cutting operation resources

Every domain may create tenant operation resources under the common operation contract:

```text
/api/v1/tenants/{tenant_id}/operations/{operation_id}
```

The operation resource identifies its `operation_type`/owner without exposing worker/queue topology.

## Cross-domain composition

A client screen may need Monitoring + Alerts + ITSM + AIOps data. That does not justify a generic cross-domain mutable `/dashboard` API that becomes owner of all state.

Read composition may occur through:

- BFF composition;
- explicit Reporting/Experience projection;
- accepted cross-domain read model.

Mutations remain owned use cases.

## Future domains

New accepted domains receive their own contract namespace/resource vocabulary. They are not placed under `misc`, `shared`, `common`, or another generic owner simply to avoid creating a clear boundary.

## Maximum-state test

This map is considered successful if the future platform can add many more resources inside these owned families—or new accepted families—without changing existing canonical IDs, tenant scope, security semantics or forcing clients to understand which internal component currently serves the route.