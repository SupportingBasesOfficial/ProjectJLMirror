# Wave 1 Assurance Boundary

Wave 1 conformance evidence is subordinate to the accepted Product, Security, API, Reliability, Runtime, Operations and Implementation Readiness authorities.

Required exact-HEAD evidence before merge readiness:

- repository deterministic assurance remains green;
- Wave 0 contract tooling remains green;
- Wave 1 unit/adversarial tests remain green;
- Wave 1 authority validator reports no findings;
- the exact Git delta from `main@5b56ad94566b48b72a993ee8f5cf7e983127ab21` remains inside the closed Wave 1 path allowlist;
- PR scope remains only identity/control-plane/minimal-runtime authority skeleton;
- caller/request-adjacent authority identifiers fail before C2 adapter invocation when non-canonical;
- browser session capability input is bounded and canonical before session-authority lookup;
- browser auth transaction currentness is fail-closed for both not-yet-current and expired transactions;
- explicit cross-tenant privileged platform operations cannot be admitted through the ordinary application runtime boundary: a caller-selected `CONTROL_PLANE` binding is insufficient and the actual executing runtime must be proven current/active by trusted authority;
- privileged/policy-sensitive human admission does not treat an earlier MFA/step-up result as durable authority;
- owning authorization, principal currentness, TenantContext/placement/runtime/fence currentness, authentication-strength currentness and executing-runtime currentness are never made final merely by choosing a serial evaluation order;
- serial currentness checks are narrowing/fail-fast evidence only and **cannot** be returned as final protected-operation authority;
- final protected-operation admission fails closed unless a `FinalAdmissionAuthorityPort` returns a well-formed `FinalAdmissionEvidence` whose implementation re-establishes every applicable current authority as one atomic or revision-bound logical decision;
- the final-admission boundary uses authority-owned currentness/time and receives no caller/request `now` parameter;
- final tenant admission binds exact current tenant/cell placement revision plus placement/runtime/configuration/workload-credential/network-policy generations, environment/isolation, fence scope and fence epoch;
- final resource-scoped admission binds the exact canonical `resource_scope`; a final snapshot for one resource cannot admit another resource merely because the action is identical;
- final privileged-human admission binds the current authentication-strength/Security policy revision;
- final cross-tenant privileged admission binds the current executing Control Plane runtime authority revision, exact `runtime.control-plane@1` profile and exact runtime generation;
- final admission always binds principal authority revision, principal/session-or-credential generation, exact action, exact resource scope (including absence), final admission revision and owning authorization policy revision;
- any mismatch, omission, malformed evidence, denied/current=false state or final-admission authority failure is a closed denial; there is no fallback to serial checks;
- an admitted final snapshot remains an admission result only and cannot replace effect-boundary fencing/currentness/atomicity;
- fenced effect admission resolves current state from the owning fence authority; a typed/supplied fence record is not currentness proof, and co-resident PostgreSQL effects retain the same-transaction predicate requirement;
- persisted fence authority state is revalidated against canonical identifier/positive-epoch constraints rather than accepted by object presence;
- reused PostgreSQL fence objects fail closed unless the migration authority owns the schema/table/functions, no effective non-owner schema/table/function ACL survives, and no direct or transitive `pg_auth_members` path can assume/inherit the migration-owner role before separately reviewed C2 role mapping;
- no residual C2 product is silently promoted to architecture authority;
- no Product/domain endpoint family is introduced beyond accepted authority;
- review findings are resolved only after later exact-HEAD evidence;
- Native Assurance passes 1–12 are clean on the exact final HEAD.

Mandatory falsification includes:

- all serial checks green but no final-admission authority -> deny;
- malformed, unavailable, denied or non-current final-admission authority -> deny;
- principal/action/session-generation drift in final evidence -> deny;
- same action with different resource scope cannot reuse final evidence;
- tenant/cell/placement/runtime/configuration/workload-credential/network-policy/fence drift -> deny;
- final Security/authentication-strength revision drift -> deny;
- cross-tenant final executing-runtime profile or generation drift -> deny;
- valid final evidence returns the final owning authorization policy revision, not an earlier serial authorization revision;
- no caller-supplied `now` reaches the final-admission port.

`CI GREEN != MERGE AUTHORIZATION` and `WAVE 1 ACCEPTED != WAVE 2 AUTHORIZED`.
