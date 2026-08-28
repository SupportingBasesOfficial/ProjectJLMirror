# Zabbix Monitoring — Canonical Normalization Profile

**Status:** proposed baseline  
**Provider:** Zabbix  
**Owner of canonical semantics:** Monitoring  
**Companions:** `zabbix-monitoring-source-provider-contract.md`, `monitoring-domain-api-contract.md`, `docs/03-domains/monitoring-domain-contract.md`  
**Traceability:** `FR-MON-002`, `FR-MON-006`, ADR-013, `docs/03-domains/bounded-contexts.md`

## Purpose

`zabbix-monitoring-source-provider-contract.md` deliberately left one normalization question to the later Monitoring domain/API design: whether Zabbix `problem.get` acknowledgement/severity/tag fields map directly into JLMIRROR problem/health semantics or require a richer intermediate treatment.

This document is that referenced design. Once this package is accepted, it resolves that provider-normalization question without changing the trust/auth/polling/reconciliation boundary already fixed by the provider contract.

The rule is intentionally **not** “copy every Zabbix field 1:1”. Provider evidence terminates at the adapter and is mapped into platform-owned semantics.

## Authority hierarchy

```text
Zabbix authenticated provider read
  -> bounded/validated provider entity
  -> this provider normalization profile
  -> Monitoring canonical resource/problem/metric/health contracts
```

Zabbix fields never select tenant, current authorization, placement, canonical platform identity or Alerting/ITSM lifecycle merely because the provider supplied them.

## Problem identity

Zabbix problem-class `eventid` remains a provider-native external reference scoped by:

```text
tenant_id
monitoring_source_id
provider_profile = zabbix
zabbix_instance_generation
```

The adapter maps that scoped external identity to a canonical `problem_id`.

The same numeric `eventid` in another tenant/source/generation is unrelated. Cross-generation equality is never inferred from matching event IDs.

## Problem lifecycle

Canonical Monitoring problem state is:

```text
active
resolved
```

Zabbix current `problem.get` evidence may establish/confirm active problems. Resolution/absence is accepted only under the provider contract's complete-snapshot/object-specific reconciliation rules. Missing from an incomplete/visibility-degraded query never means resolved.

Where `event.get` or another accepted Zabbix read provides explicit recovery/closure evidence, the adapter binds that evidence to the same scoped provider event identity before transitioning the canonical problem.

A problem transition and its required audit/current-state transition signal intent follow the Monitoring/ADR-008 atomicity contract.

## Severity normalization

JLMIRROR uses the provider-neutral Monitoring `severity_class`:

```text
unknown
informational
warning
degraded
critical
```

Zabbix maps as follows:

| Zabbix severity | Canonical `severity_class` | Health effect when current |
|---|---|---|
| Not classified | `unknown` | cannot prove `healthy`; health remains/enters `unknown` unless stronger evidence exists |
| Information | `informational` | no degradation by itself |
| Warning | `warning` | at least `degraded` |
| Average | `degraded` | at least `degraded` |
| High | `critical` | `unhealthy` |
| Disaster | `critical` | `unhealthy` |

The many-to-one mapping is intentional. The provider-native severity may be retained as bounded external diagnostic evidence under authorization/data-classification rules, so the platform does not need to make the provider scale canonical just to preserve provenance.

A future change to this mapping is a Monitoring compatibility change because it can alter health/alert-input semantics even if the JSON shape is unchanged.

## Acknowledgement field

Zabbix acknowledgement/acknowledged status is **provider metadata only**.

It SHALL NOT:

- acknowledge or resolve a JLMIRROR Monitoring problem;
- acknowledge, close or suppress a JLMIRROR Alert;
- acknowledge/resolve an ITSM incident/ticket;
- grant authorization or change tenant/resource scope;
- suppress required synchronization/reconciliation.

If exposed to an authorized operator, it is serialized under a bounded provider-metadata profile with an explicit provider namespace/meaning. It is never presented as a generic `acknowledged=true` platform field whose ownership is ambiguous.

A later Product feature may define an explicit synchronization/write-back workflow between provider acknowledgement and a JLMIRROR-owned concept, but that requires a separate Product/domain contract, authority model, ambiguity/idempotency semantics and provider write permission. This profile does not create it.

## Tags and labels

Zabbix tags are untrusted provider-controlled strings and may be retained only as bounded provider metadata/evidence.

They SHALL NOT become:

- tenant selector;
- authorization/resource-scope authority;
- physical routing authority;
- canonical resource identity;
- automatic Alerting/ITSM policy without a separately accepted mapping contract;
- unrestricted observability labels that create secret/data leakage or cardinality amplification.

Normalization must enforce finite tag count, key/value length, canonical string handling and safe output encoding under the selected provider numeric profile. Exact production counts/lengths remain evidence-driven C3/provider limits; “OPEN” never means unbounded.

