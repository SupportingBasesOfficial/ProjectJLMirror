# Logical Schemas and Data Ownership

**Status:** proposed baseline

Logical schemas communicate ownership. Exact file/ORM layout will follow implementation blueprint.

## Control Plane logical schemas

### `platform`

Owns:

- `tenants`;
- `cells`;
- `tenant_placements`;
- `tenant_lifecycle_operations`;
- platform feature/catalog metadata;
- global marketplace catalog;
- cell schema/capacity/health metadata used for placement.

### `identity`

Owns global principal authentication/session data when the identity implementation uses the Control Plane store. Tenant membership/authorization remains tenant-owned in the cell.

### `commercial`

Owns platform/customer commercial relationship, plans/contracts/billing/payment reconciliation when global to the SaaS relationship.

## Cell logical schemas

### `organization`

Tenant membership, tenant users/membership views, roles, permissions, custom roles, tenant settings, branding and feature enablement.

### `monitoring`

Monitoring sources, stable resources/devices, external provider references, metric definitions, current state, active problems/observations, synchronization state and health projections.

### `alerting`

Alerts, alert/notification policy, notifications, delivery intent/history, escalation and subscriptions.

### `itsm`

Tickets/incidents, comments, changes/RFCs, approvals/tasks, services, SLA, maintenance and knowledge base state.

### `automation`

Scripts/automation definitions, parameters, schedules/tasks, workflows, versions, executions and execution policy state.

### `infrastructure`

Assets/relationships, discovery/topology, certificates, firewall, backups, Kubernetes, capacity, drift and patch governance state.

### `aiops`

Derived anomaly/prediction/correlation findings and model/configuration metadata. It references but does not own source monitoring state.

### `finops`

Tenant infrastructure/service costs, budgets, analysis/forecast and optimization opportunities.

### `reporting`

Report definitions/schedules/deliveries, executive/public/TV read models and artifact metadata. It does not own the operational source entities it projects.

### `integrations`

Tenant API credential metadata, webhooks/deliveries, integration instances, marketplace installations and synchronization state.

### `data_admin`

Governed import/export/direct-query operation records and policy state.

### `governance`

Tenant-scoped compliance/evidence metadata and append-only audit records where logically stored with the cell.

### `system`

Technical reliability records such as outbox, inbox receipts, idempotency records and internal process/dispatch metadata. `system` does not become a generic business domain.

## Ownership rule

Only the owning domain/application service mutates its tables. Shared physical PostgreSQL does not grant logical write ownership.

## Foreign-key rule

Within a bounded context, database foreign keys are the default when the relationship is structurally authoritative.

Across bounded contexts, a physical FK is a deliberate design decision, not an automatic convenience. Cross-context references use stable IDs; a FK MAY be accepted when strong co-resident integrity materially outweighs future extraction cost. A FK never grants mutation ownership.

## Tenant-safe relationship rule

For pooled tenant tables, child relationships include tenant identity so the database can reject cross-tenant references even if application code is wrong.

Recommended relational shape:

```sql
-- parent
PRIMARY KEY (id)
UNIQUE (tenant_id, id)

-- child
FOREIGN KEY (tenant_id, parent_id)
  REFERENCES parent (tenant_id, id)
```

This pattern prevents a Tenant A child from referencing a Tenant B parent with a known ID.

## Uniqueness rule

Business uniqueness is scoped correctly:

```text
UNIQUE(tenant_id, ticket_number)
UNIQUE(tenant_id, external_provider, external_id)
UNIQUE(tenant_id, role_name)
```

Global uniqueness is used only for truly global concepts.
