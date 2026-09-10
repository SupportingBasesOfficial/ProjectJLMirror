# Organization Operating Model Contract

**Status:** proposed-for-separate-acceptance

## 1. Purpose

This contract defines the canonical organization, tenancy, delegated-operation, provider-operation, commercial-attribution, and cross-tenant accountability model for JLMIRROR.

It exists to ensure that JLMIRROR can simultaneously support:

- JLMIRROR's own managed monitoring service;
- direct SaaS customers using JLMIRROR for their own operations;
- MSPs/service providers using JLMIRROR to monitor multiple customer organizations;
- organizations whose infrastructure is monitored but which do not directly contract or pay JLMIRROR;
- shared provider installations, including one Zabbix installation containing scopes for many monitored organizations;
- dedicated provider installations;
- hybrid arrangements;
- platform-owner end-to-end operational, commercial, security and audit visibility without collapsing tenant isolation.

This contract does not grant implementation, frontend, production, billing-price, or provider-write authority by itself.

## 2. Foundational invariants

**OOM-INV-001 — Organization is not a rigid organization type.**
An organization is a stable business/administrative entity. Roles such as platform customer, monitoring service provider, provider operator, payer, beneficiary, and monitored organization are contextual relationships/responsibilities, not mutually-exclusive `organization_type` values.

**OOM-INV-002 — Tenant remains an isolation boundary.**
A tenant is the protected logical boundary for administration and tenant operational data. A monitored customer organization does not lose its own tenant boundary merely because another organization administers or pays for it.

**OOM-INV-003 — Delegation does not merge tenants.**
An MSP or service provider managing multiple customer organizations receives explicit delegated authority over the corresponding target tenants. Customer data MUST NOT be co-located conceptually into the MSP tenant merely to simplify administration.

**OOM-INV-004 — Commercial responsibility, operational responsibility and beneficiary identity are independent.**
The organization that pays, the organization that operates monitoring, the organization that operates the provider and the organization whose infrastructure is monitored MAY be different organizations.

**OOM-INV-005 — Provider visibility is not JLMIRROR authorization.**
A provider credential's effective visibility constrains what JLMIRROR can collect. JLMIRROR authorization independently constrains what each principal can read or mutate. Provider-native permissions never substitute for JLMIRROR tenant/resource authorization.

**OOM-INV-006 — Global platform visibility does not imply global unscoped mutation.**
Platform-owner personnel may receive explicitly authorized cross-tenant capabilities, but tenant isolation remains intact. Entering or mutating a target tenant context is a privileged, attributable, auditable operation.

**OOM-INV-007 — Every material managed object is traceable.**
For every material managed object, JLMIRROR MUST be able to determine, where applicable: owner, tenant, organization, operator, administrator, payer/billing attribution, entitlement source, provider/source lineage, effective authority, current state and audit/change lineage.

## 3. Canonical concepts

### 3.1 Organization

`Organization` is the stable identity for a real business/administrative entity represented inside JLMIRROR.

An organization MAY concurrently:

- directly contract JLMIRROR;
- operate one or more providers;
- provide monitoring services to other organizations;
- receive monitoring services from another organization;
- be the monitored organization for its own infrastructure;
- be the billing-responsible organization for other organizations;
- administer other organizations by explicit delegation.

No one of those responsibilities defines the organization's permanent type.

### 3.2 Tenant

`Tenant` is the protected platform boundary for one customer organization context and its tenant operational data.

A tenant identity remains stable across:

- provider replacement;
- MSP/service-provider replacement;
- contract migration;
- delegated administrator changes;
- organization display-name changes.

A service-provider change MUST NOT require recreating the monitored organization's tenant merely to transfer operational responsibility.

### 3.3 Organization relationship

An organization relationship is a directional, independently-lifecycled statement of responsibility or commercial/operational association.

The canonical relationship families are:

1. `contracts_platform` — identifies the organization commercially contracting JLMIRROR under a contract/account relationship.
2. `provides_monitoring_service_for` — identifies the organization operationally responsible for monitoring another organization.
3. `delegated_administration_for` — identifies explicitly delegated administrative authority over another organization/tenant; exact permissions remain separately authorized.
4. `billing_responsible_for` — identifies the organization/account to which another organization's billable usage is attributable when not billed directly.

