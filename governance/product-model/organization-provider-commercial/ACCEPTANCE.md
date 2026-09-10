# Organization / Provider / Commercial Product Model — Acceptance

**Status:** accepted  
**Decision:** `organization-provider-commercial-model@1`  
**Reviewed source HEAD:** `ba2817a7586ed43b18eb72a139f1eba8ffeadfa0`  
**Canonical predecessor/base:** `8e2265a4ee2810ea701166228e8f44ad3bc0d894`  
**Accepted squash:** `8c9eb94ebe76a56db85dd1ecbd3e0f8569edfb62`  
**Decision record:** `adr/ADR-022-organization-provider-commercial-operating-model.md`

## Acceptance semantics

The product model authored and reviewed in PR #125 is separately accepted as the canonical successor product/architecture decision for organization identity, tenant isolation, delegated MSP/service-provider authority, provider-instance operation, provider-scope-to-tenant mapping, commercial attribution and Platform Owner Organization 360 traceability.

The source-time contract file `docs/03-domains/organization-operating-model-contract.md` intentionally retains its authored `proposed-for-separate-acceptance` header as historical source evidence. This acceptance overlay, `STATE.md`, `DECISION_MANIFEST.json` and ADR-022 record the later acceptance event rather than rewriting the earlier source-time state.

## Accepted boundaries

Acceptance does not grant:

- runtime implementation authority;
- Zabbix validation-worker authority;
- provider-ingestion authority;
- frontend/navigation authority;
- provider write-back;
- production deployment;
- exact pricing, quota or production-capacity numerics.

Historical D2/D3/D4/Wave 4 source-time authority remains unchanged.
