# Security Policy

Security is a system property of JLMIRROR and is enforced across identity, authorization, tenant resolution, data access, asynchronous processing, integrations, observability, deployment, and operations.

## Repository handling

Do not commit:

- passwords, tokens, private keys, API keys, or refresh tokens;
- production connection strings or unrestricted database credentials;
- customer data or personally identifiable production records;
- private network topology, internal-only endpoints, or privileged operational instructions;
- decrypted integration credentials;
- incident-response secrets.

Use synthetic examples and secret references in documentation.

## Product security invariants

- Tenant-scoped operations require a validated tenant context.
- Authorization is enforced server-side; UI visibility is not authorization.
- A principal from one tenant must never read or mutate another tenant's protected resources unless an explicitly privileged cross-tenant operation exists and is audited.
- Secrets must never be emitted to logs, traces, metrics, events, error payloads, or client responses.
- Privileged operations must be attributable through audit records.
- External integrations are untrusted boundaries.
- Asynchronous messages must carry validated identity/tenant context by reference, not trusted caller-supplied connection details.

## Vulnerability reports

Do not disclose exploitable security findings in public issues. Use the repository owner's private reporting channel when available.