Provider operation is represented against the provider instance rather than faked as an organization-to-organization type relationship.

Relationships MUST have stable identity, lifecycle and effective-period evidence. The inverse view MAY be derived; duplicated opposing records are not required.

### 3.4 Provider instance

`ProviderInstance` represents one external provider installation/account/control surface that has its own provider-instance identity.

Examples include:

- the JLMIRROR operator's shared Zabbix installation;
- an MSP's Zabbix installation;
- a customer's dedicated Zabbix installation;
- a future non-Zabbix provider account/project/subscription that acts as one provider authority boundary.

A provider instance has exactly one accountable primary operator organization at a time. Delegated operational principals MAY exist but do not erase the primary operator responsibility.

### 3.5 Provider access binding

`ProviderAccessBinding` represents the credential/secret binding and provider-native authority used by JLMIRROR to access a provider instance.

The binding MUST distinguish:

- provider instance;
- operator organization;
- secret/credential reference;
- effective provider-native permissions/scope evidence;
- lifecycle/currentness;
- revision/generation where required.

Raw secret values are not organization metadata and MUST NOT be exposed through ordinary organization/customer views.

### 3.6 Provider scope

`ProviderScope` is the provider-native subset selected or proven for a JLMIRROR monitoring responsibility.

For Zabbix, a configured scope MAY use host-group references. Other providers MAY use accounts, projects, folders, tags, device groups, subscriptions, sites or equivalent constructs.

The canonical JLMIRROR model MUST NOT assume every provider implements Zabbix Host Groups.

### 3.7 Provider-scope-to-tenant binding

`ProviderScopeTenantBinding` maps a provider instance/scope to the target tenant/organization whose Monitoring data that scope is authorized to populate.

This binding is explicit, stable-identity and revisioned. Human-readable provider names are labels, not ownership authority.

A rename of a Zabbix Host Group MUST NOT silently transfer tenant ownership.

### 3.8 Monitoring Source

Monitoring Source remains a Monitoring-domain concept representing an external data origin/attachment admitted for a tenant Monitoring context.

The post-contract implementation MUST distinguish:

- external provider-instance identity;
- provider access binding;
- provider scope;
- tenant/organization destination binding;
- Monitoring Source logical identity.

One physical provider instance MAY therefore participate in Monitoring Sources/bindings for many tenants without becoming many physical provider instances.

## 4. Supported operating models

### 4.1 JLMIRROR-managed monitoring service

Example:

- Platform owner: JLMIRROR operator organization.
- Platform contracting organization: monitored customer or another commercial account as contracted.
- Provider operator: JLMIRROR operator organization.
- Provider instance: shared JLMIRROR-operated Zabbix.
- Monitored organization: Customer A.
- Provider scope: Customer A Host Group(s).
- Target tenant: Customer A tenant.
- Monitoring service provider: JLMIRROR operator organization.
- Billing responsible organization: contract-defined payer.

Customer A does not become provider administrator merely because its infrastructure is represented by that provider scope.

### 4.2 MSP uses JLMIRROR as SaaS

Example:

- Platform owner: JLMIRROR operator organization.
- Contracting/payer organization: MSP Alpha.
- Provider operator: MSP Alpha.
- Provider instance: Zabbix Alpha.
- Monitored organizations: Customer A, B, C.
- Target tenants: distinct tenant A, tenant B, tenant C.
- Monitoring service provider: MSP Alpha.
- Billing attribution: customer usage may be attributed to MSP Alpha's JLMIRROR contract according to entitlements/meters.

MSP Alpha's delegated authority over A/B/C does not merge their tenant boundaries.

### 4.3 Direct internal-use customer

Example:

- Contracting/payer organization: Enterprise Y.
- Provider operator: Enterprise Y.
- Monitoring service provider: Enterprise Y or no separate external service-provider relationship.
- Monitored organization: Enterprise Y.
- Target tenant: Enterprise Y.

The same organization may therefore be payer, operator, administrator, service provider and beneficiary in one context.

### 4.4 Hybrid provider topology

An MSP MAY operate one shared provider for Customers A/B while Customer C uses a dedicated provider instance. JLMIRROR MUST support this without changing the identity of Customers A/B/C or their tenants.

