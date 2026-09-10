# Wave 4 Monitoring — Zabbix Metric Definitions + Bindings Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@18581e18b90f1c387d2b175ec4f4dac0fbf677d2`  
**Authorization ID:** `wave4.monitoring-metric-definitions@1`

## Purpose

This record defines the exact next bounded Monitoring Data Plane implementation slice after accepted Host Inventory: authenticated Zabbix `item.get` metadata ingestion into canonical `metric_definition` plus a separate provider binding/provenance surface.

This authorization deliberately does not include `metric_current_state`, `history.get`, `metric_observation`, triggers, problems, health projection, provider write-back or frontend behavior.

## Core product model

The slice separates three concepts that must never be collapsed:

```text
CANONICAL METRIC DEFINITION
  metric_definition_id
  monitoring_resource_id
  monitoring_source_id
  source_instance_generation
  name
  value_kind
  unit
  scope_state / scope_projection_revision / scope_evidence_state
  definition_state

PROVIDER BINDING / PROVENANCE
  provider_profile = zabbix
  provider_object_kind = zabbix_item
  itemid
  hostid association evidence
  key_
  native value type
  bounded provider metadata

METRIC VALUES
  metric_current_state / metric_observation
  NOT AUTHORIZED BY THIS SLICE
```

Architectural invariants:

```text
METRIC DEFINITION IDENTITY != PROVIDER ITEM ID
METRIC DEFINITION != PROVIDER BINDING
PROVIDER VALUE TYPE != CANONICAL VALUE KIND AUTHORITY BY ITSELF
ITEM.GET METADATA != METRIC HISTORY
ITEM.GET LASTVALUE != AUTHORIZED CURRENT-STATE INGESTION IN THIS SLICE
SCOPE EXCLUSION != METRIC RETIREMENT
GENERATION RETIREMENT != METRIC RETIREMENT
UNCERTAINTY != NEGATIVE EVIDENCE
ITEM-DEFINITION POLL GENERATION != HOST-INVENTORY POLL GENERATION
SHARED RECOVERY EPOCH/ADMISSION FRAMEWORK != SHARED ENDPOINT POLL SEQUENCE
```

## Authorized product behavior

1. **Read-only provider behavior.** The adapter may use bounded authenticated Zabbix `item.get` reads under the already accepted source/provider trust boundary. No provider write-back is authorized.
2. **Canonical metric identity.** Each accepted provider item maps to a stable opaque `metric_definition_id` inside exactly one `(tenant_id, monitoring_source_id, source_instance_generation)` provider identity domain and exactly one canonical `monitoring_resource_id`.
3. **Provider item identity remains external.** Zabbix `itemid` is never a canonical metric ID and is never comparable across tenants, monitoring sources or source-instance generations.
4. **Separate binding surface.** Provider-native fields required to locate/reconcile the item are persisted in a separate binding/provenance model rather than becoming canonical metric identity.
5. **Host ownership must resolve canonically.** An item may become a canonical metric definition only when its Zabbix host association resolves to an accepted canonical `monitoring_resource` in the same tenant/source/generation and that resource is eligible for current provider work under current scope authority.
6. **Canonical value kinds.** Zabbix float/numeric -> `number`; unsigned integer -> `integer`; character/string -> `string`; text -> `text`; log -> `log`. Boolean is not inferred from integer `0/1`; it requires a separately explicit semantic mapping.
7. **Unit is metadata, not authority.** Provider unit text may populate the canonical metric unit only after bounded canonical string validation. Unit text does not alter tenant, identity, authorization, scope or value kind.
8. **Names are provider-derived canonical metadata.** Provider item name may populate canonical `name` only after bounded canonicalization; it is not identity and changes do not create a new metric definition inside the same accepted provider binding.
9. **Definition lifecycle.** `definition_state` is only `active|retired`. Retirement requires authoritative negative item-inventory evidence under the active source generation/current scope. Missing/incomplete/stale/visibility-degraded provider results preserve the prior definition state and degrade evidence instead of retiring.
10. **Scope is independent from retirement.** `scope_state=out_of_scope` preserves metric identity/history and does not imply `retired`.
11. **Generation is independent from retirement.** A prior-generation metric definition becomes operationally historical by derivation and is not rewritten to `retired` merely because source generation changed.
12. **Snapshot omission is conditional authority.** Negative item evidence is valid only from a bounded complete item snapshot with current provider visibility, current source generation, current configured-scope revision and current platform poll authority.
13. **Provider metadata is bounded.** The implementation may retain only allowlisted item metadata necessary for binding, normalization, diagnostics and future value ingestion. Raw unrestricted `item.get` payload persistence is forbidden.
14. **No current-value ingestion.** Although `item.get` exposes `lastvalue/lastclock/lastns`, this slice may parse or validate those fields only if required to prove boundary compatibility; it must not persist or expose `metric_current_state`.
15. **No historical ingestion.** `history.get`, historical checkpoints/backfill and `metric_observation` storage are explicitly outside this slice.
16. **No per-item event fanout.** This slice does not create `monitoring.metric-current-state.changed`; definition discovery itself is not the current-state transition contract.
17. **No frontend implication.** Backend/domain/data support for metric definitions creates no frontend route/navigation authority.
18. **Shared recovery framework, independent item poll stream.** Item-definition polling reuses the already accepted recovery/placement admission semantics and ordered recovery epoch framework, but it owns a distinct item-definition poll generation stream. Host Inventory and Item Definition polls must never supersede one another merely because their independent endpoint cadences interleave.

