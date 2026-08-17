# TenantContext and Placement Lifecycle

**Status:** proposed baseline  
**Primary ADRs:** ADR-003, ADR-004, ADR-005

## TenantContext

Every tenant-scoped unit of work receives one canonical logical context.

Conceptual fields:

```text
tenant_id             immutable logical tenant identity
principal_id          authenticated human/machine principal
principal_type        human | api | worker/service (accepted taxonomy)
membership_id         tenant membership when applicable
authorization_context resolved policy/permission reference or snapshot metadata
request_id            transport request identity when present
correlation_id        end-to-end business/diagnostic flow identity
causation_id          prior event/job/operation that caused this work when present
operation_id          stable side-effecting operation identity when required
cell_id               trusted internally resolved cell
placement_version     routing generation used for admission
isolation_class       pooled/dedicated accepted class
```

`TenantContext` never contains unrestricted database credentials or caller-controlled schema/cluster routing.

## Construction rules

- HTTP: constructed after authentication + trusted placement resolution and validated by destination cell.
- Job/event: reconstructed from validated logical tenant identity and current trusted placement; message routing metadata is not blindly trusted.
- Internal application call: propagated explicitly, not recovered from global mutable process state.
- Database transaction: tenant identity is projected into transaction-local database context for data-layer enforcement.

## Placement admission

Before tenant-scoped mutation, the cell validates that:

1. `tenant_id` is assigned/admitted to the cell;
2. placement state permits the operation;
3. the routing generation is current or is safely re-resolved;
4. tenant is not suspended/decommissioned;
5. relocation admission policy permits writes.

Reads during relocation follow the relocation phase policy; they must never read from an ambiguous authoritative source.

## Placement state behavior

### provisioning

No normal tenant traffic. Provisioning jobs initialize data/configuration and validate readiness before activation.

### active

Normal admitted traffic.

### migrating

Relocation orchestrator controls read/write admission. Ordinary callers cannot choose source/target.

### suspended

Normal tenant operations are denied according to product policy; narrowly scoped platform recovery/admin operations may remain.

### decommissioning

No new normal work. Data/export/retention obligations are completed according to policy before physical cleanup.

### failed

Manual/automated recovery path required; fail closed rather than guessing placement.

## Placement cache

Placement caches use key `tenant_id` and include `placement_version`, state and expiry. Cache invalidation is version-aware. A cache hit never overrides a newer authoritative version observed by the destination cell.

## Stale async work

A job/event may contain the placement version observed when it was created for diagnostic/stale-writer detection, but the consumer re-resolves logical tenant placement before authoritative work. If the unit is pinned to a source cell during relocation, that pin is issued by the relocation orchestrator, not by the original caller.