## 5. Shared Zabbix rule

A single Zabbix provider instance MAY contain data for N monitored organizations.

Example:

- `Zabbix Central` — one physical provider instance;
- Host Group A -> Tenant A;
- Host Group B -> Tenant B;
- Host Group C -> Tenant C.

JLMIRROR MUST NOT model those as three physical Zabbix instances merely because there are three monitored organizations.

Provider credentials MAY be broad or narrow:

- a platform/operator credential MAY have provider-native visibility over A+B+C;
- a narrow credential MAY see only A;
- another credential MAY see only B.

Regardless of credential breadth, data admitted to tenant A remains authorized for tenant A according to JLMIRROR's own mapping and authorization rules.

## 6. Ownership conflict and fail-closed behavior

An accidental overlapping provider scope MUST NOT silently assign the same discovered provider-native object to multiple unrelated tenant owners.

If ownership cannot be proven unambiguously, the object/binding enters an explicit reconciliation state such as `ownership_conflict` / `reconciliation_required` and MUST NOT be silently reassigned.

Legitimate shared infrastructure requires an explicit shared-resource/service model. Shared ownership MUST NOT emerge accidentally from overlapping provider scopes.

## 7. Delegated authority model

A principal normally has membership in its home organization/tenant context.

A service-provider employee operating customer tenants does not need to become a fake employee/member of each customer organization merely to act there.

JLMIRROR MUST support delegated authority with at least:

- delegating/source organization;
- target organization/tenant;
- principal or group/role assignment;
- allowed actions/permissions;
- resource scope;
- effective period/lifecycle;
- current authorization-policy evidence;
- audit linkage.

Delegation is narrowing authority. It does not create implicit platform-global access.

Two employees of the same MSP MAY have different customer sets and resource scopes.

## 8. Roles, permissions and resource scopes

Default role names are convenience templates, not the authorization source of truth.

Authorization remains based on permission/action plus applicable tenant/resource scope and policy.

Examples of product-facing templates MAY include:

- Organization Owner;
- IT Administrator;
- IT Operator;
- Viewer;
- MSP Administrator;
- MSP Operator.

Custom roles remain first-class.

An Organization Owner MAY have broad organizational authority while having no provider-administration authority unless the organization also operates that provider and the principal is separately authorized for provider administration.

`Tenant Admin != Provider Admin` is a normative separation.

## 9. Display/TV principals

Display/TV access SHOULD be represented by an independently attributable non-human display/device principal rather than a shared human user account.

A display principal is expected to support:

- tenant binding;
- narrowly selected presentation/read permissions;
- resource/view scope;
- independent credential/device binding;
- rotation/revocation;
- optional expiry;
- no implicit administrative capabilities.

Exact frontend/session/device implementation remains separately authorized.

## 10. Commercial model and attribution

Commercial ownership remains in the Commercial bounded context.

The canonical commercial separation is:

- `beneficiary` — organization receiving/using the service;
- `payer` / billing responsible account — organization financially responsible to JLMIRROR;
- `operator` — organization operationally performing the relevant service/provider responsibility.

These identities MAY be the same or different.

A monitored organization that does not directly pay JLMIRROR still receives its own organization/tenant identity and protected operational-data boundary.

## 11. Contract, entitlement, permission and usage separation

These concepts are independent:

- Contract/Plan: commercial agreement.
- Entitlement: capability/limit granted by the commercial agreement.
- Permission: what a principal is authorized to do.
- Resource scope: where that permission applies.
- Usage/Meter: measured consumption attributable for commercial/operational purposes.
- Pricing policy: how metered/entitled usage becomes a charge.

`Entitlement != Permission` is normative.

An MSP contract MAY entitle Monitoring and ITSM while assigning only Monitoring to one managed customer. Entitlement propagation/assignment MUST be explicit and inspectable rather than an undocumented implicit inheritance.

Exact prices, quotas and production meter numerics are outside this contract.

## 12. Billing attribution

Every billable usage record/aggregate MUST be traceable, where applicable, to:

- consuming tenant;
- beneficiary organization;
- covering contract/entitlement;
- billing-responsible account/organization;
- meter identity/version;
- measured quantity/time window;
- pricing-policy reference when rated;
- source evidence sufficient for reconciliation.

