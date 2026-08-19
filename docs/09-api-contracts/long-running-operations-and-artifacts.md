# Long-Running Operations and Artifact Contracts

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Work whose completion cannot be safely guaranteed inside one bounded synchronous request is represented as a durable operation resource. The API does not hide durable processes behind request timeouts, queue IDs or provider-native job IDs.

This includes, depending on workload and policy:

- tenant provisioning/decommissioning/relocation;
- large import/export;
- report generation;
- long-running automation;
- reconciliation after ambiguous external effects;
- governed deletion/erasure;
- large backfills/data administration;
- provider synchronization actions when duration or uncertainty warrants it.

## Operation resource identity

Tenant-scoped operations use:

```text
/api/v1/tenants/{tenant_id}/operations/{operation_id}
```

Platform-global operations use:

```text
/api/v1/platform/operations/{operation_id}
```

`operation_id` is a stable platform identity independent of queue message IDs, worker attempts, provider request IDs and physical execution location.

## `202 Accepted`

When an endpoint accepts durable asynchronous responsibility:

```text
202 Accepted
Location: /api/v1/tenants/{tenant_id}/operations/{operation_id}
```

The response body returns the operation representation or a documented equivalent reference.

`202` means the operation was durably admitted under the contract. It does not mean the requested business outcome succeeded.

## Operation representation

Conceptual shape:

```json
{
  "id": "op_opaque",
  "tenant_id": "tenant_opaque",
  "operation_type": "report_generation",
  "status": "running",
  "revision": "rev_opaque",
  "requested_at": "2026-08-18T12:00:00Z",
  "started_at": "2026-08-18T12:00:01Z",
  "completed_at": null,
  "requested_by": {
    "principal_id": "principal_opaque",
    "principal_type": "human"
  },
  "progress": {
    "completed_units": 42,
    "total_units": 100
  },
  "result": null,
  "error": null
}
```

Fields are operation-type-specific where necessary. Sensitive internal worker/provider details are not exposed by default.

## Operation status taxonomy

The baseline logical states are:

```text
queued
running
waiting
reconciliation_required
succeeded
failed
cancelling
cancelled
```

Individual operation types MAY use a strict subset or refine additional documented states. External state is not a mirror of queue/worker internals.

### `queued`

Durably admitted but no active execution has been established yet.

### `running`

Execution is actively progressing or an owner process holds current work authority.

### `waiting`

Progress is intentionally waiting for an accepted external/precondition state such as approval, scheduled time, provider response or governed hold condition.

### `reconciliation_required`

The platform cannot yet safely classify an external/cross-authority outcome. Automatic duplicate execution is not eligible until reconciliation establishes truth.

### `succeeded`

The contractually requested outcome reached its accepted terminal success state.

### `failed`

The operation reached a terminal failure under its contract. Failure does not imply partial external effects were rolled back unless the operation type explicitly guarantees that.

### `cancelling` / `cancelled`

Cancellation was requested and is in progress / reached its accepted terminal cancelled state. Cancellation is never assumed to rewind already-committed irreversible effects.

## Progress

Progress is optional because not all workflows have a meaningful percentage.

When exposed, progress uses stable semantics such as:

- completed/total units;
- current stage and stage count;
- processed bytes/items;
- known estimated percentage only when the denominator is meaningful.

A fake percentage based only on elapsed time is not a contract.

## Result

A terminal successful operation exposes a stable result reference where applicable:

```json
{
  "result": {
    "resource": {
      "type": "artifact",
      "id": "artifact_opaque"
    }
  }
}
```

Large result data is represented through resources/artifacts rather than embedded into the operation indefinitely.

## Error

Operation failure uses the same stable problem/error-code vocabulary as synchronous API errors, but as durable operation state.

A safe operation error may include:

```json
{
  "error": {
    "code": "provider.authentication_failed",
    "detail": "The configured provider credentials could not be authenticated."
  }
}
```

It does not persist or expose raw credentials, stack traces or unrestricted provider payloads.

## Polling

Clients poll the stable operation resource with bounded backoff. Responses MAY include `Retry-After` when useful.

