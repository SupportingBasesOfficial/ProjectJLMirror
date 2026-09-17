# G1 Identity + Tenant + Protected Shell — Runtime Proof

This slice composes the accepted Wave 1 browser-authentication, browser-session and current-authority primitives into the first protected JLMirror shell. It does not create new identity, membership, permission or tenant-lifecycle semantics.

## Local proof

From repository root:

```bash
python tools/g1/run_identity_tenant_shell_runtime.py
```

The canonical runner performs three bounded proofs:

1. Python unit/adversarial tests for OIDC transaction binding, opaque server-side session issuance, single-use callback, current tenant re-admission, cross-tenant denial, logout/revocation and stale-session denial;
2. Node presentation tests for loading/ready/unauthenticated/forbidden/revoked/unavailable shell states and no tenant-context disclosure outside an admitted `ready` state;
3. a pinned PostgreSQL container conformance proof for the logical BFF transaction/session authority schema.

## Browser/BFF security boundary

- OIDC Authorization Code is exchanged only by the confidential BFF-side composition.
- PKCE S256 verifier, state and nonce are bound to a single server-side authorization transaction.
- the callback transaction is consumed once;
- the browser receives only an opaque session capability;
- raw access, refresh and ID tokens are not browser application state;
- every protected shell opening resolves the current server-side session and then re-establishes current tenant admission;
- caller `tenant_id` expresses requested logical scope only and is never sufficient authority;
- returned admission evidence for another tenant is rejected;
- retired/expired sessions cannot be reused.

## Persistence boundary

`sql/g1/001_browser_session_authority.sql` materializes only logical Identity/BFF-session state needed by this slice:

- browser authorization transactions;
- opaque-handle digests and session generations;
- single-use transaction consumption;
- single-winner session retirement.

The conformance harness explicitly checks that the G1 schema does not create membership, permission, tenant-status or tenant-access-generation columns. Those truths remain owned by their existing authorities.

This SQL selects no production topology, replication shape, cache product, RPO/RTO or production numeric. Those remain governed by their separately accepted/open decisions.

## Runtime workflow

`.github/workflows/g1-identity-tenant-shell-runtime.yml` is intentionally canonical JSON-form YAML because the trusted implementation-scope validator parses the exact object structure. It has zero GitHub token permissions and exactly one executable responsibility:

```text
python tools/g1/run_identity_tenant_shell_runtime.py
```

## Product boundary

The frontend is deliberately minimal. It renders current tenant context only after a `ready` response with complete admitted identity/revision evidence. Denied, revoked, unavailable and malformed states expose no tenant context and do not invent navigation or G2+ behavior.

## Merge boundary

Green runtime/scope/readiness evidence is not merge authorization. A separate owner authorization remains required immediately before merge.