If a future domain promotes a provider tag into a platform label, the mapping uses a versioned allowlisted namespace and explicit semantics. Arbitrary tags do not automatically enter that namespace.

## Trigger/problem text

Provider problem/trigger names/descriptions are untrusted external text. They may populate canonical problem `summary`/bounded diagnostic metadata only after:

- accepted character/string canonicalization;
- size limits;
- output escaping;
- logging/redaction policy;
- rejection/quarantine of structurally invalid values where required.

Provider text is data, never HTML/script/template authority.

## Resource association

A Zabbix problem references canonical Monitoring resources through the already accepted Zabbix host/trigger/event mapping. A provider host/trigger ID alone is insufficient; the adapter resolves the scoped external mapping under the same tenant/source/source-generation authority.

If a problem references an object that cannot be mapped safely, the adapter records a bounded unresolved/reconciliation condition rather than fabricating a cross-resource association.

## Health projection contribution

This profile supplies problem severity inputs to the Monitoring health rules; it does not make Zabbix severity itself the health enum.

Current trusted problem evidence contributes:

```text
critical              -> unhealthy
warning/degraded      -> degraded
informational only    -> no degradation by itself
unknown active        -> cannot prove healthy
no active health-affecting problem + current complete evidence -> healthy
```

If source evidence is stale/incomplete/reconciliation-required/unavailable, the health response preserves that `evidence_state`. A last-known class cannot masquerade as freshly proven health.

## Metric value normalization

Zabbix item/history value types map into the Monitoring canonical value kinds without exposing Zabbix table/type IDs as API semantics:

| Zabbix logical value class | Monitoring `value_kind` |
|---|---|
| float/numeric | `number` |
| unsigned integer | `integer` |
| character/string | `string` |
| text | `text` |
| log | `log` |

A provider value that cannot be represented losslessly under the accepted canonical representation is rejected/quarantined or handled by a separately accepted extension; it is not silently coerced into a misleading type.

Boolean Monitoring metrics, when a domain/provider mapping explicitly declares a boolean semantic, may normalize from a provider integer/string representation only through that metric-definition mapping. Zabbix integer `0/1` is not globally assumed to be boolean.

## External metadata representation

Any retained Zabbix-specific evidence uses an explicit provider namespace/profile such as conceptually:

```json
{
  "provider_profile": "zabbix",
  "native_severity": "High",
  "acknowledged": true,
  "tags": [{"key": "...", "value": "..."}]
}
```

This is illustrative logical shape, not permission to return all provider fields. The API contract decides whether a specific caller may receive provider metadata. Raw provider payloads are not returned as a compatibility escape hatch.

## Security / privacy / abuse

- provider tags/text may contain customer-sensitive data and inherit classification/redaction rules;
- provider metadata never contains API tokens/credentials;
- tags/labels are not copied into metrics/log labels without cardinality/security policy;
- provider strings are safe-encoded before browser/UI presentation;
- malformed/oversized provider metadata cannot consume unbounded parser/storage/response capacity;
- one tenant's provider vocabulary cannot collide with another tenant's canonical mapping.

## Testing

The provider adapter conformance suite SHALL prove at least:

1. each Zabbix severity maps to exactly the canonical class above;
2. High and Disaster remain distinguishable in retained native evidence if that metadata is enabled, while both canonicalize to `critical`;
3. Not classified cannot make a current active problem produce `healthy` merely because its numeric provider severity is low;
4. Zabbix acknowledgement cannot change canonical problem state, Alerting state, ITSM state or authorization;
5. arbitrary provider tags cannot select tenant, resource permission, placement or policy;
6. oversized/high-cardinality tags are bounded/rejected according to the selected limits;
7. provider text is escaped/treated as data, not executable markup;
8. provider event/host/trigger IDs from another source generation cannot attach to the current canonical problem/resource mapping;
9. missing `problem.get` data under incomplete/visibility-degraded polling cannot resolve a problem;
10. source evidence staleness is preserved in health output rather than hidden by last-known severity;
11. numeric/string/text/log metric values map to the canonical value kinds without lossy silent coercion;
12. no retained provider metadata leaks credentials or unrestricted raw payloads into logs/traces/API errors.

## Remaining OPENs

This profile closes the **semantic mapping** question. It intentionally leaves evidence-driven implementation numerics open:

- maximum provider tag count/key/value length;
- maximum provider summary/text size after parse/normalization;
- provider paging/polling/history/backfill limits;
- storage/retention policy for optional provider metadata;
- concrete secret-manager/KMS mechanism;
- production observability cardinality limits.

Those decisions may tune bounds but cannot promote Zabbix acknowledgement/tags/severity/native IDs into platform authority.
