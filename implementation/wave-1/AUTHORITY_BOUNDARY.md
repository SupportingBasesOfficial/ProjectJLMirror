# Wave 1 — Authority Boundary

Wave 1 implements only the identity and authority skeleton authorized by the accepted Implementation Readiness sequencing.

## Included slices

- `impl.identity-bff@1`
- `impl.control-plane@1`
- minimal `impl.platform-runtime@1`

## Included authority primitives

- browser session/authentication transaction primitives;
- bounded canonical URL-safe browser session capability parsing before session-store lookup;
- principal-bound authentication-strength evidence and privileged step-up predicates;
- machine principal assertion/replay authority ports;
- typed workload identity parsing and service-authentication boundary;
- trusted `TenantContext` construction inputs;
- current authorization and placement admission predicates;
- revision-bound/atomic logical final-admission authority for protected operations;
- current executing-runtime authority binding for every protected final admission, with exact Control Plane binding for cross-tenant privileged work;
- runtime/configuration/workload credential/network-policy generation separation;
- classified finite-scalar configuration plus typed secret-reference boundaries;
- monotonic PostgreSQL fence contract and stale-actor rejection;
- current fence authority resolution before portable fence-token admission, with same-transaction predicate+effect required where fence/effect are co-resident;
- persisted fence-state revalidation before historical state can remain authority-eligible;
- exact-base Git delta scope guard that rejects Product/domain/Wave 2/normative-doc changes;
- runtime profile bindings required by the three Wave 1 slices.

Trusted C2 adapters provide evidence only. Malformed, unbound or non-canonical adapter output fails closed before it can create session, replay, tenant, workload or protected-effect authority. Caller/request-adjacent tenant, destination and authority-generation identifiers are canonicalized before C2 placement/configuration/machine verification ports are invoked.

The browser session cookie is an opaque capability, not an arbitrary string namespace. Wave 1 accepts only the bounded URL-safe capability grammar before digest/store lookup; Unicode, control characters, whitespace, non-URL-safe encodings and oversized handles cannot make the session store the parser or resource-amplification boundary. The raw capability remains repr/log-redacted.

Browser authorization transaction authority is time-bounded on both sides: a consumed transaction is usable only while `created_at <= now < expires_at`. Clock rollback/not-yet-current state cannot reach the IdP adapter as an authentication attempt.

Privileged or policy-sensitive human admission does not freeze Security authority when MFA/step-up first passes. Serial Security checks may reject early, but they are narrowing evidence only. Final protected-operation admission requires the revision-bound final-admission authority to re-establish the applicable authentication-strength policy/evidence with current Security authority. Policy hardening, stale assurance or loss of proof during the decision window fails closed; an earlier step-up result is not durable authority.

Cross-tenant privileged operations remain distinct platform operations. A valid platform-admin principal, permission, authentication-strength result or caller-selected `RuntimeBinding` cannot route such an operation through the ordinary `runtime.api@1` application boundary. Serial runtime checks resolve trusted current executing-runtime evidence and may reject early, but they are not the final grant. The final-admission authority must re-establish and revision-bind the exact accepted `runtime.control-plane@1` executing runtime using authority-owned currentness/time. A typed `CONTROL_PLANE` constant and caller-supplied `now` are expected/narrowing inputs only, never final execution authority.

Tenant/resource admission has the same executing-runtime requirement. The `runtime_generation` carried by `TenantContext` is trusted destination placement/runtime authority; it is **not** proof of the process/runtime generation actually executing the authorization decision. Every final protected-operation snapshot therefore also binds a current executing-runtime authority revision, exact executing runtime profile and executing runtime generation. For ordinary tenant/resource API work that profile must equal the accepted `runtime.api@1` boundary; for cross-tenant privileged work it must equal `runtime.control-plane@1`. The final-admission implementation, not caller input or placement context, owns resolution of that current executing-runtime evidence.

Owning membership/permission/resource authorization is not durable merely because an `AuthorizationDecision` said `current=True`. Wave 1 may evaluate principal, placement/runtime/fence, authentication-strength and owning authorization serially as fail-fast narrowing gates, but no ordering of those checks can create final authority: whichever serial check is last would otherwise reopen a TOCTOU window for the preceding authorities.

Final protected-operation admission therefore requires one `FinalAdmissionAuthorityPort` result whose implementation performs one atomic or revision-bound logical current-authority decision using authority-owned currentness/time. The returned `FinalAdmissionEvidence` binds at minimum the final admission revision, owning authorization policy revision, principal authority revision, exact principal/session or credential generation, exact action, exact executing-runtime authority revision/profile/generation, exact `resource_scope` semantics, and every applicable authority dimension:

- for tenant-scoped work: tenant/cell placement revision, placement/runtime/configuration/workload-credential/network-policy generations, environment/isolation binding, fence scope and fence epoch;
- for resource-scoped work: a non-null exact canonical resource scope consumed by the owning authorization decision; evidence for one resource cannot be reused for another resource even when the action is identical;
- for platform/tenant scope: `resource_scope` is absent; attaching resource authority to a non-resource declaration is rejected rather than silently ignored;
- for privileged/policy-sensitive humans: current authentication-strength/Security policy revision;
- for every protected operation: current executing runtime authority revision, exact expected runtime profile and exact executing runtime generation;
- for cross-tenant privileged work specifically: the executing runtime profile is exactly `runtime.control-plane@1`.

