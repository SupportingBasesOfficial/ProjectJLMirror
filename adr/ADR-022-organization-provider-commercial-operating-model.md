# ADR-022 — Organization, Provider and Commercial Operating Model

**Status:** accepted  
**Date:** 2026-09-09  
**Accepted by:** PR #125 successor acceptance state  
**Accepted source HEAD:** `ba2817a7586ed43b18eb72a139f1eba8ffeadfa0`  
**Accepted squash:** `8c9eb94ebe76a56db85dd1ecbd3e0f8569edfb62`  
**Reversibility:** reversible only through an explicit successor ADR because this decision constrains tenancy, provider ownership, delegated authority, Monitoring lineage and Commercial attribution.

## Context

JLMIRROR must support several operating models at the same time:

- JLMIRROR-operated managed monitoring, including one shared Zabbix installation containing data for many customer organizations;
- MSPs/service providers that contract JLMIRROR and operate their own providers for many customers;
- direct SaaS customers that use JLMIRROR for their own infrastructure;
- customers whose infrastructure is monitored but whose payer, provider operator or monitoring service provider is another organization;
- dedicated and hybrid provider topologies.

Treating organization identity, tenant isolation, provider installation identity, monitoring responsibility, provider operation and billing responsibility as one concept would either weaken tenant isolation or force duplicate/incorrect provider identities.

Accepted tenancy already establishes that a tenant is a protected customer-organization boundary. Accepted Monitoring already establishes tenant-scoped Monitoring Source identity and provider-generation-scoped external identity. The missing architectural decision was how those authorities compose when a physical provider installation is shared across organizations or operated by an organization different from the monitored customer.

## Decision

### Organization and tenant

`Organization` is a stable business/administrative entity. Operational/commercial roles such as platform customer, monitoring service provider, provider operator, payer, beneficiary and monitored organization are contextual responsibilities or relationships, not mutually-exclusive organization types.

A monitored customer organization retains its own tenant isolation boundary even when another organization administers, monitors or pays for it. Delegated MSP/service-provider authority does not merge customer tenants.

### Provider instance

Introduce the architectural concept `ProviderInstance` for one physical/logical external provider installation/account/control surface.

One `ProviderInstance` MAY serve many tenant-scoped Monitoring responsibilities. For example, one JLMIRROR-operated Zabbix instance may expose separate Host Group scopes for Customer A, B and C without becoming three physical provider instances.

Each `ProviderInstance` has exactly one accountable primary operator organization at a time. Additional delegated operational principals may exist, but responsibility remains attributable.

### Provider access and scope

Provider credentials/access bindings and provider-native scopes are separate from tenant authorization.

A `ProviderAccessBinding` identifies how JLMIRROR accesses a provider instance. A `ProviderScopeTenantBinding` explicitly maps provider-native scope to the target tenant/organization whose Monitoring domain may be populated from that scope.

Provider visibility is not JLMIRROR authorization. A broad provider credential may read data for several organizations, while JLMIRROR still admits each object only into its explicitly authorized tenant context.

Ownership ambiguity fails closed. Overlapping or ambiguous provider scope does not silently assign or transfer tenant ownership; it enters reconciliation-required state.

### Monitoring Source compatibility

Tenant-scoped `MonitoringSource` remains the Monitoring-domain attachment/external-origin authority. It is not redefined as the physical provider installation.

Multiple tenant-scoped Monitoring Sources MAY reference the same `ProviderInstance` while retaining independent tenant identity, source identity, provider scope, credential/access binding and authorization.

The previously accepted Zabbix identity scope remains:

```text
(tenant_id, monitoring_source_id, "zabbix", zabbix_instance_generation)
```

The accepted explicit base-URL/source-instance replacement semantics also remain in force. Sharing a physical provider instance does not transfer provider administration authority to a monitored tenant.

### Commercial and authority separation

Commercial beneficiary, payer/billing-responsible organization, monitoring service provider and provider operator are independent dimensions.

Contract/plan, entitlement, principal permission, resource scope, usage/meter and pricing policy are distinct concepts. Entitlement never substitutes for authorization.

Cross-tenant platform-owner access remains explicitly privileged, attributable and auditable; platform-global visibility is not a bypass of tenant isolation.

## Consequences

Positive consequences:

- one shared provider installation can safely serve many isolated tenants;
- MSP/customer data remains separated even when MSP staff have delegated authority;
- provider administration is separated from tenant administration;
- billing attribution can point to a payer/contract different from the monitored tenant without changing data ownership;
- service-provider/provider transfers can preserve stable tenant and historical identity;
- Organization 360 can reconstruct ownership, operator, payer, provider lineage, authority and audit lineage.

Costs and constraints:

- provider ingestion must carry explicit provider-instance and tenant-binding lineage;
- ambiguous mappings require reconciliation instead of optimistic assignment;
- delegated authority requires explicit lifecycle/currentness handling;
- Commercial, Organization & Access, Platform Management and Monitoring must communicate through stable contracts rather than sharing ownership.

## Rejected alternatives

### One tenant for an MSP and all of its customers

Rejected because it weakens the accepted customer isolation boundary and increases cross-customer data-mixing risk.

### One physical provider instance per monitored organization

Rejected because it misrepresents shared-provider deployments such as one central Zabbix installation serving N companies.

### Provider permission as customer authorization

Rejected because provider-native visibility cannot express or replace JLMIRROR's tenant/resource authorization model.

### Rigid organization types

Rejected because the same organization may concurrently contract JLMIRROR, operate a provider, provide monitoring and be monitored itself.

## Traceability

Primary product contract:

- `docs/03-domains/organization-operating-model-contract.md`

Compatibility overlay:

- `governance/product-model/organization-provider-commercial/MONITORING_COMPATIBILITY.md`

Accepted state/evidence:

- `governance/product-model/organization-provider-commercial/DECISION_MANIFEST.json`
- `governance/product-model/organization-provider-commercial/STATE.md`

Related accepted authorities:

- `adr/ADR-003-tenant-isolation.md`
- `adr/ADR-005-identity-and-authorization.md`
- `adr/ADR-013-external-provider-adapters.md`
- `adr/ADR-021-monitoring-source-instance-replacement.md`
- `docs/03-domains/monitoring-domain-contract.md`
- `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md`
- `docs/02-requirements/business-rules.md`

## Authority boundary

ADR-022 does not authorize runtime implementation, frontend/navigation, provider write-back, production deployment, production capacity numerics or exact commercial prices. Those remain governed by their respective implementation/product/production gates.
