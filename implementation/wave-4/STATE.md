# Wave 4 — Monitoring implementation state

Current bounded implementation: `wave4.monitoring-source-foundation@1`.

Canonical implementation authorization: `main@8e2265a4ee2810ea701166228e8f44ad3bc0d894`, authorization `wave4.monitoring-zabbix.vertical@1`.

## What is real in this slice

- canonical logical Monitoring source model;
- opaque source-instance generation separated from logical source identity;
- deterministic/static Zabbix HTTPS configuration validation with canonical textual admission;
- canonical configured host-group scope representation;
- local source-creation plan with revisions `1/1` and initial evidence `reconciliation_required`;
- PostgreSQL logical source + immutable historical generation + durable sync-operation + create-idempotency records;
- atomic `monitoring.create_zabbix_source(...)` create-or-observe transaction;
- same-tenant/same-key/same-fingerprint replay returns the original logical source/sync result;
- same-tenant/same-key/different-fingerprint is rejected as `idempotency.key_reused`;
- the same key remains independent across tenants;
- mutable credential binding and configured scope remain on logical source authority while provider endpoint identity is generation-bound;
- durable `validation_and_initial_sync` responsibility, explicitly outside the source-configuration transaction's network boundary;
- executable conformance against a digest-pinned PostgreSQL image proving migration, transaction, tenant isolation, replay, generation immutability and revision-regression guards.

## What is deliberately not claimed yet

No Zabbix network client, credential resolution, DNS/egress decision, provider call, resource/metric/problem ingestion, history adapter, HTTP adapter, browser UI, realtime, provider write-back, production deployment or C3 production numerics are implemented by this slice.

The next bounded implementation step is the worker-owned Zabbix validation and initial synchronization flow against the persisted source generation.

Frontend Product Experience remains separately designed. Backend entity/API/table/use-case shape does not define route/navigation shape.
