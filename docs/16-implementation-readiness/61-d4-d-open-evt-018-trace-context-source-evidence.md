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
- authenticated tenant-scope proof for repeated internal async hops: byte equality or a short tenant-derived prefix is never accepted as proof that a trace is already scoped; the HMAC attests the exact tenant plus the tenant-scoped trace identity, while the W3C parent/span ID may change on a legitimate child span but is tenant-scoped before observable export;
- proof issuance is inseparable from scoping: `scope_and_issue` first derives the tenant-scoped trace and only then attests the derived tenant-scoped trace ID; no public API can bless a caller-chosen raw trace ID as already scoped;
- proof-bound same-tenant continuity: a valid attestation preserves the tenant-scoped trace ID across repeated hops while each incoming child parent/span ID is transformed for the tenant before export; the same raw child parent ID therefore cannot become a cross-tenant join channel, and the same attestation crossing into another tenant boundary causes a new tenant re-scope before export;
- complete fail-closed proof parsing: malformed or non-string proof fields, including `tenant_id`, `trace_id`, and `mac_hex`, cannot escape as runtime type errors and are discarded as invalid observability metadata without changing business/delivery semantics;
- canonical tenant-scope identity validation before encoding or cryptographic work: tenant IDs are bounded and must be strictly UTF-8 encodable before tenant-scoping hashes, proof payload encoding, HMAC issuance, or verification;
- raw replay and forged-proof resistance: already-scoped bytes presented without valid scope authority are treated as untrusted ingress and scoped again, and a proof issued under a different authority is rejected without changing business or delivery semantics;
- explicit falsification of the prior short-marker weakness, including the known `tenant-27417` / `tenant-33720` 32-bit marker collision: no prefix collision can bypass re-scoping because prefix inspection is no longer an authority mechanism;
- validated `tracestate` is intentionally discarded before observable/exportable context is produced, preventing attacker-controlled vendor state or high-cardinality correlators from becoming a cross-tenant join channel;
- cross-tenant correlation isolation even when the same valid inbound trace identifier and `tracestate` are copied between tenants;
- identical business identity, business effect, and delivery semantics with valid, missing, changed, or invalid trace context;
- explicit separation from tenant, message, idempotency, ordering, delivery, and business-effect authorities.

The source manifest identity envelope is immutable and validated exactly: `schema_version=1`, `gate_id=D4`, `track_id=D4-D`, `source_decision=OPEN-EVT-018`, `evidence_id=trace_context_observability_only_validation_and_redaction`, `mode=source_evidence_only`, and `source_base=98fb99cc04fcf42e795596f68939149463645799`.

## Automatic adversarial-learning gate

Material review findings are part of the exact-head evidence lifecycle rather than advisory metadata. The deterministic assurance gate reconciles all supported PR review surfaces — top-level PR conversation comments, inline review comments, and formal reviews — and `issue_comment` events resolve the current pull-request head explicitly before checkout so a comment cannot be reconciled against an incidental default-branch revision.

A material finding is not considered internalized merely because a ledger token appears in a source file. Declared guardrails must resolve through registered mechanisms to checks that are actually executed: D4-D source guardrails resolve against the IDs returned by `run_probes()`, while falsification guardrails resolve only to named `falsify_*` functions that are invoked by the corresponding test program's `main`. Parameterized ledger identifiers are accepted only when they match concrete executed probe IDs. Omitted review surfaces, unregistered guardrail paths, fictional checks, and incidental source substrings are rejected by falsification.

This learning governance does not grant source credit or any D4 authority; it only makes remediation completeness and reusable learning prerequisites for a green exact-head gate.

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
