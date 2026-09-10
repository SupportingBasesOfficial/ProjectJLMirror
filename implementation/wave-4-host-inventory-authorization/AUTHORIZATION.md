# Wave 4 Monitoring — Host Inventory Product Behavior Authorization

**Status:** proposed / not authorized  
**Canonical base:** `main@b2214b498a0360ebf8091fe857ccffc107494ace`  
**Authorization ID:** `wave4.monitoring-host-inventory@1`

## Purpose

This record defines the exact Product behavior for the next bounded Wave 4 slice identified by the canonical implementation manifest: Zabbix host inventory ingestion.

This proposal does **not** implement ingestion. No host inventory code may become canonical until this exact behavior is accepted and separately authorized for merge.

## Proposed product behavior

If accepted, the next implementation slice may ingest only Zabbix hosts into canonical `monitoring_resource` state under the already accepted Monitoring/Zabbix contracts.

The initial behavior is intentionally conservative:

1. **Read-only provider behavior.** Inventory comes from bounded authenticated Zabbix reads only. No provider write-back is authorized.
2. **Canonical platform identity.** Each accepted Zabbix host maps to a stable opaque `monitoring_resource_id` inside exactly one `(tenant_id, monitoring_source_id, source_instance_generation)` identity domain. Zabbix `hostid` remains only a scoped external reference.
3. **No cross-generation identity reuse.** Matching `hostid`, name, address or other provider fields across source generations never implicitly reuses a canonical resource identity.
4. **Initial resource kind is `host`.** This slice does not infer `server`, `network_device`, `appliance`, operating-system class or business role from provider metadata. Richer classification requires a later accepted mapping.
5. **Configured scope governs observation authority.** Only hosts proven within the source's currently configured host-group scope may enter current inventory authority.
6. **Current inventory defaults to active generation only.** Historical-generation resources remain retained evidence and are not presented as currently monitored unless an explicit historical read is requested under existing authorization rules.
7. **Presence is fail-closed.** Positive provider evidence may establish/confirm `presence_state=present`. A host missing from an incomplete, visibility-degraded, stale, wrong-generation, stale-scope or otherwise non-authoritative poll remains last-known and the evidence state degrades; absence alone does not mean removal.
8. **Removal requires authoritative negative evidence.** `presence_state=removed` may be committed only when a complete authoritative inventory snapshot for the active source generation/current scope proves absence according to the accepted provider reconciliation contract.
9. **Scope exclusion is not removal.** A resource becoming `out_of_scope` preserves identity/history and does not become `removed` solely because of the scope edit.
10. **Bounded canonical data only.** This slice may persist canonical resource identity, display name, resource kind, scoped external references, scope/presence evidence and required synchronization metadata. It does not authorize arbitrary raw provider payload storage.
11. **No derived customer semantics from provider metadata.** Host groups, interfaces, IPs, tags, templates, inventory fields or names cannot select tenant, authorization, business ownership, physical placement or policy.
12. **No frontend implication.** Implementing host inventory backend/domain/API capability does not create or authorize a frontend route or navigation destination.

## Explicitly outside this slice

This authorization does not permit:

- metric-definition ingestion;
- metric current-state or history ingestion;
- problem/event ingestion;
- health projection;
- host interface inventory as a separate canonical domain model;
- arbitrary Zabbix inventory/custom-field replication;
- tag-driven platform policy;
- host-to-business-service topology inference;
- cross-generation resource migration/linkage;
- provider write-back;
- retry/backoff production numerics;
- production deployment;
- frontend route/navigation creation.

## User-visible meaning if implemented

After implementation, JLMirror can know **which Zabbix hosts are currently part of the authorized monitored inventory**, while preserving uncertainty correctly. A temporary provider failure or incomplete poll cannot make assets disappear. A scope edit cannot pretend a host was deleted. A source replacement cannot merge two generations just because provider-native IDs happen to match.

## Acceptance boundary

Acceptance of this proposal authorizes only the behavior above. Implementation must still be delivered in a separate PR with exact-head CI, PostgreSQL/provider falsification, tenant/generation/scope/negative-evidence proofs, panoramic/adversarial review and separate merge authorization.

Until this proposal is explicitly accepted, host inventory ingestion remains not authorized.
