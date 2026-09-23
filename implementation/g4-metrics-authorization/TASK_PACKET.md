# G4 Metrics — AI Task Packet

SLICE: `g4.metrics@1`  
GOAL: An authorized tenant user can open one canonical resource, list its canonical metric definitions, see current metric values with truthful freshness/evidence semantics, and inspect bounded history through the protected JLMirror shell.  
BASE SHA: supplied by the later implementation PR and MUST equal the exact current default-branch base.  
AUTHORITY: this package plus accepted Wave 4 metric definitions/current/history and Monitoring API/domain contracts.

## STOP CONDITIONS

STOP and request successor authorization if implementation requires:

- modifying `src/jlmirror_monitoring/**`, `sql/wave4/**`, G1/G2/G3 implementation namespaces or accepted shared contracts;
- adding another canonical metric/current/history store;
- treating Zabbix `itemid` as JLMirror metric identity;
- direct browser/BFF provider calls or `history.get` passthrough;
- unbounded/all-history queries or silent cross-generation unions;
- deriving Health/Problem/Alerting truth from metric values;
- provider write-back;
- production behavior.

## ALLOWED PATHS

```text
apps/g4-metrics/
contracts/g4-metrics/
implementation/g4-metrics/
tests/g4/
tools/g4/
.github/workflows/g4-metrics-runtime.yml
```

Everything else is read-only unless successor authority says otherwise.

## IMPLEMENTATION CLAIM

```json
{
  "schema_version": 1,
  "authorization_id": "g4.metrics@1",
  "slice_id": "g4.metrics@1"
}
```

Path: `implementation/g4-metrics/IMPLEMENTATION_CLAIM.json`  
Branch prefix: `impl/g4-metrics`  
Required label: `jlmirror-slice:g4-metrics`

## DOMAIN / DATA

Reuse canonical Wave 4 metric substrate.

```text
metric_definition_id = canonical identity
zabbix itemid = scoped provider evidence only
metric definition != current state
current state != history
missing != zero
stale/incomplete != current
metric value != health
active source generation = default current meaning
history requires exact metric_definition_id + finite from/to
history completeness is explicit evidence
cross-generation history union = forbidden
```

No G4-owned canonical persistence.

## API / BFF

Every request:

```text
browser -> canonical G1 session -> current tenant admission
 -> monitoring.metric.read
 -> canonical Monitoring metric read
 -> bounded response
```

Resource association is canonical through `monitoring_resource_id`; ID possession never grants authority.

Use the accepted metric-definition/current/history endpoints and filters. Do not invent a provider passthrough or aggregate that collapses current/history authority.

## FRONTEND

Required states:

- loading;
- empty;
- current;
- stale;
- incomplete;
- reconciliation required;
- unavailable;
- forbidden;
- visibly historical generation;
- history complete/incomplete/gap/reconciliation;
- bounded safe rendering for string/text/log values.

Never display a canonical Health/Problem conclusion inferred from metrics under this gate.

## TESTS

At minimum:

1. closed metric definition/current/history response contracts;
2. current authorization on every page/read;
3. cross-tenant and revoked denial;
4. canonical metric ID vs Zabbix itemid separation;
5. active-generation default;
6. historical-generation non-current semantics;
7. missing value not rendered as zero;
8. stale/incomplete/unavailable truthfulness;
9. bounded value serialization by value kind;
10. finite history window requirement;
11. no all-history fallback;
12. no implicit cross-generation union;
13. completeness/gap truthfulness;
14. accepted Wave 4 metric substrate reuse proof;
15. browser E2E resource -> metric current -> bounded history;
16. runtime/container proof;
17. adversarial scope proof rejecting G5+, provider passthrough and parallel Monitoring authority.

## DONE

```text
accepted provider fixture / Wave4 metric substrate
 -> canonical metric_definition
 -> canonical metric_current_state
 -> bounded metric_observation history
 -> current tenant + monitoring.metric.read
 -> protected BFF/API
 -> resource metrics UI
```

Success requires exact-head CI green, trusted scope/readiness evidence, zero unresolved material findings and separate explicit owner merge authorization.

```text
G4 != G5 Problem/Health
METRICS != HEALTH
METRICS != PROBLEMS
G4 != new Monitoring persistence
G4 != production authority
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