A customer tenant's usage MAY therefore be billed to an MSP contract without changing the customer tenant's ownership.

## 13. Lifecycle and transfer

Organization, Tenant, Relationship, Contract, Provider Binding and Monitoring Source lifecycles are independent and MUST NOT be collapsed into one status.

Termination of `MSP Alpha provides_monitoring_service_for Customer A` MUST NOT delete Customer A.

A service-provider transfer MUST preserve Customer A's stable organization/tenant identity and historical records while:

1. fencing/revoking old delegated authority;
2. establishing successor relationship/authority;
3. establishing or updating provider mappings;
4. reconciling currentness and ownership;
5. activating successor operations only when authority is proven.

Historical audit/evidence remains attributable to the authority that existed when the action occurred.

## 14. Platform-owner sovereign operations view

JLMIRROR's platform owner requires end-to-end visibility across:

- organizations and tenants;
- organization relationships/delegations;
- contracts, entitlements, meters and billing attribution;
- principals, roles, permissions and resource scopes;
- provider instances, operators, credentials/bindings and scope mappings;
- Monitoring resources and lineage;
- workers, synchronization, reconciliation and backlogs;
- security/authentication/authorization evidence;
- audit/change history;
- deployments/platform health and internal observability.

This sovereign view is a governed control/operations plane, not a removal of tenant boundaries.

A platform user entering a customer's protected tenant/resource context MUST do so through explicitly privileged cross-tenant authority and required accountability controls. Support/cross-tenant actions MUST remain attributable.

## 15. Organization 360 traceability requirement

The platform-owner product experience MUST eventually be able to answer, for a material organization/object:

- What is this organization/object?
- Which tenant owns/protects its operational data?
- Who directly contracts JLMIRROR?
- Who is billed?
- Which contract/entitlement covers it?
- Who provides monitoring service?
- Who operates the source provider?
- Which provider instance and provider scope feed it?
- Which principals can access it and under which authority/delegation?
- What is its current operational/commercial/security state?
- What changed, who changed it, under which authorization, and when?

If JLMIRROR cannot answer a materially applicable question above from governed data/evidence, the corresponding model is incomplete.

## 16. Domain ownership boundaries

This contract does not transfer aggregate ownership between bounded contexts.

- Platform Management owns tenant lifecycle/registry/platform administration metadata.
- Organization & Access owns memberships, roles, permissions, custom roles, assignments/scopes, delegated-access policy and tenant-facing organization/access configuration.
- Commercial owns commercial accounts, contracts/plans, entitlements where commercial in nature, pricing/billing state, invoices/payments and billing attribution/rating policy.
- Monitoring owns Monitoring Source semantics, resource identity, synchronization/currentness and normalized monitoring data.
- Integrations/Provider adapters own provider-specific protocol translation/connector mechanics without owning Monitoring business semantics.
- Compliance & Governance owns protected audit/accountability authority while source domains remain responsible for producing required evidence.

Cross-domain references MUST use stable identities/contracts rather than direct ownership theft.

## 17. Implementation consequence for Wave 4 Monitoring

Before provider-validation/ingestion proceeds beyond the current local Monitoring Source foundation, the implementation design MUST account for:

- provider instance identity distinct from tenant destination;
- provider operator organization;
- provider access binding/credential identity;
- provider-native scope;
- explicit provider-scope-to-tenant binding;
- delegated operator authority where the actor/operator is not the monitored tenant;
- fail-closed ownership ambiguity;
- lineage sufficient to support platform-owner Organization 360 and billing attribution later without rewriting Monitoring history.

This clause does not merge or rewrite the historical authorization state of prior gates and does not itself authorize runtime implementation.

## 18. Explicit non-decisions / deferred authority

This contract deliberately does not select:

- exact commercial prices;
- production quotas/capacity numerics;
- exact billing meter catalogue;
- tax/invoice jurisdiction rules;
- exact frontend navigation/information architecture;
- exact device/session protocol for display principals;
- exact secret-manager vendor;
- exact provider-administrator UI;
- provider write-back;
- production deployment authority.

Those require their own accepted contracts/authorization where applicable.