Missing, malformed, non-current, denied or mismatched final evidence fails closed. `ScopeClass.RESOURCE` without a canonical `resource_scope` is invalid before authorization begins, so a resource operation can never degrade into action-only authority. The finalizer receives no caller-supplied `now`; a request timestamp cannot keep an expired runtime/session/policy current during a slow decision. Earlier serial checks remain useful for narrowing and diagnostics, but **serial currentness checks are not final admission authority**. The final decision remains an admission result, not durable effect authority; effectful paths still consume the applicable current/fenced/atomic authority at their effect boundary.

Fence scope/epoch/generation equality is necessary but not sufficient for a protected effect. A typed `FenceRecord` supplied by a caller is not currentness evidence. The portable Wave 1 predicate resolves the current record from the owning fence authority and requires its state to be exactly `active` before comparing scope, epoch and generation. For co-resident PostgreSQL effects, even that preflight result is insufficient: the current fence predicate and protected mutation must execute in the same database transaction. `quarantined`, `retired` or any other syntactically valid state cannot admit a protected effect and cannot use the ordinary successor compare-and-advance path to resurrect effect eligibility. Recovery/state-transition authority remains separately governed by the accepted Phase 13/15 lifecycle and recovery predicates.

An already-present `platform.authority_fences` object is not automatically conforming. The follow-on revalidation migration applies the canonical identifier/positive-epoch contract to persisted rows and validates historical state without rewriting or deleting authority data merely to make validation pass. Direct ACL cleanliness is not enough: before C2 role mapping, the migration-owner role must also have no direct or transitive `pg_auth_members` path by which another role can assume or inherit owner authority. This conservative check does not claim to remove PostgreSQL cluster-superuser power; it closes owner-role membership laundering inside the modeled role boundary.

## Explicitly not selected here

The following remain C2 implementation choices and are not made canonical by code presence:

- identity provider product;
- BFF/session-store product;
- CSRF mechanism/product beyond fixed Phase 09 semantics;
- workload-identity issuer/attestation backend;
- service mesh;
- secret manager/KMS;
- configuration-distribution product;
- orchestrator/scheduler;
- ingress/load-balancer product;
- physical environment/topology mapping;
- concrete final-admission coordination/store mechanism, provided it conforms to the fixed revision-bound/atomic authority contract.

## Explicitly absent

- Product/domain endpoints not already accepted;
- customer telemetry implementation;
- provider adapters;
- realtime implementation;
- artifact delivery activation;
- Wave 2 transactional business/domain implementation;
- production topology/numerics.

## Authority laws

```text
AUTHENTICATED != AUTHORIZED
SESSION VALID != CURRENT AUTHORITY
NONCANONICAL/UNBOUNDED BROWSER SESSION HANDLE != SESSION AUTHORITY
MFA PRESENT != REQUIRED ASSURANCE CURRENT
EARLIER STEP-UP PASS != FINAL CURRENT ASSURANCE
AUTHENTICATION STRENGTH EVIDENCE != TRANSFERABLE PRINCIPAL AUTHORITY
MALFORMED ADAPTER OUTPUT != TRUSTED AUTHORITY
NONCANONICAL LOOKUP/GENERATION INPUT != C2 ADAPTER AUTHORITY
NOT-YET-CURRENT AUTH TRANSACTION != AUTHENTICATION AUTHORITY
WORKLOAD IDENTITY != TENANT AUTHORITY
NETWORK PRESENCE != TRUST
TENANT ID INPUT != TENANT CONTEXT
CALLER-SELECTED RUNTIME BINDING != EXECUTING RUNTIME AUTHORITY
DESTINATION RUNTIME GENERATION != EXECUTING RUNTIME AUTHORITY
CROSS-TENANT PLATFORM AUTHORITY != APPLICATION RUNTIME AUTHORITY
EARLIER AUTHORIZATION GRANT != FINAL CURRENT AUTHORIZATION
SERIAL CURRENTNESS CHECKS != FINAL ADMISSION AUTHORITY
CALLER-SUPPLIED NOW != FINAL CURRENTNESS CLOCK
ACTION MATCH != RESOURCE-SCOPE MATCH
RESOURCE SCOPE ABSENCE != RESOURCE AUTHORITY
FINAL ADMISSION SNAPSHOT != DURABLE EFFECT AUTHORITY
PLACEMENT CACHE HIT != GLOBAL AUTHORITY
ENVIRONMENT LABEL != AUTHORIZATION
UNCLASSIFIED/UNTYPED CONFIG != RUNTIME-ADMISSIBLE CONFIG
TYPED FENCE RECORD != CURRENT EFFECT AUTHORITY
FENCE SCOPE/EPOCH/GENERATION MATCH != EFFECT AUTHORITY WITHOUT ACTIVE STATE
NON-ACTIVE FENCE STATE != ORDINARY SUCCESSOR AUTHORITY
PREEXISTING FENCE TABLE != PERSISTED AUTHORITY CONFORMANCE
OWNER OBJECT ACL CLEAN != OWNER ROLE UNASSUMABLE
FENCE TOKEN != AMBIGUOUS EFFECT ABSENCE
SECRET REFERENCE != SECRET VALUE
IMPLEMENTATION MANIFEST != AUTHORIZED GIT DELTA BY ITSELF
WAVE 1 AUTHORIZED != WAVE 2 AUTHORIZED
```
