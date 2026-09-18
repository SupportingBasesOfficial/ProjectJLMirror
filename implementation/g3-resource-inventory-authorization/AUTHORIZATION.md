# G3 Resource Inventory — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@a0f5e436812b2ebb5334485dbf4fc4abb393befa`  
**Authorization ID:** `g3.resource-inventory@1`

## Purpose

This is the separate implementation-authorization gate for the third AI-E2E product increment. It does not implement G3. It authorizes only the bounded user path required for an already-authorized tenant user to observe canonical Monitoring resources discovered from the accepted Zabbix host-inventory substrate through protected BFF/API and browser UI.

G3 MUST reuse the accepted Wave 4 host-inventory implementation and canonical `monitoring_resource` identity model. It MUST NOT create a second inventory store, reinterpret Zabbix `hostid` as platform identity, or broaden into metrics, Problems/Health, Alerting, device classification or production authority.

## Authorization on acceptance

If this exact package is reviewed, accepted and separately merged:

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g3_resource_inventory_only
```

Authorized slice:

```text
g3.resource-inventory@1
```

Observable outcome: an authorized tenant user can list and inspect canonical monitored resources for the current active Monitoring Source generation, including bounded provenance/provider evidence, while cross-tenant, stale-generation and unauthorized access fail closed.

`merge_authorization = not_granted` remains separate.

## Dependency boundary

G3 depends on:

- canonical G1 protected identity/tenant/BFF implementation;
- canonical G2 Monitoring Source onboarding implementation;
- accepted Wave 4 host-inventory product behavior and implementation;
- accepted Monitoring domain/API contracts.

The implementation MUST consume these authorities. It MUST NOT modify or duplicate them unless a successor authorization explicitly grants that authority.

## Existing substrate to reuse

Canonical existing substrate includes at minimum:

- `src/jlmirror_monitoring/**`;
- `sql/wave4/**`;
- accepted host-inventory runtime/conformance tooling under `tools/wave4/**`;
- `implementation/wave-4-host-inventory-authorization/**`;
- accepted Monitoring domain/API/Zabbix provider contracts.

These shared paths are read-only under this authorization.

## Implementation path authority

Allowed prefixes:

- `apps/g3-resource-inventory/`;
- `contracts/g3-resource-inventory/`;
- `implementation/g3-resource-inventory/`;
- `tests/g3/`;
- `tools/g3/`.

Allowed exact path:

- `.github/workflows/g3-resource-inventory-runtime.yml`.

Required future implementation PR identity:

- branch prefix `impl/g3-resource-inventory`;
- label `jlmirror-slice:g3-resource-inventory`;
- claim file `implementation/g3-resource-inventory/IMPLEMENTATION_CLAIM.json`;
- authorization ID `g3.resource-inventory@1`;
- same repository;
- base equal to current default branch tip when trusted evidence is produced.

Path admission alone is insufficient. Executable G3 artifacts must be rejected if they introduce G4+ capability, parallel Monitoring persistence/domain truth, shared-substrate writes, provider-native authorization, automatic device classification, or production authority.

## Product behavior authorized

The later implementation may expose only the minimum G3 golden path required for:

1. current tenant admission through canonical G1;
2. current `monitoring.resource.read` authorization;
3. list of canonical Monitoring resources for the admitted tenant;
4. detail read by canonical opaque `monitoring_resource_id`;
5. current active-generation resources by default;
6. visibly historical generation semantics only where the accepted API contract permits direct historical lookup;
7. bounded provider provenance/evidence view for accepted Zabbix host evidence;
8. `resource_kind=host` exactly for this accepted host-inventory slice;
9. provider object identity kept separate from canonical identity;
10. truthful presence/currentness/evidence presentation;
11. browser E2E proving allowed, forbidden and cross-tenant paths;
12. exact runtime/container proof for G3-owned composition.

## Binding resource semantics

```text
MONITORING_RESOURCE_ID = CANONICAL_PLATFORM_IDENTITY
RESOURCE_KIND = host
PROVIDER_OBJECT_KIND = zabbix_host
ZABBIX_HOSTID != MONITORING_RESOURCE_ID
PROVIDER_NATIVE_ID != PLATFORM_IDENTITY
PROVIDER_EVIDENCE != TENANT_AUTHORITY
PROVIDER_EVIDENCE != CANONICAL_DEVICE_CLASSIFICATION
CURRENT_INVENTORY_DEFAULT = ACTIVE_SOURCE_GENERATION_ONLY
INCOMPLETE_OR_STALE_EVIDENCE != RESOURCE_ABSENCE
SCOPE_EXCLUSION != REMOVAL
HISTORICAL_GENERATION != CURRENT_OPERATIONAL_STATE
```

Removal/absence semantics remain owned by the accepted host-inventory substrate. G3 UI/BFF may project them; it may not reinterpret them.

## API/BFF authority

The protected browser path consumes the accepted Monitoring API contract.

Required stable action:

```text
monitoring.resource.read
```

Minimum logical surfaces:

```text
GET /api/v1/tenants/{tenant_id}/monitoring-resources
GET /api/v1/tenants/{tenant_id}/monitoring-resources/{monitoring_resource_id}
```

Exact endpoint spelling used by implementation MUST match the accepted Monitoring API contract. The authorization does not grant permission to invent a parallel resource API if the canonical contract differs.

Every read re-establishes current tenant placement and current authorization. URL possession, resource ID knowledge, prior session admission and provider payloads never grant authority.

## Frontend authority

Implement only the bounded G3 inventory experience:

- inventory navigation entry inside the protected shell;
- loading/empty/current/unavailable/forbidden states;
- resource list;
- resource detail;
- resource kind;
- generation state;
- bounded provenance/provider evidence;
- truthful stale/incomplete evidence presentation.

The UI MUST NOT classify a host as server/switch/router/firewall/VM/etc. unless a later separately governed classification contract grants that authority.

## Explicit non-authority

This gate does not authorize:

- new canonical Monitoring resource persistence;
- modification of accepted host-inventory ingestion semantics;
- provider write-back;
- metric definitions/current values/history;
- G4 Metrics product surface;
- Problem or Health product surface;
- Monitoring→Alerting changes;
- Alert creation/policy;
- source replacement/cutover;
- canonical device taxonomy/classification;
- topology/business-service inference;
- ITSM, Automation, AIOps, FinOps or Commercial behavior;
- concrete secret-manager or egress-transport selection;
- production deployment/C3 numerics;
- raw unrestricted provider payload persistence/exposure;
- shared Monitoring/G1/G2 substrate modification without successor authorization.

## Required proof before merge of the later implementation

- complete diff inside the canonical G3 allowlist;
- semantic-scope guard rejects G4+ and parallel Monitoring authority;
- current-authorization and cross-tenant tests;
- accepted Wave 4 host-inventory reuse proof;
- resource list/detail contract tests;
- browser E2E from protected shell to inventory list/detail;
- stale/incomplete/historical truthfulness tests;
- runtime/container proof;
- exact-head CI green;
- trusted scope attestation/readiness evidence;
- panoramic/adversarial review with zero unresolved material findings;
- separate explicit owner merge authorization.

```text
G2_AUTHORIZED != G3_AUTHORIZED
G3_AUTHORIZED != G4_AUTHORIZED
IMPLEMENTED != PRODUCTION_READY
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
