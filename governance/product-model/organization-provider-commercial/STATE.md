# Organization / Provider / Commercial Product Model — State

**Decision:** `organization-provider-commercial-model@1`  
**State:** `SEPARATELY_ACCEPTED`  
**Canonical base:** `main@8e2265a4ee2810ea701166228e8f44ad3bc0d894`  
**Reviewed source HEAD:** `ba2817a7586ed43b18eb72a139f1eba8ffeadfa0`  
**Accepted squash:** `8c9eb94ebe76a56db85dd1ecbd3e0f8569edfb62`  
**Decision record:** `adr/ADR-021-organization-provider-commercial-operating-model.md`

## Purpose

Record the separately accepted canonical product model that separates organization identity, tenant isolation, delegated service-provider authority, provider operation, monitored-organization ownership and commercial/billing attribution before Wave 4 Monitoring provider ingestion proceeds.

## Accepted decisions

- Organization is a stable entity with contextual responsibilities/relationships, not a rigid mutually-exclusive type.
- A monitored customer organization keeps its own tenant isolation boundary even when an MSP/service provider administers it or pays for its use.
- MSP/service-provider access to customer tenants is explicit delegated authority; it does not merge customer data into the MSP tenant.
- One physical provider instance may serve many target tenants.
- Provider operator, monitoring service provider, beneficiary and payer may be different organizations.
- Provider-native visibility and JLMIRROR authorization are independent layers.
- Provider scope -> target tenant/organization mapping is explicit, revisioned and ownership-bearing.
- Ownership ambiguity fails closed into reconciliation; overlap never silently reassigns tenant ownership.
- Contract, entitlement, principal permission, resource scope, usage meter and pricing policy are independent concepts.
- Service-provider/provider transitions preserve stable organization/tenant identity and historical evidence.
- Platform-owner global visibility does not remove tenant isolation; privileged cross-tenant operations remain attributable and auditable.
- Display/TV access is modeled as an independently attributable non-human principal with narrow scope.
- Platform-owner Organization 360 traceability is a product requirement.

## Wave 4 consequence

No provider validation/ingestion successor slice should assume `1 Monitoring Source = 1 physical provider = 1 organization`.

Before that successor implementation is authorized, its design must account for:

1. external provider-instance identity;
2. provider operator organization;
3. provider access/credential binding;
4. provider-native scope;
5. explicit target tenant/organization binding;
6. delegated operator authority when source operator differs from the monitored tenant;
7. fail-closed ownership conflict;
8. source/organization/authority lineage sufficient for later Organization 360 and billing attribution.

## Authority boundaries

This accepted state does **not**:

- merge or modify PR #124;
- authorize the Zabbix validation worker;
- authorize provider ingestion;
- authorize frontend routes/navigation;
- authorize provider write-back;
- select pricing amounts, quotas or production billing numerics;
- grant production authority;
- rewrite historical D2/D3/D4/Wave 4 authorization source-time truth.

Any implementation that consumes this model still requires the applicable separate implementation authority and exact-head review gates.
