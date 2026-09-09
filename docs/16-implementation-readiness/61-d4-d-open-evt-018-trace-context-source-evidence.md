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
- keyed tenant pseudonymization of accepted trace and parent identifiers before observable/exportable use: tenant-scoped identifiers are derived with HMAC under an authority-held secret, so unequal tenant representations are not publicly derivable from another tenant's exported identifier plus a known tenant ID;
- fail-closed handling when no tenant-scope authority exists: an exportable trace identifier is discarded as optional observability context rather than falling back to an unkeyed/public transform, while the business envelope and delivery semantics remain unchanged;
- authenticated tenant-scope proof for repeated internal async hops: byte equality or a tenant-derived representation is never accepted as proof that a trace is already scoped; the HMAC binds the exact tenant, tenant-scoped semantic trace ID, and the latest governed exported parent/span ID;
- the proof-bound parent ID is a representation companion only, never tenant/business authority: when the incoming parent equals the authenticated last exported parent it is preserved exactly, while a legitimately new child parent is treated as fresh representation, tenant-scoped once, and followed by a refreshed proof;
- exact-context same-tenant forwarding is idempotent at the exported representation: forwarding the previous trace context with its valid proof does not produce `T(T(parent))`, so the receiver's parent remains linkable to the preceding exported span;
- legitimate child-span evolution remains supported: the semantic trace ID remains stable, a new raw child parent is tenant-scoped before export, and forwarding that already-governed child export with its refreshed proof preserves it without a second transformation;
- proof issuance is inseparable from keyed scoping: `scope_and_issue` first derives the tenant-scoped trace and parent representation under the authority key and only then attests that exported result; no public API can bless caller-chosen raw identifiers as already scoped;
- a proof crossing into another tenant cannot preserve the previous tenant's exported representation; the context is re-scoped under the secret authority for the new tenant and a new proof is issued;
- complete fail-closed proof parsing: malformed or non-string proof fields, including `tenant_id`, `trace_id`, `parent_id`, and `mac_hex`, cannot escape as runtime type errors and are discarded as invalid observability metadata without changing business/delivery semantics;
- canonical tenant-scope identity validation before encoding or cryptographic work: tenant IDs are bounded and must be strictly UTF-8 encodable before tenant-scoping HMAC input construction, proof payload encoding, HMAC issuance, or verification;
- raw replay and forged-proof resistance: already-scoped bytes presented without valid scope authority are treated as untrusted ingress and keyed-scoped again, and a proof issued under a different authority is rejected without changing business or delivery semantics;
- explicit falsification of the prior short-marker weakness, including the known `tenant-27417` / `tenant-33720` 32-bit marker collision: no prefix collision can bypass re-scoping because prefix inspection is no longer an authority mechanism;
- validated `tracestate` is intentionally discarded before observable/exportable context is produced, preventing attacker-controlled vendor state or high-cardinality correlators from becoming a cross-tenant join channel;
- cross-tenant correlation isolation even when the same valid inbound trace identifier, parent identifier, and `tracestate` are copied between tenants;
- identical business identity, business effect, and delivery semantics with valid, missing, changed, or invalid trace context;
- explicit separation from tenant, message, idempotency, ordering, delivery, and business-effect authorities.

The source manifest identity envelope is immutable and validated exactly: `schema_version=1`, `gate_id=D4`, `track_id=D4-D`, `source_decision=OPEN-EVT-018`, `evidence_id=trace_context_observability_only_validation_and_redaction`, `mode=source_evidence_only`, and `source_base=98fb99cc04fcf42e795596f68939149463645799`.

## Automatic adversarial-learning gate

Material review findings are part of the exact-head evidence lifecycle rather than advisory metadata. The deterministic assurance gate reconciles all supported PR review surfaces — top-level PR conversation comments, inline review comments, and formal reviews — and `issue_comment` events resolve the current pull-request head explicitly before checkout so a comment cannot be reconciled against an incidental default-branch revision.

A material finding is not considered internalized merely because a ledger token appears in a source file. D4-D source guardrails resolve against the IDs actually returned by `run_probes()`. Falsification guardrails receive credit only when they resolve to registered `falsify_*` checks that are directly and unconditionally reachable from the corresponding CI test program's `main`, and the module itself must prove a canonical `if __name__ == "__main__": main()` entrypoint. Syntactic presence inside dead conditions, unused nested functions, after unconditional termination, or inside a never-invoked `main` is not execution evidence. Parameterized ledger identifiers are accepted only when they match concrete executed probe IDs.

Learning entries may be stored in immutable ledger shards under `governance/adversarial/learning-ledger.d/`; the validator merges the canonical ledger and all shards and still enforces globally unique entry/review identities and monotonically increasing guardrail generations per failure class.

### One-time bootstrap exception for PR #118

GitHub determines whether an `issue_comment` workflow exists from the default branch. PR #118 is itself the change introducing that trigger, so the trigger cannot retroactively protect PR #118 before merge. This is represented by an exact machine-readable bootstrap exception for review comment `3963734258`, limited to PR #118, with two compensating controls: all three review surfaces must be manually reconciled against the exact current HEAD immediately before merge eligibility, and no unresolved P0/P1 or non-green exact-head CI may remain. The exception expires as soon as the deterministic-assurance `issue_comment` trigger is present on `main` after PR #118 merges; it is not reusable by later PRs.

## Bounded review policy

Repository rigor is now coupled to an explicit stop rule rather than an unbounded reviewer loop. P0/P1 findings remain merge-blocking. P2 findings block only when they demonstrate gate incorrectness, a security/authority invariant failure, or failure of the learning enforcement itself; otherwise they become explicit follow-up work. Findings sharing a root-cause class are remediated horizontally as one batch. After the repository-owned adversarial matrix and exact-head CI are clean, the normal process permits one final external red-team round; if that round yields no new P0/P1 material finding, the PR review loop closes instead of recursively restarting on non-blocking residual hardening.

This bounded policy does not weaken tenant isolation, source non-promotion, authority separation, or exact-head evidence requirements.

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
