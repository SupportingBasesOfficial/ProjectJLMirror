# System Invariants

**Status:** proposed baseline

Invariants are implementation-independent conditions that must remain true across HTTP requests, workers, jobs, events, integrations, administrative tools, migrations, and recovery paths.

## Tenant and authorization

**INV-TENANT-001** — Every tenant-scoped operation MUST execute with a validated Tenant Context.

**INV-TENANT-002** — A principal scoped to Tenant A MUST NOT access protected Tenant B resources unless an explicitly privileged cross-tenant operation authorizes it.

**INV-TENANT-003** — Tenant placement, schema/database routing, or connection metadata MUST be derived from trusted platform metadata, never directly from caller-supplied physical routing data.

**INV-AUTHZ-001** — Authorization MUST be enforced server-side at the owning boundary. Client-side feature visibility is not authorization.

**INV-AUTHZ-002** — Feature enablement MUST NOT grant permissions that the principal does not possess.

## Data and ownership

**INV-DATA-001** — Every mutable aggregate has exactly one logical owning domain.

**INV-DATA-002** — A domain MUST NOT directly mutate another domain's owned state through database access.

**INV-DATA-003** — External-provider identifiers MUST NOT be the sole internal identity of platform-owned resources.

**INV-DATA-004** — Durable business truth MUST NOT depend solely on ephemeral cache/pub-sub state.

## Security

**INV-SECRET-001** — Secrets MUST NOT appear in client responses, logs, traces, metrics labels, integration events, queue payloads, or audit before/after snapshots.

**INV-AUDIT-001** — Relevant privileged and security-sensitive mutations MUST produce attributable audit records.

**INV-AUDIT-002** — Normal application runtime MUST NOT update or delete immutable audit records.

## Asynchronous processing

**INV-ASYNC-001** — Any retriable side-effecting operation MUST define idempotency or deduplication behavior.

**INV-ASYNC-002** — A job payload MUST identify the tenant logically and MUST NOT be trusted to carry unrestricted connection secrets or caller-controlled schema routing.

**INV-ASYNC-003** — Failure processing one tenant MUST NOT prevent unrelated tenants from progressing when the workload can be isolated.

## Reliability and integrations

**INV-EXT-001** — Failure of an external provider MUST NOT cause avoidable platform-wide failure.

**INV-EXT-002** — External responses and inbound payloads MUST be treated as untrusted input and validated/normalized at the integration boundary.

**INV-REALTIME-001** — Real-time subscribers MUST be authorized for the tenant/resource scope before receiving protected events.

## Evolution

**INV-MIGRATION-001** — Production schema evolution MUST remain compatible with the active deployment strategy; destructive changes require an explicit migration sequence.

**INV-CONTRACT-001** — Externally consumed API, webhook, event, export, and job contracts MUST be versioned or otherwise evolved compatibly.

## Operability

**INV-OBS-001** — Important operations MUST be correlatable across request, job, worker, integration and persistence boundaries without exposing secrets.

**INV-RECOVERY-001** — A backup is not considered a recovery capability until restoration is tested.