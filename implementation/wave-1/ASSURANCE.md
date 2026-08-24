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
- explicit cross-tenant privileged platform operations cannot be admitted through the ordinary application runtime boundary: a caller-selected `CONTROL_PLANE` binding is insufficient and the actual executing runtime must be proven current/active by the trusted runtime authority with exact Control Plane profile/principal/isolation/ingress/environment binding;
- privileged/policy-sensitive human admission revalidates the exact principal-bound authentication-strength evidence against the current Security policy after the owning authorization decision and immediately before final admission; an earlier MFA/step-up pass is not durable authority;
- owning authorization cannot be returned as admitted when the exact TenantContext/placement/runtime/fence currentness changes during authorization evaluation; the placement/currentness boundary is revalidated after the owning decision and before protected-operation admission;
- the owning membership/permission/resource authorization is evaluated again as the final admission check after placement, authentication-strength and principal-currentness checks; an earlier `AuthorizationDecision.current` snapshot is not durable final authorization;
- fenced effect admission resolves current state from the owning fence authority; a typed/supplied fence record is not currentness proof, and co-resident PostgreSQL effects retain the same-transaction predicate requirement;
- persisted fence authority state is revalidated against canonical identifier/positive-epoch constraints rather than accepted by object presence;
- reused PostgreSQL fence objects fail closed unless the migration authority owns the schema/table/functions, no effective non-owner schema/table/function ACL survives, and no direct or transitive `pg_auth_members` path can assume/inherit the migration-owner role before separately reviewed C2 role mapping;
- no residual C2 product is silently promoted to architecture authority;
- no Product/domain endpoint family is introduced beyond accepted authority;
- review findings are resolved only after later exact-HEAD evidence;
- Native Assurance passes 1–12 are clean on the exact final HEAD.

`CI GREEN != MERGE AUTHORIZATION` and `WAVE 1 ACCEPTED != WAVE 2 AUTHORIZED`.