## Canonical binding requirements

A Zabbix binding is scoped by at least:

```text
tenant_id
monitoring_source_id
source_instance_generation
metric_definition_id
monitoring_resource_id
provider_profile = zabbix
provider_object_kind = zabbix_item
provider_external_ref = itemid
```

The binding may additionally retain bounded provider metadata such as `key_`, native value type, item status/flags needed for reconciliation and exact host association evidence. Provider-specific metadata cannot silently broaden canonical semantics.

Within one tenant/source/generation, one accepted `itemid` has at most one active canonical binding. Matching `key_`, item name or units do not merge distinct provider item IDs. Reused item IDs across source generations are independent mappings.

## Item snapshot / reconciliation semantics

The implementation must preserve the same uncertainty discipline established by Host Inventory:

- configured host-group anchors are revalidated before omission may carry negative authority;
- item enumeration is bounded and completeness is explicit;
- a truncated or provider-visibility-degraded item snapshot cannot retire previously known metric definitions;
- a complete authoritative snapshot may retire an omitted active definition only when its owning resource remains within the relevant evidence domain;
- late/superseded item poll completion cannot override newer item-definition state;
- current platform item-definition poll epoch/generation is the authority for item-definition reconciliation, not Zabbix wall clock;
- recovery/failover/PITR cannot reuse stale poll authority without the already accepted recovery admission mechanism;
- the recovery/placement epoch and admission mechanism may be shared with Host Inventory because they express writer/placement continuity for the source;
- the monotonic item-definition poll generation must be distinct from `host_inventory_poll_generation`, because endpoint-specific cadences are independent and must not cancel unrelated in-flight work.

This split is deliberate: shared recovery authority avoids inventing a second recovery system, while independent endpoint poll streams prevent false supersession between `host.get` and `item.get` cycles.

## Explicitly outside this slice

This authorization does not permit:

- `metric_current_state` persistence or API behavior;
- use of `item.get.lastvalue`, `lastclock` or `lastns` as accepted current state;
- `history.get` or `metric_observation` ingestion;
- history checkpoints/backfill/finalization;
- trigger/problem/event ingestion;
- health projection;
- alerting/ITSM/AIOps behavior;
- provider write-back;
- raw provider payload replication;
- boolean inference from generic Zabbix integer values;
- cross-generation metric identity merging;
- sharing `host_inventory_poll_generation` as the item-definition poll sequence;
- tag/key/name-driven tenant, authorization or policy selection;
- production polling/retry/capacity numerics beyond hard safety bounds;
- HTTP route implementation beyond already accepted API contracts;
- frontend route or navigation creation.

## Acceptance boundary

This authorization becomes implementation authority only after its exact HEAD passes deterministic validation and panoramic/adversarial review and is separately squash-merged into `main`. Until then, implementation of the metric-definition slice remains blocked.
