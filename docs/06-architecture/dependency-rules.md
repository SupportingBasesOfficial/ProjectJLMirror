# Architecture Dependency Rules

**Status:** accepted

These rules are intended to become automated architecture tests once implementation begins.

## Layer direction

Within a bounded-context module:

```text
presentation -> application -> domain
infrastructure -> application/domain ports
```

The domain layer does not import HTTP frameworks, queue SDKs, cache SDKs, database ORM implementations or provider clients.

## Cross-context rules

- A context MAY call another context through an explicitly exported application/query contract when synchronous consistency is required.
- A context MAY consume a versioned integration event owned by another context.
- A context MUST NOT directly update another context's tables/repositories.
- A context MUST NOT import another context's internal entities/repositories as a shortcut.
- Shared packages MUST contain genuinely cross-cutting contracts/primitives, not a backdoor shared domain model.
- Read models are owned projections; they do not transfer mutation ownership.

## Infrastructure rules

- Cache, queue, broker, object storage and telemetry SDKs are accessed through infrastructure adapters or shared platform primitives with explicit semantics.
- Database access is tenant-context aware by construction for tenant-scoped repositories.
- External provider SDK/native payload models stop at the adapter boundary.
- Secrets are resolved by secret reference at runtime and never passed as ordinary domain values farther than necessary.

## Runtime rules

- HTTP handlers remain thin and do not contain durable business policy.
- Workers invoke application use cases; queue callbacks do not become a second business implementation.
- Realtime gateways deliver authorized projections/events and do not become a second source of truth.
- BFF code contains web/session/composition concerns but not domain authority.

## Enforcement plan

Implementation SHALL add:

- module-boundary lint/import rules;
- architecture tests over dependency graph;
- forbidden direct database ownership tests/review;
- contract compatibility tests;
- tenant-isolation repository tests;
- CI checks preventing secrets and unsupported package directions.