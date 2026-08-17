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

## Secrets

**SEC-SEC-001** — Source code and ordinary configuration SHALL use secret references rather than production secret values.

**SEC-SEC-002** — Secrets SHALL be excluded from application logs, traces, metrics labels, error responses, domain/integration events, queue payloads and audit snapshots.

**SEC-SEC-003** — Secret rotation SHALL be possible without redefining the business entity that references the secret.

## Input and integrations

**SEC-INT-001** — All inbound external data is untrusted and SHALL be validated for schema, size and semantic constraints before entering owning domains.

**SEC-INT-002** — Outbound HTTP/integration capability SHALL defend against SSRF, unrestricted redirects, unsafe protocols/addresses and unbounded response bodies according to connector threat model.

**SEC-INT-003** — Webhook authentication/signature mechanisms SHALL support replay protection where the external protocol allows it.

## Automation and data administration

**SEC-EXEC-001** — Script/command execution SHALL use an execution boundary with explicit target scope, timeout, resource controls, credential context and result/output policy.

**SEC-EXEC-002** — Direct SQL/data administration SHALL use dedicated database/runtime privileges and SHALL NOT run as database superuser or unrestricted application owner.

**SEC-EXEC-003** — Export/import SHALL validate authorization at request time and again at execution/download time when asynchronous or delayed.

## Audit and telemetry

**SEC-AUD-001** — Privileged security-sensitive mutations SHALL generate tamper-resistant audit records not mutable by normal application runtime.

**SEC-AUD-002** — Security telemetry SHALL preserve correlation and actor/tenant context without leaking protected values.

## Abuse protection

**SEC-ABUSE-001** — Rate/usage limits SHALL be enforceable across dimensions including principal/API key, tenant, route/operation and integration where required.

**SEC-ABUSE-002** — Expensive capabilities such as reports, exports, SQL queries, automation and provider synchronization SHALL have explicit resource/concurrency controls.

## Supply chain and deployment

**SEC-SUPPLY-001** — Dependencies, build inputs, secrets and release artifacts SHALL be subject to automated integrity/security checks before production release.

**SEC-SUPPLY-002** — Production runtime principals SHALL use least privilege and SHALL be distinct from migration/administrative owners where applicable.
