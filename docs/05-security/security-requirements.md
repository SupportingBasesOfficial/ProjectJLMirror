# Security Requirements

**Status:** proposed baseline

## Identity and credentials

**SEC-ID-001** — Human and machine credentials SHALL be independently revocable and SHALL have explicit expiration/lifecycle policy where applicable.

**SEC-ID-002** — Privileged human access SHALL support MFA and policy-driven step-up/re-authentication where risk warrants it.

**SEC-ID-003** — Password-equivalent secrets SHALL be stored using algorithms/settings appropriate to their credential class; reversible encryption is not a substitute for password hashing.

## Tenant isolation

**SEC-TEN-001** — Tenant context SHALL be resolved from trusted logical identity and platform metadata. Caller-supplied physical schema, database URL, cluster or unrestricted secret reference SHALL NOT select tenant placement.

**SEC-TEN-002** — Tenant isolation SHALL be enforced through multiple layers appropriate to the accepted data architecture, including application authorization and data-layer controls.

**SEC-TEN-003** — Cache keys, pub/sub topics, queue routing, observability dimensions, exports and read models containing protected tenant state SHALL include unambiguous tenant isolation semantics.

## Authorization

**SEC-AUTHZ-001** — Every privileged or protected operation SHALL declare required authorization policy/permission and scope.

**SEC-AUTHZ-002** — Cross-tenant operations SHALL be distinct privileged operations rather than implicit wildcard behavior.

**SEC-AUTHZ-003** — Authorization decisions SHOULD be explainable enough for audit/debugging without exposing secrets.

## Browser and realtime

**SEC-BROWSER-001** — The first-party browser SHALL use the BFF as the confidential session boundary and SHALL NOT receive long-lived platform access or refresh credentials.

**SEC-BROWSER-002** — A protected browser realtime connection that bypasses the normal BFF request hop SHALL use a short-lived, narrowly scoped connection capability minted through the BFF (or an explicitly reviewed equivalent) and SHALL validate the expected browser Origin. Ambient cookies alone SHALL NOT authorize a protected direct WebSocket connection.

**SEC-BROWSER-003** — Realtime connection capabilities SHALL be bounded in lifetime and scope, resistant to replay/reuse as appropriate to their contract, and SHALL NOT become general API bearer credentials.

## Secrets

**SEC-SEC-001** — Source code and ordinary configuration SHALL use secret references rather than production secret values.

**SEC-SEC-002** — Secrets SHALL be excluded from application logs, traces, metrics labels, error responses, domain/integration events, queue payloads and audit snapshots.

**SEC-SEC-003** — Secret rotation SHALL be possible without redefining the business entity that references the secret.

## Input and integrations

**SEC-INT-001** — All inbound external data is untrusted and SHALL be validated for schema, size and semantic constraints before entering owning domains.

**SEC-INT-002** — Outbound HTTP/integration capability SHALL defend against SSRF, unrestricted redirects, unsafe protocols/addresses and unbounded response bodies according to connector threat model.

**SEC-INT-003** — Webhook authentication/signature mechanisms SHALL support replay protection where the external protocol allows it.

**SEC-INT-004** — Inbound callback endpoints SHALL enforce a hard transport/raw-body byte limit before buffering the complete body or performing signature/authentication work. Declared `Content-Length` MAY enable earlier rejection but SHALL NOT be the only limit; streaming byte accounting or an equivalent transport-enforced bound SHALL reject oversized bodies. Parser/decompression limits remain independently bounded after authenticity checks.

## Automation and data administration

**SEC-EXEC-001** — Script/command execution SHALL use an execution boundary with explicit target scope, timeout, resource controls, credential context and result/output policy.

**SEC-EXEC-002** — Direct SQL/data administration SHALL use dedicated database/runtime privileges and SHALL NOT run as database superuser or unrestricted application owner.

**SEC-EXEC-003** — Export/import SHALL validate authorization at request time and again before delayed/asynchronous execution and release/download. A delayed user-requested artifact SHALL NOT be released solely because the requester was authorized when the job was created.

**SEC-EXEC-004** — Caller-authored SQL SHALL NOT be allowed to replace the tenant-binding input trusted by RLS/data policy. Interactive SQL against pooled protected data SHALL use a tenant binding the SQL principal cannot alter (for example a tenant-bound database principal/protected mapping) or a mediated/physically isolated query surface with equivalent guarantees.

## Audit and telemetry

**SEC-AUD-001** — Privileged security-sensitive mutations SHALL generate tamper-resistant audit records not mutable by normal application runtime.

**SEC-AUD-002** — Security telemetry SHALL preserve correlation and actor/tenant context without leaking protected values.

**SEC-AUD-003** — When audit evidence is required for a successful local authoritative mutation, the audit record or a durable audit intent SHALL commit atomically with that mutation. Post-commit best-effort audit alone is insufficient.

## Abuse protection

**SEC-ABUSE-001** — Rate/usage limits SHALL be enforceable across dimensions including principal/API key, tenant, route/operation and integration where required.

**SEC-ABUSE-002** — Expensive capabilities such as reports, exports, SQL queries, automation and provider synchronization SHALL have explicit resource/concurrency controls.

## Supply chain and deployment

**SEC-SUPPLY-001** — Dependencies, build inputs, secrets and release artifacts SHALL be subject to automated integrity/security checks before production release.

**SEC-SUPPLY-002** — Production runtime principals SHALL use least privilege and SHALL be distinct from migration/administrative owners where applicable.
