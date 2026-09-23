# G3 Resource Inventory — Runbook

## Slice

`g3.resource-inventory@1`

## Runtime entrypoint

```text
python tools/g3/run_resource_inventory_runtime.py
```

The proof executes:

1. G3 unit, authorization and contract tests;
2. the accepted Wave 4 host-inventory PostgreSQL conformance;
3. browser E2E for current list, canonical detail, revoked authority and cross-tenant denial;
4. bounded container proof with HTTPS, read-only root filesystem, dropped capabilities, no-new-privileges and non-root user.

## Product boundary

The G3 application reads the accepted canonical Monitoring resource projection under tenant RLS. It does not create a new resource store, mutate canonical Monitoring state, call the provider synchronously, infer device class, or expose later product gates.

Current collections return active-generation resources only. Direct detail lookup may return retained historical-generation evidence and labels it explicitly historical.

Provider-native host identity is never platform identity. It appears only as a bounded external reference on the detail surface.

## Failure behavior

- missing browser session -> 401;
- current authorization denial / revoked / cross-tenant -> 403;
- unknown canonical resource -> 404;
- bounded read/runtime failure -> 503;
- historical resource in current collection -> fail closed.

## Merge evidence

A later merge requires exact-head runtime success, trusted G3 scope attestation/readiness, zero unresolved material findings, and separate owner merge authorization.
