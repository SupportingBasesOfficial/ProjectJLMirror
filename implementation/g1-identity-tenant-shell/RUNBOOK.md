# G1 Identity + Tenant + Protected Shell — Runtime Proof

This slice composes the accepted Wave 1 browser-authentication, browser-session and current-authority primitives into the first protected JLMirror shell. It does not create new identity, membership, permission or tenant-lifecycle semantics.

## Local proof

From repository root:

```bash
python tools/g1/run_identity_tenant_shell_runtime.py
```

The canonical runner performs four bounded proofs:

1. Python unit/adversarial tests for OIDC transaction binding, opaque server-side session issuance, single-use callback, current tenant re-admission, cross-tenant denial, logout/revocation and stale-session denial;
2. Node presentation tests for loading/ready/unauthenticated/forbidden/revoked/unavailable shell states and no tenant-context disclosure outside an admitted `ready` state;
3. a pinned PostgreSQL container conformance proof for the logical BFF transaction/session authority schema;\n4. a real headless Chrome journey against the HTTPS BFF/frontend entrypoint covering admitted tenant, forbidden cross-tenant, revoked current authority, CSRF rejection and CSRF-protected logout.

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

## Executable G1 entrypoints

The bounded local application entrypoints are:

- `python apps/g1-identity-tenant-shell/bff_server.py --certfile <cert> --keyfile <key>` for the confidential HTTPS BFF/application boundary;
- `python apps/g1-identity-tenant-shell/start_frontend.py --certfile <cert> --keyfile <key>` for the standalone static frontend proof.

The canonical browser E2E enables the explicitly test-only `--fixture` bootstrap. That fixture still executes the accepted PKCE/OIDC composition, opaque server-side session issuance, current authentication-strength check and tenant denial semantics; it does not create production identity or tenant truth.

## Browser E2E

`tools/g1/run_identity_tenant_shell_browser_e2e.py` launches the HTTPS BFF and a real installed Chrome/Chromium headless browser. It proves:

- admitted `tenant-a` renders only after current shell admission;
- a browser-selected `tenant-b` fails closed and does not render requested tenant context;
- revoked authority renders no tenant context;
- a state-changing logout without the CSRF header is rejected while the session remains current;
- the accepted versioned HMAC CSRF cookie/header binding permits logout, after which stale session reuse becomes unauthenticated.

## Runtime workflow

`.github/workflows/g1-identity-tenant-shell-runtime.yml` is intentionally canonical JSON-form YAML because the trusted implementation-scope validator parses the exact object structure. It has zero GitHub token permissions and exactly one executable responsibility:

```text
python tools/g1/run_identity_tenant_shell_runtime.py
```

## Product boundary

The frontend is deliberately minimal. It renders current tenant context only after a `ready` response with complete admitted identity/revision evidence. Denied, revoked, unavailable and malformed states expose no tenant context and do not invent navigation or G2+ behavior.

## Merge boundary

Green runtime/scope/readiness evidence is not merge authorization. A separate owner authorization remains required immediately before merge.


## Executable product entrypoints

The slice now exposes bounded executable entrypoints rather than test-only functions:

```bash
PYTHONPATH=src python apps/g1-identity-tenant-shell/bff_server.py \
  --host 127.0.0.1 --port 8444 \
  --certfile <cert.pem> --keyfile <key.pem>
```

Without `--fixture`, the fixture IdP and fixture current-authority adapters are unreachable and the BFF fails closed until real deployment adapters are configured. Deterministic fixture CSRF keys are isolated to `--fixture`; the non-fixture process does not reuse them.

The standalone frontend entrypoint is:

```bash
python apps/g1-identity-tenant-shell/start_frontend.py \
  --host 127.0.0.1 --port 8443 \
  --certfile <cert.pem> --keyfile <key.pem>
```

The browser proof uses the same-origin BFF-hosted frontend so protected browser cookies never need a cross-origin relaxation.

## Fixture bootstrap

`implementation/g1-identity-tenant-shell/fixture_bootstrap.json` is the explicit E2E-16 identity/tenant bootstrap. The browser harness consumes it directly; it is not an ornamental sample.

Fixture endpoints exist only when the BFF is started with `--fixture`. The E2E proof separately starts a non-fixture BFF and verifies those endpoints return 404.

## Current-authority composition

`src/jlmirror_g1/authority.py` is an adapter, not a new authority owner. For every admitted shell read it:

1. resolves current placement server-side from the requested logical tenant;
2. constructs canonical `TenantContext` through the accepted Wave 1 owner;
3. requires `organization.memberships.read`;
4. requires current policy-driven authentication-strength evidence from the server-side browser session;
5. invokes `authorize_protected_operation()`;
6. accepts the shell only after one revision-bound `FinalAdmissionEvidence`.

The browser-selected tenant remains request scope only.

## CSRF proof

State-changing BFF logout requires all of the following simultaneously:

- exact trusted same-origin `Origin`;
- one opaque HttpOnly server-side session cookie;
- one CSRF cookie;
- exactly one matching `X-JLMirror-CSRF` header;
- a token valid under the current/previous two-key HMAC ring and bound to the session lineage.

Missing/duplicate/mismatched evidence fails closed before session retirement.
