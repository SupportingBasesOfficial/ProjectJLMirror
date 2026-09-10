# Wave 4 Monitoring — Host Inventory Product Behavior Authorization

**Status:** proposed / not authorized  
**Canonical base:** `main@b2214b498a0360ebf8091fe857ccffc107494ace`  
**Authorization ID:** `wave4.monitoring-host-inventory@1`

## Purpose

This record defines the exact Product behavior for the next bounded Wave 4 slice identified by the canonical implementation manifest: Zabbix host inventory ingestion with bounded provider evidence capture for future canonical device classification.

This proposal does **not** implement ingestion. No host inventory code may become canonical until this exact behavior is accepted and separately authorized for merge.

## Core product model

The slice separates three concepts that must never be collapsed:

```text
CANONICAL RESOURCE IDENTITY
  monitoring_resource_id

PROVIDER OBJECT IDENTITY / EVIDENCE
  provider_profile = zabbix
  provider_object_kind = host
  hostid + bounded host/inventory/interface/template/group/tag evidence

CANONICAL DEVICE KNOWLEDGE
  future/evolving platform classification and normalized attributes
```

A Zabbix `host` is the provider object from which the resource was observed. It is **not** a declaration that the physical or logical device is a generic host/server.

The JLMirror canonical resource identity remains stable for the accepted generation-scoped mapping even as knowledge about the resource becomes richer later.

## Proposed product behavior

If accepted, the next implementation slice may ingest Zabbix hosts into canonical `monitoring_resource` state under the already accepted Monitoring/Zabbix contracts and may retain a bounded provider-evidence profile useful for later device classification.

1. **Read-only provider behavior.** Inventory comes from bounded authenticated Zabbix reads only. No provider write-back is authorized.
2. **Canonical platform identity.** Each accepted Zabbix host maps to a stable opaque `monitoring_resource_id` inside exactly one `(tenant_id, monitoring_source_id, source_instance_generation)` identity domain. Zabbix `hostid` remains only a scoped external reference.
3. **No cross-generation identity reuse.** Matching `hostid`, name, address, serial, model or other provider fields across source generations never implicitly reuses a canonical resource identity.
4. **Provider object kind is not device taxonomy.** The initial provider object kind is `host`/`zabbix_host`. It describes the Zabbix object class only. It MUST NOT by itself classify the real device as server, switch, router, firewall, access point, VM, storage, appliance or any other canonical device type.
5. **Capture useful Zabbix device evidence now.** The slice may retrieve and persist bounded, normalized provider evidence exposed by accepted Zabbix host reads, including where available: host technical/display names, host inventory fields, interfaces, host groups, linked templates and bounded tags. Exact retained fields must be allowlisted and bounded; unrestricted raw provider payload persistence is forbidden.
6. **Provider evidence is not canonical truth.** Inventory fields, names, interfaces, groups, templates and tags are evidence about the resource. They cannot automatically select tenant, authorization, business ownership, placement, policy or canonical device classification merely because Zabbix supplied them.
7. **Classification-ready without premature classification.** The model must preserve enough provenance to support a later independently governed canonical classification layer such as device class/type, vendor, model, operating system, virtualization role or business role. This slice may normalize direct factual attributes only when their semantics are explicitly accepted; heuristic or multi-signal device classification requires a separately accepted classification contract.
8. **Classification enrichment must not replace identity.** Future SNMP, LLDP/CDP, agent inventory, CMDB, cloud, virtualization, manual operator input, rules or AI-assisted classification may enrich or revise knowledge about the same canonical resource without changing `monitoring_resource_id` within the accepted mapping.
9. **Provenance is mandatory.** Any retained provider-derived device attribute/evidence must remain attributable to the provider evidence from which it came. A later canonical classification must be able to distinguish provider-reported evidence from platform-derived or operator-asserted knowledge.
10. **Configured scope governs observation authority.** Only hosts proven within the source's currently configured host-group scope may enter current inventory authority.
11. **Current inventory defaults to active generation only.** Historical-generation resources remain retained evidence and are not presented as currently monitored unless an explicit historical read is requested under existing authorization rules.
12. **Presence is fail-closed.** Positive provider evidence may establish/confirm `presence_state=present`. A host missing from an incomplete, visibility-degraded, stale, wrong-generation, stale-scope or otherwise non-authoritative poll remains last-known and the evidence state degrades; absence alone does not mean removal.
13. **Removal requires authoritative negative evidence.** `presence_state=removed` may be committed only when a complete authoritative inventory snapshot for the active source generation/current scope proves absence according to the accepted provider reconciliation contract.
14. **Scope exclusion is not removal.** A resource becoming `out_of_scope` preserves identity/history and does not become `removed` solely because of the scope edit.
15. **Bounded canonical data and bounded evidence only.** This slice may persist canonical resource identity, display name, provider object kind, scoped external references, scope/presence evidence, required synchronization metadata and an allowlisted bounded Zabbix evidence profile. Arbitrary raw provider payload replication remains forbidden.
16. **No frontend implication.** Implementing host inventory backend/domain/API capability does not create or authorize a frontend route or navigation destination.

## Classification direction reserved by this authorization

This authorization intentionally prepares, but does not prematurely freeze, a future classification model conceptually capable of expressing:

```text
monitoring_resource_id
provider_object_kind
canonical_device_class
canonical_device_type
vendor
model
operating_system
virtualization_role
classification_source
classification_revision
classification_evidence_state
```

The exact taxonomy, precedence rules, confidence semantics and authority hierarchy for those canonical classification fields are **not** granted by this slice. They require a separate accepted Product/domain classification contract.

The architectural invariant established now is:

```text
RESOURCE IDENTITY != PROVIDER OBJECT TYPE
PROVIDER EVIDENCE != CANONICAL DEVICE CLASSIFICATION
CLASSIFICATION CHANGE != RESOURCE IDENTITY CHANGE
```

## Explicitly outside this slice

This authorization does not permit:

- metric-definition ingestion;
- metric current-state or history ingestion;
- problem/event ingestion;
- health projection;
- unrestricted raw Zabbix payload replication;
- treating host inventory, tags, templates, groups, names or interface types as automatic canonical device classification;
- a finalized global device taxonomy;
- heuristic/AI classification as canonical authority;
- tag-driven platform policy;
- host-to-business-service topology inference;
- cross-generation resource migration/linkage;
- provider write-back;
- retry/backoff production numerics;
- production deployment;
- frontend route/navigation creation.

## User-visible meaning if implemented

After implementation, JLMirror can know **which Zabbix hosts are currently part of the authorized monitored inventory** and can retain bounded evidence about what those resources appear to be, without confusing provider metadata with platform truth.

A temporary provider failure or incomplete poll cannot make assets disappear. A scope edit cannot pretend a host was deleted. A source replacement cannot merge two generations just because provider-native IDs happen to match. Future device classification can become progressively richer without forcing canonical resource identities to be recreated.

## Acceptance boundary

Acceptance of this proposal authorizes only the behavior above. Implementation must still be delivered in a separate PR with exact-head CI, PostgreSQL/provider falsification, tenant/generation/scope/negative-evidence proofs, bounded-provider-evidence proofs, panoramic/adversarial review and separate merge authorization.

Until this proposal is explicitly accepted, host inventory ingestion remains not authorized.
