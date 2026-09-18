# G4 Metrics — Runbook

## Slice

`g4.metrics@1`

## Runtime entrypoint

```text
python tools/g4/run_metrics_runtime.py
```

The proof executes:

1. G4 service, authorization, contract, cache and PostgreSQL-read-adapter tests;
2. accepted Wave 4 metric-definition PostgreSQL conformance;
3. accepted Wave 4 metric-current-state PostgreSQL conformance;
4. accepted Wave 4 metric-history PostgreSQL conformance;
5. browser E2E for definitions/current, bounded history, revoked authority and cross-tenant denial;
6. bounded container proof with HTTPS, read-only root filesystem, dropped capabilities, no-new-privileges and non-root user.

## Product boundary

G4 reads accepted canonical metric definitions, current state and historical observations. It does not create or mutate canonical Monitoring state, call the provider from the browser/BFF path, infer Health/Problem truth, or union generations.

Current metric values are read from the dedicated current-state projection, never reconstructed from history.

History requires exactly one canonical metric definition plus a finite explicit UTC window. Completeness comes from accepted history coverage/checkpoint evidence. Returned rows alone are never completeness proof.

## Bounded proof profile

The non-production G4 proof profile accepts:

- at most 500 rows per collection/history request;
- history windows up to 24 hours;
- canonical values no larger than the accepted storage bound already enforced by the Wave 4 substrate.

These are proof/runtime safety bounds and do not grant production C3 authority.

## Failure behavior

- missing browser session -> 401;
- current authorization denial/revoked/cross-tenant -> 403;
- missing required resource/metric/window input -> 400;
- unknown canonical metric -> 404;
- bounded read/runtime failure -> 503.

## Merge evidence

A later merge requires exact-head runtime success, trusted G4 scope attestation/readiness, zero unresolved material findings, and separate owner merge authorization.
