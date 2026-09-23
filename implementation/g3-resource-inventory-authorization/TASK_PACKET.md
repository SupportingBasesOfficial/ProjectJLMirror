# G3 Resource Inventory — AI Task Packet

SLICE: `g3.resource-inventory@1`  
GOAL: An authorized tenant user can list and inspect canonical monitored resources discovered by the accepted Zabbix host-inventory substrate through the protected JLMirror shell.  
BASE SHA: supplied by the later implementation PR and MUST equal the exact current default-branch base.  
AUTHORITY: this package plus the accepted Wave 4 host-inventory and Monitoring API/domain contracts.

## STOP CONDITIONS

STOP and request successor authorization if implementation requires:

- modifying `src/jlmirror_monitoring/**`, `sql/wave4/**`, G1/G2 implementation namespaces or accepted shared contracts;
- adding another canonical resource table/domain;
- changing host-inventory identity, presence, scope or negative-evidence semantics;
- treating Zabbix `hostid` as JLMirror identity;
- inferring server/switch/router/firewall/VM or another device class as canonical truth;
- adding metrics, Problem/Health, Alerting, source replacement/cutover or production behavior;
- provider write-back;
- unrestricted raw provider payload storage/exposure.

## ALLOWED PATHS

```text
apps/g3-resource-inventory/
contracts/g3-resource-inventory/
implementation/g3-resource-inventory/
tests/g3/
tools/g3/
.github/workflows/g3-resource-inventory-runtime.yml
```

Everything else is read-only unless successor authority says otherwise.

## IMPLEMENTATION CLAIM

```json
{
  "schema_version": 1,
  "authorization_id": "g3.resource-inventory@1",
  "slice_id": "g3.resource-inventory@1"
}
```

Path: `implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json`  
Branch prefix: `impl/g3-resource-inventory`  
Required label: `jlmirror-slice:g3-resource-inventory`

## DOMAIN / DATA

Reuse canonical Wave 4 host inventory.

```text
monitoring_resource_id = canonical identity
resource_kind = host
provider_object_kind = zabbix_host
zabbix hostid = scoped external evidence only
active source generation = default current inventory authority
historical generation != current operational inventory
incomplete/stale visibility != absence
scope exclusion != removal
```

No G3-owned canonical persistence.

## API / BFF

Every request:

```text
browser -> canonical G1 session -> current tenant admission
 -> monitoring.resource.read
 -> canonical Monitoring resource read
 -> bounded response
```

List/detail APIs MUST consume the accepted Monitoring API contract rather than invent a parallel identity or filter model.

## FRONTEND

Required states:

- loading;
- empty;
- current list;
- resource detail;
- forbidden;
- unavailable;
- stale/incomplete evidence where applicable;
- visibly historical state where canonical direct historical lookup is allowed.

Display provider provenance as evidence, never as platform authority or device classification.

## TESTS

At minimum:

1. closed list/detail contract shapes;
2. current authorization on every read;
3. cross-tenant denial;
4. canonical ID vs provider hostid separation;
5. active-generation default;
6. historical-generation truthfulness;
7. incomplete/stale evidence not rendered as removal;
8. bounded provider-evidence output;
9. accepted Wave 4 inventory reuse proof;
10. browser E2E list -> detail;
11. runtime/container proof;
12. adversarial scope proof rejecting G4+ and parallel Monitoring authority.

## DONE

```text
Zabbix fixture / accepted Wave4 inventory
 -> canonical monitoring_resource
 -> current tenant + monitoring.resource.read
 -> BFF/API list/detail
 -> protected browser inventory UI
```

Success requires exact-head CI green, scope/readiness evidence, zero unresolved material findings and separate explicit owner merge authorization.

```text
G3 != G4 metrics
G3 != canonical device classification
G3 != new Monitoring persistence
G3 != production authority
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
