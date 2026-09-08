# D4-D OPEN-EVT-018 — Trace Context Source Evidence

## Purpose

This source-evidence slice proves the final D4-D evidence axis `trace_context_observability_only_validation_and_redaction` without granting ledger credit, selecting a D4-D candidate, or changing any implementation/production authority.

Canonical source base: `main@98fb99cc04fcf42e795596f68939149463645799`.

## Evidence boundary

The source run must prove that trace context is an observability-only facility. It must never become authority for tenant identity or authorization, idempotency, ordering, canonical message identity, delivery semantics, or business-effect eligibility.

The proof set covers:

- runtime type guards and bounded canonical validation of `traceparent`, `tracestate`, and trace attributes;
- a selected canonical `tracestate` profile with bounded length, at most 32 members, valid member grammar, and duplicate-key rejection;
- strict rejection of malformed, orphaned, or non-string trace metadata by the trace normalizer rather than accidental runtime exceptions;
- isolation of invalid observability metadata from business processing: the processing boundary discards invalid trace context and continues with an empty observation context without changing the business envelope or delivery semantics;
- deny-by-default propagated attributes: only explicitly allowlisted semantic fields with bounded, enumerated values may cross the boundary;
- explicit propagation context for every propagated attribute, binding `source`, `trust_level`, `classification`, `hop_scope`, and whether the field may leave JLMIRROR;
- prevention of source impersonation, untrusted/external propagation, protected-classification propagation, invalid hop scope, and unauthorized egress;
- rejection of unknown attributes and of credential/protected content smuggled under otherwise benign allowlisted field names;
- exclusion of secrets, credentials, authorization tokens, cookies, private keys and other non-allowlisted protected baggage from propagated telemetry context;
- cross-tenant correlation isolation even when trace identifiers match;
- identical business identity, business effect, and delivery semantics with valid, missing, changed, or invalid trace context;
- explicit separation from tenant, message, idempotency, ordering, delivery, and business-effect authorities.

The source manifest identity envelope is immutable and validated exactly: `schema_version=1`, `gate_id=D4`, `track_id=D4-D`, `source_decision=OPEN-EVT-018`, `evidence_id=trace_context_observability_only_validation_and_redaction`, `mode=source_evidence_only`, and `source_base=98fb99cc04fcf42e795596f68939149463645799`.

## Source-time state

This source evidence is intentionally non-promoting, and the manifest snapshot is validated as an exact authority state rather than only checking the D4-D/D4-wide counters:

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
