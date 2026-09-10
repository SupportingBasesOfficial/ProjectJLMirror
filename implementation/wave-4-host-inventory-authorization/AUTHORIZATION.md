# Wave 4 Monitoring — Host Inventory Product Behavior Authorization

**Status:** accepted via PR #133; implementation remains blocked until post-merge `resource_kind` clarification is canonical  
**Accepted merge:** `main@f85b01cce8e148123dd980ae6b60f83c707263f5`  
**Authorization ID:** `wave4.monitoring-host-inventory@1`

## Purpose

This record defines the exact Product behavior for the bounded Wave 4 Zabbix host inventory slice, including bounded provider-evidence capture for future canonical device classification.

PR #133 accepted the product direction, but a late post-merge P1 review identified one material omission: the accepted Monitoring contract requires canonical `monitoring_resource.resource_kind`, and the authorization did not explicitly bind its value. No host-inventory implementation may begin until this clarification is canonical.

## Core product model

The slice separates four concepts that must never be collapsed:

```text
CANONICAL RESOURCE IDENTITY
  monitoring_resource_id

CANONICAL MONITORING RESOURCE CLASS
  resource_kind = host

PROVIDER OBJECT IDENTITY / EVIDENCE
  provider_profile = zabbix
  provider_object_kind = zabbix_host
  hostid + bounded host/inventory/interface/template/group/tag evidence

CANONICAL DEVICE KNOWLEDGE
  future/evolving platform classification and normalized attributes
```

`resource_kind=host` is the initial broad canonical Monitoring resource class for resources created from the accepted Zabbix host-inventory slice. It means only that the Monitoring resource is a host-class monitored resource. It does **not** classify the actual device as a server or any other physical/logical device type.

`provider_object_kind=zabbix_host` describes the provider-native object class from which the resource was observed. It is provider evidence/origin metadata, not canonical device taxonomy.

Future canonical device classification such as server, switch, router, firewall, access point, VM, storage, appliance or other classes remains independently governed and may evolve without changing `monitoring_resource_id` or `resource_kind=host` for this accepted slice.

## Exact `resource_kind` mapping

For this initial authorized slice:

```text
accepted Zabbix host object
  -> provider_object_kind = zabbix_host
  -> monitoring_resource.resource_kind = host
```

Normative rules:

- every canonical `monitoring_resource` created by this slice MUST persist `resource_kind=host`;
- the implementation MUST NOT choose `zabbix_host`, `server`, `device`, `unknown`, or any other value for `resource_kind` in this slice;
- `resource_kind` is platform-owned and provider-neutral at the Monitoring domain level;
- `provider_object_kind` remains separately provider-scoped;
- future device taxonomy/classification is separate state and cannot silently redefine `resource_kind` semantics;
- a later expansion of canonical Monitoring resource classes requires a separately accepted compatibility/product contract rather than implementation inference.

This closes the ambiguity identified by the late PR #133 review and makes the accepted domain/API `resource_kind` field implementable without conflating it with device taxonomy.

## Authorized product behavior

The next implementation slice may ingest Zabbix hosts into canonical `monitoring_resource` state under the accepted Monitoring/Zabbix contracts and may retain a bounded provider-evidence profile useful for later device classification.

1. **Read-only provider behavior.** Inventory comes from bounded authenticated Zabbix reads only. No provider write-back is authorized.
2. **Canonical platform identity.** Each accepted Zabbix host maps to a stable opaque `monitoring_resource_id` inside exactly one `(tenant_id, monitoring_source_id, source_instance_generation)` identity domain. Zabbix `hostid` remains only a scoped external reference.
3. **No cross-generation identity reuse.** Matching `hostid`, name, address, serial, model or other provider fields across source generations never implicitly reuses a canonical resource identity.
4. **Canonical resource class.** Every accepted resource in this slice uses `resource_kind=host` exactly as defined above.
5. **Provider object kind is not device taxonomy.** `provider_object_kind=zabbix_host` describes the Zabbix object only and MUST NOT classify the real device.
6. **Capture useful Zabbix device evidence now.** The slice may retrieve and persist bounded, normalized provider evidence exposed by accepted Zabbix host reads, including where available host technical/display names, host inventory fields, interfaces, host groups, linked templates and bounded tags. Exact retained fields must be allowlisted and bounded; unrestricted raw provider payload persistence is forbidden.
7. **Provider evidence is not canonical truth.** Inventory fields, names, interfaces, groups, templates and tags cannot automatically select tenant, authorization, business ownership, placement, policy or canonical device classification merely because Zabbix supplied them.
8. **Classification-ready without premature classification.** The model must preserve provenance for a later independently governed canonical classification layer. Heuristic or multi-signal device classification requires a separately accepted classification contract.
9. **Classification enrichment must not replace identity.** Future SNMP, LLDP/CDP, agent inventory, CMDB, cloud, virtualization, manual operator input, rules or AI-assisted classification may enrich or revise knowledge about the same canonical resource without changing the accepted resource identity.
10. **Provenance is mandatory.** Retained provider-derived evidence must remain attributable to its source.
11. **Configured scope governs observation authority.** Only hosts proven within the source's currently configured host-group scope may enter current inventory authority.
12. **Current inventory defaults to active generation only.** Historical-generation resources remain retained evidence and are not presented as currently monitored by default.
13. **Presence is fail-closed.** Incomplete, stale, visibility-degraded, wrong-generation or stale-scope evidence cannot remove a previously known resource.
14. **Removal requires authoritative negative evidence.** `presence_state=removed` requires a complete authoritative inventory snapshot for the active generation/current scope.
15. **Scope exclusion is not removal.** `out_of_scope` preserves identity/history and does not imply `removed`.
16. **Bounded canonical data and bounded evidence only.** Arbitrary raw provider payload replication remains forbidden.
17. **No frontend implication.** Backend/domain/API host-inventory capability does not create or authorize a frontend route.

## Classification direction reserved by this authorization

Future classification may conceptually express:

```text
monitoring_resource_id
resource_kind
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

The exact device taxonomy, precedence rules, confidence semantics and authority hierarchy remain outside this slice.

Architectural invariants:

```text
RESOURCE IDENTITY != RESOURCE KIND
RESOURCE KIND != PROVIDER OBJECT TYPE
PROVIDER EVIDENCE != CANONICAL DEVICE CLASSIFICATION
CLASSIFICATION CHANGE != RESOURCE IDENTITY CHANGE
```

## Explicitly outside this slice

This authorization does not permit metric ingestion, problem/event ingestion, health projection, unrestricted raw Zabbix payload replication, automatic canonical device classification from provider metadata, a finalized global device taxonomy, heuristic/AI classification as canonical authority, tag-driven platform policy, business-service topology inference, cross-generation identity migration, provider write-back, production numerics/deployment or frontend route/navigation creation.

## Acceptance boundary

PR #133 accepted the host-inventory product direction. This successor clarification must itself pass exact-head CI, panoramic/adversarial review and separate merge authorization. Until it is canonical, host-inventory implementation remains blocked.
