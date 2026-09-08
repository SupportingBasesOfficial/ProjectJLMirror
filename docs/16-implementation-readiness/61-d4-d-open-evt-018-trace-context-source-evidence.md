# D4-D OPEN-EVT-018 — Trace Context Source Evidence

## Purpose

This source-evidence slice proves the final D4-D evidence axis `trace_context_observability_only_validation_and_redaction` without granting ledger credit, selecting a D4-D candidate, or changing any implementation/production authority.

Canonical source base: `main@98fb99cc04fcf42e795596f68939149463645799`.

## Evidence boundary

The source run must prove that trace context is an observability-only facility. It must never become authority for tenant identity or authorization, idempotency, ordering, canonical message identity, delivery semantics, or business-effect eligibility.

The proof set covers:

- runtime type guards and bounded canonical validation of `traceparent`, `tracestate`, and trace attributes;
- a selected canonical `tracestate` ingress profile with bounded length, at most 32 members, valid member grammar, and duplicate-key rejection;
- strict rejection of malformed, orphaned, or non-string trace metadata by the trace normalizer rather than accidental runtime exceptions;
- isolation of invalid observability metadata from business processing: the processing boundary discards invalid trace context and continues with an empty observation context without changing the business envelope or delivery semantics;
- deny-by-default propagated attributes: only explicitly allowlisted semantic fields with bounded, enumerated values may cross the boundary;
- explicit propagation context for every propagated attribute, binding `source`, `trust_level`, `classification`, `hop_scope`, and whether the field may leave JLMIRROR;
- prevention of source impersonation, untrusted/external propagation, protected-classification propagation, invalid hop scope, and unauthorized egress;
- rejection of unknown attributes and of credential/protected content smuggled under otherwise benign allowlisted field names;
- exclusion of secrets, credentials, authorization tokens, cookies, private keys and other non-allowlisted protected baggage from propagated telemetry context;
- tenant scoping of accepted trace identifiers before they are exposed as observable/exportable context: the same raw inbound trace ID is deterministically transformed per tenant, preventing a backend or exporter from joining tenants by the raw propagated trace ID;
- authenticated tenant-scope proof for repeated internal async hops: byte equality or a short tenant-derived prefix is never accepted as proof that a trace is already scoped; only a verifier-bound HMAC attestation over the exact tenant and exact scoped `traceparent` can preserve the scoped identifier on a later hop in that tenant;
- proof issuance is inseparable from scoping: the authority exposes only a `scope_and_issue` operation that first derives the tenant-scoped trace and then attests that exact derived `traceparent`; there is no public API that signs caller-supplied traceparent bytes as already scoped;
- proof-bound same-tenant idempotence: a valid attestation preserves the exact scoped trace across repeated hops in the attested tenant, while the same valid attestation entering a different tenant boundary causes a new tenant re-scope before export;
- raw replay and forged-proof resistance: already-scoped bytes presented without valid scope authority are treated as untrusted ingress and scoped again, and a proof issued under a different authority is rejected without changing business or delivery semantics;
- explicit falsification of the prior short-marker weakness, including the known `tenant-27417` / `tenant-33720` 32-bit marker collision: no prefix collision can bypass re-scoping because prefix inspection is no longer an authority mechanism;
- validated `tracestate` is intentionally discarded before observable/exportable context is produced, preventing attacker-controlled vendor state or high-cardinality correlators from becoming a cross-tenant join channel;
- cross-tenant correlation isolation even when the same valid inbound trace identifier and `tracestate` are copied between tenants;
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
