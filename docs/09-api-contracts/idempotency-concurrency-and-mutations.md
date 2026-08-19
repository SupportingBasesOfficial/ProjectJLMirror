# Idempotency, Concurrency and Mutation Contracts

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Effectful HTTP requests may be retried by clients, proxies, SDKs or operators after network failure. The API contract therefore distinguishes HTTP method idempotency from business-effect idempotency and defines durable replay behavior explicitly.

## Idempotency header

Retry-safe effectful `POST`/command contracts use:

```text
Idempotency-Key: <opaque client-generated key>
```

The key is opaque to the platform. Clients SHALL NOT encode secrets in it.

The accepted maximum key length is 255 UTF-8 bytes after transport decoding. Endpoint-specific profiles MAY impose a smaller documented limit.

`Idempotency-Key` is not tenant scope, authorization, correlation or resource identity.

## When the key is required

A contract SHALL mark idempotency as one of:

```text
none
optional
required
intrinsic
```

- `none` — the operation has no meaningful idempotency-key behavior;
- `optional` — key may be supplied for replay protection;
- `required` — caller MUST supply a key because automatic/client retry without it could duplicate a logical effect;
- `intrinsic` — the HTTP/resource operation is already idempotent under a stable resource/conditional mutation contract and an additional key is unnecessary.

High-risk externally effectful commands SHOULD default to `required` unless the domain proves an equivalent stable operation identity.

## Effective idempotency scope

The client supplies only the key. The server derives the effective scope from trusted contract context, including as applicable:

- API major version;
- canonical operation/route contract identity;
- tenant/global scope;
- principal/credential dimension when semantically required;
- resource/command scope where the operation contract requires it.

A client-provided header/body field cannot select a weaker deduplication namespace.

## Request fingerprint

For keyed operations, the server computes/persists a stable request fingerprint over the semantically relevant normalized request contract.

The fingerprint SHALL be insensitive to transport details that do not alter the logical request, and SHALL include all fields whose difference would represent a different logical operation.

The same effective scope/key with a different fingerprint is a conflict and MUST NOT execute.

## Atomic admission

The accepted system invariant applies directly to the API contract:

```text
request
  -> derive effective idempotency scope
  -> atomic create-or-observe durable claim
       |-- new + matching request -> one logical executor
       |-- existing + different fingerprint -> conflict
       |-- existing in progress + same fingerprint -> deterministic in-progress result
       |-- existing completed + same fingerprint -> replay established logical result
```

A `SELECT` followed by an unprotected claim insert is not sufficient.

## Replay representation

A completed same-fingerprint retry returns the contractually equivalent logical result without re-executing the protected effect.

The platform SHOULD preserve/reconstruct:

- equivalent HTTP success class/status;
- canonical resource/operation identity;
- response representation or stable result reference;
- relevant `Location` header;
- safe contract metadata needed by the caller.

Transport-ephemeral values such as request ID are allowed to differ between the original response and replay.

## Different fingerprint conflict

Reusing a key in the same effective scope for a different request returns:

```text
409 Conflict
code: idempotency.key_reused
```

No effectful processing of the conflicting request is allowed.

## In-progress duplicate

A same-fingerprint request that observes an existing non-terminal executable claim does not become a second executor.

Preferred representation:

```text
409 Conflict
code: idempotency.in_progress
```

with `Retry-After` when the server can provide a safe polling interval and, when applicable, a stable operation resource reference.

An endpoint whose effect is represented by a durable operation MAY instead return the same `202 Accepted` operation resource for a same-key duplicate. The endpoint contract SHALL choose one behavior and keep it stable.

## Claim completion and local mutation

When the idempotency claim and authoritative mutation are co-resident, successful completion commits the mutation, required audit/outbox, stable result linkage and completed claim atomically.

A retry after response loss SHALL discover/replay the committed result rather than execute the mutation again.

## Cross-authority/external effects

When the protected effect occurs in another authority, the API operation carries/derives a stable `operation_id` that can be reconciled.

If outcome becomes ambiguous, the claim does not silently expire into retry eligibility. The API exposes a durable operation/reconciliation state where possible.

Timeout or lease expiry alone is never evidence that an irreversible effect did not happen.

## Idempotency retention

Claims remain durable for at least the documented retry/replay/recovery window of the operation. Retention may vary by operation class.

An endpoint SHALL NOT advertise a retry window longer than the platform can safely preserve the claim/result evidence needed to honor it.

Numeric retention durations remain operation/SLO policy until separately accepted.

## Optimistic concurrency

Mutable resources with lost-update risk use an opaque revision validator.

Successful reads SHOULD expose:

```text
ETag: "<opaque-strong-revision>"
```

The representation MAY also expose the same logical revision as `revision` when useful to SDK/UI clients.

## Conditional mutation

Contracts requiring optimistic concurrency require:

```text
If-Match: "<opaque-strong-revision>"
```

If the precondition is required but omitted:

```text
428 Precondition Required
code: concurrency.precondition_required
```

If the supplied revision is stale/mismatched:

```text
412 Precondition Failed
code: concurrency.revision_mismatch
```

A failed precondition performs no protected mutation.

## Commands and revisions

A state-transition command MAY also require `If-Match` when executing the command against an obsolete resource revision would be unsafe.

Example:

```text
POST /api/v1/tenants/{tenant_id}/incidents/{incident_id}:resolve
If-Match: "rev_..."
Idempotency-Key: ...
```

Idempotency protects duplicate execution of the same logical command. `If-Match` protects against executing it against a resource version the caller did not intend. They solve different races and MAY both be required.

## Create-if-absent

Where a business resource has a natural/caller-chosen unique key, the endpoint contract MAY expose create-if-absent semantics. Database implementation details remain hidden.

A uniqueness conflict returns a stable domain conflict code identifying the conflicting logical constraint when safe; it does not expose raw database constraint names.

## PATCH conflict behavior

A PATCH that is syntactically valid but violates a current domain invariant/state machine returns a domain conflict/semantic-validation response rather than silently overwriting current state.

The contract SHALL distinguish:

- stale revision (`412`);
- current-state business conflict (`409`);
- field/input semantic invalidity (`422`);
- authorization denial (`403`/concealed `404`).

## DELETE and repeated requests

DELETE contracts declare whether deleting an already absent/terminally deleted resource returns:

- idempotent success/no-content;
- not-found;
- the existing asynchronous deletion operation.

Governed erasure that spans authorities SHOULD return/replay the stable deletion/erasure operation rather than creating a second cleanup process.

## Bulk mutation

Bulk requests do not inherit one giant implicit transaction.

Each bulk endpoint SHALL declare:

- maximum item count;
- whether the batch is atomic or per-item;
- per-item idempotency identity/result semantics;
- partial failure representation;
- whether large requests are converted into an asynchronous operation.

Cross-domain or high-volume bulk work SHOULD default to durable operation semantics instead of holding one database transaction across arbitrary item counts.

## SDK retry policy

Future generated/official SDKs SHALL derive automatic retry behavior from operation metadata.

An SDK MUST NOT automatically retry an effectful operation solely because it received a network timeout. Automatic retry is permitted only when the method/endpoint is intrinsically retry-safe or a valid idempotency/operation contract makes replay safe.