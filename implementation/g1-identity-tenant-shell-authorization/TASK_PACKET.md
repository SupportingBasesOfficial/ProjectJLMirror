# G1 Identity + Tenant + Protected Shell — AI Task Packet

```text
SLICE: g1.identity-tenant-protected-shell@1
GOAL: Authenticated user enters a tenant-scoped JLMirror shell while current platform authorization is enforced and forbidden/cross-tenant context fails closed.
BASE SHA: 7c20c9301711e9a4bf355517d7aa23faad7a05b7
AUTHORITY: proposed g1.identity-tenant-protected-shell@1 authorization; accepted Wave 1 identity/BFF substrate; separately accepted D3 Identity/Security; canonical API/BFF/security contracts; AI E2E delivery constitution.
DEPENDENCIES: accepted Waves 1–3 substrate; G0 bootstrap only where directly required by this G1 slice.
ALLOWED PATHS: future G1-specific apps/runtime/contracts/tests/container/bootstrap paths declared by the implementation PR; no product code is authorized by this proposal until merged.
FORBIDDEN: G2+ product behavior; Monitoring UI; Resource/Metric/Problem/Health UI; Alerting policy/lifecycle; ACK/notification; ITSM; Automation; AIOps; FinOps; Commercial; production deployment; speculative generic design/navigation systems.
DB: Reuse accepted durable Identity/session/current-authority ownership. Add only persistence/bootstrap required by G1 and only when existing accepted substrate does not already provide it.
DOMAIN: No new identity or authorization semantics. JWT validity never equals current authorization. IdP-native roles/groups/orgs never become platform membership/permission truth.
API/BFF: Confidential BFF. OIDC Authorization Code + PKCE S256. Browser receives only opaque server-side session capability. Current tenant/membership/permission/placement/auth-strength authority precedes protected reads/effects. Client tenant identifiers are never authority.
FRONTEND: Minimal protected application shell with tenant context and loading/success/unauthenticated/forbidden/unavailable/revoked-or-stale-authority states. No backend-shape-driven navigation expansion.
FAILURE: IdP new-login/step-up uncertainty fails closed; current-authority uncertainty fails closed; revoked/forbidden tenant is denied without existence leakage; stale positive cache/session state cannot override current durable authority.
SECURITY: Tenant isolation; CSRF explicit; no refresh token or long-lived platform credential in browser JS; forced logout/revocation cannot be masked by stale cache; provider/workload/network identity is never business authority.
TESTS: Unit + integration + real persistence + browser E2E + cross-tenant + revoked permission + suspended/forbidden tenant + stale-session/current-authority adversarial cases.
RUN: Clean checkout -> start G1 dependencies -> migrate/bootstrap -> seed test identity/tenant -> start BFF/backend/frontend -> execute allowed browser journey -> execute forbidden/cross-tenant journey -> container proof -> exact-head CI.
DONE: E2E-16 evidence for this slice, including exact-head CI and browser proof. Human patching of DB/source during the journey is forbidden.
STOP IF: Any required product semantic is not already authorized; implementation needs G2+ behavior; tenant/current-authority owner is ambiguous; a framework/provider feature would become canonical business authority; production-only C3 numeric/topology choice becomes necessary.
```

This packet is a bounded projection of repository truth. It is not merge authority and is not permission to implement before the accompanying authorization becomes canonical.
