# Wave 4 — Monitoring implementation state

Current bounded implementation: `wave4.monitoring-source-foundation@2`.

Implementation authority remains `main@8e2265a4ee2810ea701166228e8f44ad3bc0d894`, authorization `wave4.monitoring-zabbix.vertical@1`.

Successor compatibility baseline: `main@3c66b5e70e6d12f373315b95e3feefdfbf47e941`, accepted `organization-provider-commercial-model@1`, ADR-022.

## What is real in this slice

- tenant-scoped logical Monitoring source model;
- opaque source-instance generation separated from logical source identity;
- explicit `provider_instance_ref` on immutable source-generation lineage;
- explicit stable `provider_scope_tenant_binding_id` on the tenant-scoped Monitoring source;
- multiple tenants may reference the same physical/logical provider instance without sharing source identity, binding identity, idempotency or tenant authority;
- `credential_binding_ref` remains an opaque access/secret-binding reference, never raw credential bytes;
- configured Zabbix HostGroup scope remains bounded and tenant-source scoped;
- local source creation starts with `operational_evidence_state=reconciliation_required` and durable `validation_and_initial_sync` work;
- PostgreSQL source/generation/sync/idempotency/audit creation remains atomic;
- same-tenant/same-key/same-fingerprint replay returns the original logical result;
- same-tenant/same-key/different-fingerprint fails as `idempotency.key_reused`;
- the same idempotency key remains independent across tenants;
- source-generation records are immutable;
- mutable credential/scope edits remain source configuration and do not create a fake new physical provider instance;
- privileged local audit evidence remains append-only and excludes provider URL, credentials, configured provider scope and raw provider payload;
- no DNS, provider connection, Zabbix authentication or provider network call occurs inside source creation.

## Shared-provider invariant

One `provider_instance_ref` MAY be referenced by many independently isolated Monitoring sources, for example one platform-operated Zabbix serving several customer HostGroups.

This does not imply:

- one tenant owns the shared provider installation;
- provider visibility is JLMIRROR authorization;
- one source can populate another tenant;
- source-instance generation is physical-provider ownership;
- the provider operator organization is implemented or inferred inside this slice.

Provider operator, Organization runtime, delegated MSP authority and Commercial runtime remain outside this bounded implementation.

## Deliberately not implemented

No provider-instance registry runtime, Organization/Commercial runtime, provider-operator resolution, MSP delegation runtime, Zabbix network client, credential secret resolution, DNS/egress decision, provider call, resource/metric/problem ingestion, history adapter, HTTP adapter, browser UI, realtime, provider write-back, central Compliance audit projection/external delivery, production deployment or C3 production numerics are implemented here.

The next bounded implementation step is worker-owned Zabbix validation and initial synchronization only after this source-lineage successor slice is accepted.

Frontend Product Experience remains separately designed. Backend entity/API/table/use-case shape does not define route/navigation shape.
