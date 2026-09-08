# D4-D OPEN-EVT-018 — Trace Context Source Evidence

## Purpose

This source-evidence slice proves the final D4-D evidence axis `trace_context_observability_only_validation_and_redaction` without granting ledger credit, selecting a D4-D candidate, or changing any implementation/production authority.

Canonical source base: `main@98fb99cc04fcf42e795596f68939149463645799`.

## Evidence boundary

The source run must prove that trace context is an observability-only facility. It must never become authority for tenant identity or authorization, idempotency, ordering, canonical message identity, delivery semantics, or business-effect eligibility.

The proof set covers:

- bounded canonical validation of `traceparent`, `tracestate`, and trace attributes;
- rejection of malformed or invalid trace identifiers;
- bounded trace metadata to prevent unbounded observability input;
- policy redaction of sensitive trace attributes;
- preservation of non-sensitive correlation metadata;
- cross-tenant correlation isolation even when trace identifiers match;
- identical business identity/effect with valid, missing, or changed trace context;
- explicit separation from tenant, message, idempotency, and ordering authorities.

## Source-time state

This source evidence is intentionally non-promoting:

- D4-D remains `4/5` and unselected;
- D4-wide remains `25/26`;
- `ledger_credit=[]`;
- `current_run_auto_credit=false`;
- D4-D candidate remains `null/not_selected`;
- selection authority remains `not_granted`;
- D4 remains `scoped`;
- D4 transport remains `selected_not_granted`;
- canonical Product/Wave4 implementation authority remains `not_granted`;
- production authority remains `none`;
- C3 numeric/topology authority remains `not_selected`.

## Promotion separation

A successful source run only produces immutable reviewed provenance for the OPEN-EVT-018 evidence. Any transition from D4-D `4/5` to `5/5` and D4-wide `25/26` to `26/26` requires a separate ledger-promotion PR with independent exact-head CI, review, and explicit merge authorization.

Even after `5/5` / `26/26`, candidate selection, D4 acceptance, Product/Wave4 authority, production authority, and C3 numeric/topology authority remain separate gates and must not be inferred or granted implicitly.
