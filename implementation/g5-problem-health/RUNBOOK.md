# G5 Problem + Health — Runbook

## Slice

`g5.problem-health@1`

## Runtime entrypoint

```text
python tools/g5/run_problem_health_runtime.py
```

The proof executes:

1. service, current-authorization, contract, cache and read-adapter tests;
2. accepted Wave 4 Problem State PostgreSQL conformance;
3. accepted Wave 4 Health Projection PostgreSQL conformance;
4. browser E2E for active/resolved Problems, canonical Health, revoked authority and cross-tenant denial;
5. bounded HTTPS container proof with read-only root filesystem, dropped capabilities, no-new-privileges and non-root user.

## Product boundary

G5 reads accepted canonical Problem and Health projections. It does not recompute lifecycle or Health in the browser/BFF.

Problems default to the active source generation and paginate by the accepted `(opened_at DESC, problem_id ASC)` order using an authorized Problem anchor.

Health defaults to the active source generation and paginates by canonical resource ID. Retained historical class/state remains visible only with non-current generation/evidence semantics.

## Bounded proof profile

The non-production proof profile accepts at most 500 rows per request and a finite serialized response budget. These are validation/runtime safety bounds and do not establish production capacity authority.

## Failure behavior

- missing browser session -> 401;
- current authorization denial/revoked/cross-tenant -> 403;
- invalid filters/cursor/limit -> 400;
- unknown canonical Problem/Health resource -> 404;
- bounded read/runtime failure -> 503.

## Merge evidence

Merge readiness requires exact-head runtime success, trusted G5 scope attestation/readiness, zero unresolved material findings, and separate owner merge authorization.
