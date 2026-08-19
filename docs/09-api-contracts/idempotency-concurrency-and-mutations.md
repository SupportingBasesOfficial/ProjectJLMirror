# Idempotency, Concurrency and Mutation Contracts

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

Effectful HTTP requests may be retried by clients, proxies, SDKs or operators after network failure. The API contract therefore distinguishes HTTP method idempotency from business-effect idempotency and defines durable replay behavior explicitly.

For HTTP surfaces, all idempotency and concurrency semantics operate only after the request has passed `http-message-framing-and-canonicalization.md`. A malformed/ambiguous wire request cannot create a claim, choose an idempotency key, establish a precondition or execute a protected effect.

## Idempotency header

Retry-safe effectful `POST`/command contracts use:

```text
Idempotency-Key: <opaque client-generated key>
```

The key is opaque to the platform. Clients SHALL NOT encode secrets in it.

The key length and accepted character/encoding profile SHALL be bounded before implementation. The concrete transport limit remains `OPEN-API-004`; unlimited key size is not an accepted default.

`Idempotency-Key` is not tenant scope, authorization, correlation or resource identity.

`Idempotency-Key` is a security-sensitive `strict_singleton` input under the canonical HTTP message profile. Duplicate/conflicting instances are rejected before claim creation or protected effect. A proxy and owning service SHALL NOT derive different effective keys by first/last/concatenation behavior, and a request trailer cannot introduce or override the key after header admission.

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
- canonical HTTP method and request-target interpretation;
- tenant/global scope;
- principal/credential dimension when semantically required;
- resource/command scope where the operation contract requires it.

A client-provided header/body field cannot select a weaker deduplication namespace.

An implicit method override, alternate path normalization, untrusted forwarded authority or duplicate header interpretation cannot change the effective idempotency scope after an edge component has made a different decision. Such ambiguity is rejected at canonical ingress.

## Request fingerprint

For keyed operations, the server computes/persists a stable request fingerprint over the semantically relevant normalized request contract.

The fingerprint SHALL be insensitive to transport details that do not alter the logical request, and SHALL include all fields whose difference would represent a different logical operation.

The same effective scope/key with a different fingerprint is a conflict and MUST NOT execute.

Canonical HTTP normalization happens before fingerprinting. Fingerprinting SHALL NOT be used to “paper over” a wire request that different hops could parse into different methods, resources, headers or bodies.

## Atomic admission

The accepted system invariant applies directly to the API contract:

```text
canonical HTTP request
  -> derive effective idempotency scope
  -> compute/validate semantic fingerprint
  -> atomic create-or-observe durable claim
       |-- new + matching request -> one logical executor
       |-- existing + different fingerprint -> conflict
       |-- existing in progress + same fingerprint -> deterministic in-progress result
       |-- existing completed + same fingerprint -> replay established logical result
```

A `SELECT` followed by an unprotected claim insert is not sufficient.

No idempotency claim is created for a request rejected by framing/header/request-target/method/content-coding canonicalization before protected admission.

## Replay representation

A completed same-fingerprint retry returns the contractually equivalent logical result without re-executing the protected effect.

The platform SHOULD preserve/reconstruct:

- equivalent HTTP success class/status where safe;
- canonical resource/operation identity;
- response representation or stable result reference;
- relevant `Location` header;
- safe contract metadata needed by the caller.

Transport-ephemeral values such as request ID are allowed to differ between the original response and replay.

### One-time secret response exception

A secret-producing create/rotate/reissue operation is still subject to the same atomic admission and one-logical-effect rules, but **secret material itself is excluded from replayable completed-result state**.

For an endpoint whose initial successful response may contain a newly generated API secret, recovery code or other non-retrievable credential material:

1. the initial secret-bearing response MAY present that secret under the explicit high-risk representation contract;
2. the platform SHALL NOT retain plaintext/recoverable secret material solely to make that response replayable;
3. if the response is lost, the same idempotency key MUST observe the already-completed logical effect and MUST NOT create/rotate/reissue another credential automatically;
4. the retry MUST NOT re-present the original secret;
5. the retry returns the stable created/rotated resource metadata/reference plus a deterministic non-secret recovery outcome;
6. any recovery that needs new secret material must be a separate explicitly authorized rotate/reissue/create operation with a new idempotency identity.

The baseline recovery problem is:

```text
409 Conflict
code: secret.delivery_not_replayable
Location: <stable credential/resource metadata URI when applicable>
```

The response MAY include safe metadata identifying the completed logical resource and the allowed recovery action, but never the lost secret.

### Lockout-safe credential rotation

An endpoint that can replace or invalidate a currently usable credential SHALL define **credential continuity** separately from one-time presentation.

A rotation/reissue contract MUST NOT invalidate the caller's only usable authority before the platform can prove one of these recovery-safe conditions:

- a distinct still-valid principal/session/credential with sufficient authority can perform the required recovery action;
- the old credential remains valid during a bounded staged/overlap cutover until a separately authorized activation/confirmation step safely retires it;
- an accepted privileged recovery authority independent of the lost new secret can rotate/reissue or create replacement material.

A nominal endpoint named `rotate`, `reissue`, `revoke` or `create` is not by itself proof of recovery. The endpoint contract SHALL identify **which surviving authority** can invoke the recovery path after the secret-bearing response is lost.

`revoke -> create` is only a valid recovery strategy when the caller or operator still has separate current authority to execute the create step. If revocation would remove the sole authority needed to create a replacement, that flow is prohibited as a lockout-prone contract.

Where product/security policy intentionally requires immediate old-credential invalidation, the operation MUST require/prove alternate recovery authority before admission rather than discovering after commit that the caller is locked out.

This exception changes only replay representation and credential-delivery continuity; it does not weaken atomic admission, deduplication, current authorization, audit or result-linkage requirements.

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

A retry after response loss SHALL discover/replay the committed result rather than execute the mutation again. For one-time-secret operations, the committed safe result linkage explicitly excludes the secret material and follows the recovery rule above.

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

`If-Match` is parsed once under the accepted protocol-defined list/cardinality semantics before application precondition logic. Duplicate field lines or proxy/application parsing differences cannot produce competing effective preconditions. Security-relevant preconditions cannot be introduced through request trailers.

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

Canonical HTTP ingress ensures all hops agree that this is the same method, resource target, idempotency key and precondition before either race-control mechanism executes.

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

Generic HTTP method override cannot convert an endpoint not designed for PATCH into a PATCH mutation path.

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

## Canonical ingress fault tests

Effectful/idempotent endpoints SHALL test, through the deployed edge/application path where applicable:

- duplicate/conflicting `Idempotency-Key` rejected before claim creation;
- `Idempotency-Key` in a request trailer cannot create/override the admitted key;
- method override cannot change the operation after routing/cache/idempotency interpretation;
- ambiguous request-target/authority cannot move one key into a different logical operation scope;
- duplicate/multi-line `If-Match` has one accepted protocol interpretation or is rejected;
- conflicting framing/content coding cannot make the claim fingerprint cover bytes/semantics different from the use case;
- canonical-ingress rejection creates no durable claim/effect.

## SDK retry policy

Future generated/official SDKs SHALL derive automatic retry behavior from operation metadata.

An SDK MUST NOT automatically retry an effectful operation solely because it received a network timeout. Automatic retry is permitted only when the method/endpoint is intrinsically retry-safe or a valid idempotency/operation contract makes replay safe.

For one-time-secret operations, SDKs MUST treat `secret.delivery_not_replayable` as a recovery state requiring an explicit user/application decision; they MUST NOT automatically issue a replacement secret operation.

SDKs cannot assume that a malformed/ambiguous transport request created an idempotency claim; they should construct a new valid canonical request rather than replaying transport ambiguity.