Polling SHALL NOT require the original worker/queue node to remain alive.

## Realtime acceleration

Phase 10 MAY define operation-status realtime events to accelerate UI updates. Realtime remains advisory: clients can always recover current operation state through the authoritative API resource.

## Cancellation

Where cancellation is supported:

```text
POST /api/v1/tenants/{tenant_id}/operations/{operation_id}:cancel
```

The cancel command is itself idempotent under the operation contract and MAY require `Idempotency-Key` where repeated external cancellation could have effects.

Cancellation response indicates accepted cancellation intent/current state; it does not promise immediate process termination.

A worker transport interrupt alone is not proof that the business operation is cancelled.

## Resumption/retry

Clients do not create a new operation merely because polling observed `waiting` or `reconciliation_required`.

A retry/restart command is allowed only when the owning operation type exposes one and when current durable state proves a new attempt is safe.

## Artifact resource

Generated reports, exports, attachments and other protected binary content are represented by stable metadata resources separate from delivery capability.

Conceptual representation:

```json
{
  "id": "artifact_opaque",
  "tenant_id": "tenant_opaque",
  "artifact_type": "report",
  "status": "available",
  "content_type": "application/pdf",
  "size_bytes": 1234567,
  "checksum": {
    "algorithm": "sha256",
    "value": "..."
  },
  "created_at": "...",
  "expires_at": "...",
  "classification": "confidential"
}
```

Storage bucket/key/object version is not part of the normal public resource representation.

## Artifact status

External artifact status SHOULD remain a contract projection of the accepted internal lifecycle. Example states:

```text
preparing
available
unavailable
erasure_fencing
deleting
deleted
reconciliation_required
failed
```

An internal `STAGING/PENDING_OBJECT` state may map to `preparing` if exposing internal detail adds no consumer value.

Only a contractually `available` artifact may be released.

## Download contract

Protected artifact bytes are retrieved through a logical application-mediated endpoint such as:

```text
GET /api/v1/tenants/{tenant_id}/artifacts/{artifact_id}/content
```

The endpoint:

1. authenticates the caller;
2. resolves current tenant context;
3. checks current authorization;
4. verifies the artifact is currently releasable;
5. acquires the accepted generation-bound active-delivery lease/fence before the first protected byte;
6. streams or delegates delivery only through a mechanism preserving equivalent revocation/fencing semantics.

The logical API contract remains stable if the implementation later moves between application streaming, CDN/object-storage proxying or another mechanism.

A direct vendor signed URL MAY be used internally only when it satisfies the accepted prompt-revocation, delivery-generation and active-stream fencing invariants. Vendor URL shape is never the canonical artifact identity.

## Range/resume

Byte-range/resumable download support MAY be added per artifact class. If supported, every resumed request re-enters current authorization/releasability/delivery-generation admission; an old range request does not bypass current erasure fencing.

## Delayed export/report authorization

User-requested export/report operations reauthorize before protected execution and again before artifact release according to the accepted security baseline.

The fact that an artifact was generated for a user does not grant permanent download authority after membership/permission/tenant access is revoked.

## Import contract

Large imports are modeled as operation + input artifact/staging resources rather than giant unbounded synchronous requests.

Import flow conceptually:

```text
create/import intent
  -> upload/stage bounded input artifact
  -> validate
  -> current authorization check before protected mutation
  -> durable operation executes/resumes
  -> result/error resource
```

Request-time human authority does not persist as worker authority.

## Governed deletion/erasure

Deletion/erasure of an artifact that spans metadata and object storage uses a durable operation/resource state. The API SHALL NOT report confirmed erasure until the accepted upload-publication, delivery capability/lease/active-stream and governance/legal-hold reconciliation conditions have passed.

If state is uncertain, the external operation remains non-terminal/reconciliation-required rather than returning a false success.

## Maximum-state rule

Operation and artifact contracts SHALL remain valid when worker implementation, queue vendor, object store, cell placement or process decomposition changes. A client tracks logical `operation_id` / `artifact_id`, never the transient execution mechanism.