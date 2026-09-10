# Monitoring Source Compatibility Overlay

**Status:** candidate companion to `organization-provider-commercial-model@1`

## Purpose

Preserve the accepted source-time truth of Wave 4 Monitoring contracts while removing an ambiguity exposed by the later organization/provider/commercial operating-model decision.

Existing accepted Monitoring/Zabbix contracts use phrases such as `tenant-configured Zabbix API URL`, `tenant's instance`, `zabbix_instance_generation`, and a tenant-scoped `monitoring_source_id`.

Those phrases MUST NOT be interpreted as any of the following:

- every tenant owns the physical Zabbix installation it reads from;
- every tenant Monitoring Source corresponds to a unique physical Zabbix installation;
- one physical Zabbix installation cannot serve multiple tenant Monitoring Sources;
- provider administration authority belongs to the monitored tenant merely because the source is configured in that tenant context.

## Successor interpretation

Under the candidate organization operating model:

1. A tenant-scoped `Monitoring Source` remains the Monitoring-domain attachment/external-origin authority for that tenant.
2. A separate `ProviderInstance` identity represents the external physical/logical provider installation/account/control surface.
3. Multiple tenant-scoped Monitoring Sources/bindings MAY reference the same `ProviderInstance` when that provider is shared.
4. `ProviderScopeTenantBinding` proves which provider-native subset may populate which target tenant.
5. `ProviderAccessBinding` proves which credential/secret binding is used and under which provider-native authority.
6. `ProviderInstance` has an accountable primary operator organization independent from the target monitored tenant.
7. JLMIRROR tenant/resource authorization is enforced independently of provider-native credential breadth.

## Generation compatibility

The accepted `observation_identity_scope = (tenant_id, monitoring_source_id, "zabbix", zabbix_instance_generation)` remains valid and MUST continue preventing cross-tenant or cross-generation identity contamination.

The candidate `ProviderInstance` identity does not authorize removing `tenant_id` or `monitoring_source_id` from canonical Monitoring identity scope merely because two tenant sources happen to reference the same shared Zabbix installation.

`zabbix_instance_generation` in the accepted Monitoring contract continues to fence the provider identity generation relevant to that tenant Monitoring Source. A future implementation MAY additionally maintain a provider-instance generation/control-plane identity if required, but that does not retroactively change historical Monitoring event identity.

## Shared Zabbix example

```text
ProviderInstance: Zabbix Central
operator: JLMIRROR operator organization

Tenant A Monitoring Source
  -> ProviderAccessBinding A or shared operator binding
  -> ProviderScope: HostGroup A
  -> ProviderScopeTenantBinding -> Tenant A

Tenant B Monitoring Source
  -> ProviderAccessBinding B or shared operator binding
  -> ProviderScope: HostGroup B
  -> ProviderScopeTenantBinding -> Tenant B
```

Both Monitoring Sources may resolve to the same provider endpoint while remaining distinct tenant authorities and identity scopes.

## Base-URL replacement compatibility

The accepted rule that an ordinary Monitoring Source base-URL edit requires the explicit source-instance replacement workflow remains intact.

The organization/provider model does not weaken this guard. If the underlying provider attachment changes in a way that can invalidate provider identity comparison, the tenant Monitoring Source generation transition remains explicitly governed.

Future provider-instance registry work may make same-provider-instance endpoint migration more precisely provable, but no such inference is authorized by this compatibility overlay.

## Authority boundary

This document is interpretive governance only. It does not authorize:

- runtime implementation;
- migration of PR #124;
- provider validation/ingestion;
- changes to accepted Monitoring API/event payloads;
- provider write-back;
- production deployment.
