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

Possession of an `operation_id` or operation URL is **not bearer authority**. Every protected read, poll, cancel, retry/resume or result-access request re-establishes current authentication, tenant context and applicable authorization under the owning operation contract.

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

Fields are operation-type-specific where necessary. Sensitive internal worker/provider details are not exposed by default. Principal/actor metadata is exposed only when the caller is authorized to see it under the operation's data-classification contract.

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

A result reference does not grant authority to the result resource. Access is reauthorized under the result resource's current contract at dereference/download time.

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

Every poll is a new protected read and re-evaluates current authorization. An operation created while a principal had access does not remain readable after that authority is revoked unless a separately accepted policy grants continuing access.

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

Cancellation requires current authorization at the time of the command. `requested_by` metadata or authority that existed at operation creation is not a durable cancellation grant.

## Resumption/retry

Clients do not create a new operation merely because polling observed `waiting` or `reconciliation_required`.

A retry/restart command is allowed only when the owning operation type exposes one and when current durable state proves a new attempt is safe.

Retry/resume also re-establishes current authorization; stale operation ownership or a persisted request-time grant is insufficient.

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
  "download_name": "report.pdf",
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

`content_type`, browser-delivery classification and `download_name` are server-controlled delivery metadata. A client-supplied upload `Content-Type`, filename or extension is untrusted input and SHALL NOT by itself authorize browser execution, determine the delivered media type, or become the response filename without the safe-name policy below.

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
3. validates the request/resource contract;
4. checks current authorization;
5. verifies the artifact is currently releasable;
6. establishes the accepted browser-delivery/media-type and safe-download-name profile for the artifact;
7. acquires the accepted generation-bound active-delivery lease/fence before the first protected byte;
8. streams or delegates delivery only through a mechanism preserving equivalent authorization, browser-isolation and revocation/fencing semantics.

The logical API contract remains stable if the implementation later moves between application streaming, CDN/object-storage proxying or another mechanism.

A direct vendor signed URL MAY be used internally only when it satisfies the accepted prompt-revocation, delivery-generation, active-stream and browser-delivery isolation invariants. Vendor URL shape is never the canonical artifact identity.

Protected artifact delivery uses the `artifact_delivery_guarded` cache class unless an endpoint deliberately proves stricter `no_store` behavior. A CDN/cache hit SHALL NOT bypass current authorization, releasability, delivery-generation admission, active-stream fencing, safe-download-name policy or the artifact's browser-delivery profile.

## Untrusted artifact processing boundary

Media classification, archive inspection, preview generation, document conversion, metadata extraction, thumbnailing and similar processing of user/provider-supplied bytes are security-sensitive parser/renderer operations. They SHALL NOT be treated as safe merely because the artifact was authenticated, uploaded by an authorized user or stored successfully.

When an operation invokes complex or active-content parsers/renderers, its contract SHALL identify an accepted processing profile that provides, as applicable:

- an isolated least-privilege execution boundary separate from ordinary API/BFF business runtime;
- no platform/application secret access unless a narrowly scoped processing capability is explicitly required;
- no unrestricted network/metadata-service/private-control-plane egress;
- CPU, memory, wall-time, input, decompressed/expanded-output, nesting/member-count and generated-output bounds;
- no implicit execution of macros/scripts/embedded programs;
- no automatic retrieval of attacker-controlled embedded URLs outside the accepted outbound/SSRF policy;
- deterministic failure/timeout behavior that cannot mark partially processed bytes as trusted/safe;
- safe temporary-file/storage lifecycle and cleanup under tenant/artifact identity;
- structured/redacted diagnostics with no raw secret or unrestricted document-content leakage.

Archive/decompression and nested-content processing remain bounded against expansion bombs and recursive parser abuse.

### Archive extraction identity and containment

Archive processing SHALL establish one canonical logical member-name model **before** inspection/materialization decisions are trusted.

For every archive member, the processing profile canonicalizes the destination identity under the semantics relevant to the actual staging filesystem and later consumers, including as applicable:

- Unicode normalization;
- case-folding/case-sensitivity behavior;
- path separator conversion;
- leading/trailing dot/space behavior;
- platform-reserved names;
- relative/absolute path interpretation.

The archive is rejected if two input members:

- have the same raw logical name when duplicates are not explicitly part of a safe format contract;
- normalize/case-fold/convert to the same canonical destination;
- alias the same file through path spelling differences;
- create file-versus-directory or link-versus-file type collisions;
- would cause an earlier inspected/scanned member to be overwritten or shadowed by later bytes.

Containment also requires every materialized path to remain inside the intended staging root: absolute paths, parent traversal, separator tricks, symlink/hardlink escape, device/special files and equivalent filesystem redirection SHALL NOT write outside the accepted artifact-processing boundary.

Materialization uses safe no-follow semantics and atomic create/no-replace behavior (or an equivalent primitive) so a validated member cannot change target/type between validation and creation and a later archive entry cannot silently replace a previously inspected file.

A scanner/classifier and any later parser/consumer SHALL observe the same canonical member identity and bytes. A pipeline that scans one alias and executes/parses another colliding alias is prohibited even when both remain inside the staging root.

## XML and structured active resolution

XML/XML-derived document processing SHALL **reject DTD declarations by default** and disable external entities, XInclude, external schema/stylesheet/resource resolution and equivalent active external-resolution features.

If a specific format genuinely requires a DTD, trusted schema/catalog or another active dependency, it SHALL use a separately reviewed profile with pinned local resources or an explicitly isolated deny-by-default resolver; attacker-controlled declarations/URIs SHALL NOT gain local-file or network authority. Parser/library upgrades cannot silently re-enable DTDs or active resolution.

A generated preview/converted result receives its own artifact identity/version/classification and browser-delivery profile. It does **not** inherit `safe_inline` merely because an internal renderer produced it. The output must independently satisfy the accepted delivery classification before inline release.

Exact parser/renderer/sandbox/antimalware products are implementation choices; the isolation and bounded-processing properties are contract/security requirements when such processing exists.

## Browser delivery safety and active content

Authorization to download protected bytes is **not** authorization for those bytes to execute in the first-party browser security origin.

Every browser-reachable artifact content contract SHALL classify delivery using an accepted profile equivalent to:

```text
opaque_download
safe_inline
active_inline_isolated
```

### `opaque_download`

This is the default for:

- user/provider supplied content that has not been proven browser-inert;
- unknown/unrecognized media types;
- script-capable/browser-active formats;
- any artifact whose inline execution safety is uncertain.

The response SHALL use a server-controlled authoritative media type. Unknown content defaults to a non-executable generic binary media type rather than inheriting a client-controlled type.

Browser delivery SHALL use `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff` or equivalent browser-enforced behavior. User-controlled filename/media metadata SHALL NOT be able to inject response headers or opt the object into inline execution.

### Safe download filename contract

A filename shown/saved by browsers or operating systems is a security-relevant presentation surface, not merely cosmetic metadata.

The server SHALL derive a canonical safe `download_name` from trusted artifact identity/media classification plus optionally sanitized user-facing metadata. It SHALL always be able to fall back to a server-generated neutral name that does not depend on attacker-controlled text.

Before use in `Content-Disposition`, filename metadata SHALL be processed under one unambiguous policy that:

- applies a defined Unicode normalization profile before security checks;
- rejects/removes control characters, CR/LF/NUL, bidi overrides/isolates and other directionality/control code points that can create misleading display;
- strips or replaces path separators, drive/UNC syntax, dot-segments and other path interpretation characters;
- avoids platform-reserved/special device names and dangerous leading/trailing dot/space forms;
- prevents attacker-controlled double/misleading executable extensions from contradicting the authoritative delivered media class; the safe extension is server-derived from the accepted content classification or omitted;
- produces one logical filename value, without duplicate/conflicting `Content-Disposition` parameters;
- when both `filename` and `filename*` are emitted, uses a conservative ASCII fallback plus an encoded international form that represent the same normalized logical name rather than attacker-controlled alternatives;
- escapes/encodes header syntax so quotes, semicolons, percent-encoding or Unicode cannot create response splitting or parameter ambiguity.

Original uploaded filenames MAY be retained as separately classified metadata for authorized UI display/audit where useful, but they are not automatically the download header value.

If safe normalization cannot produce an unambiguous name, the server-generated fallback is used.

### `safe_inline`

Inline rendering is allowed only for explicitly allowlisted content classes whose browser behavior is accepted for the target surface and whose authoritative media type/content classification has been established independently from caller-controlled upload metadata.

`safe_inline` is not a generic fallback for "the browser seems able to display it". If the platform cannot prove the accepted inline class, delivery falls back to `opaque_download`.

### `active_inline_isolated`

Browser-active/script-capable content MAY be rendered inline only when Product actually requires the capability and a dedicated security profile has been accepted.

That profile SHALL use an isolated untrusted-content browser origin or equivalent browsing boundary that:

- does not share first-party application/BFF ambient session cookies or credential authority;
- does not share service-worker/DOM origin trust with the application/BFF surface;
- prevents persistent browser state, storage, service-worker control or same-origin authority from crossing tenant/artifact/principal security boundaries unless an explicitly reviewed design proves equivalent isolation;
- cannot use the artifact response itself to gain application/BFF authorization;
- applies a restrictive sandbox/content-security/navigation/opener/referrer/cross-origin policy appropriate to the active format;
- preserves current artifact authorization, releasability, delivery-generation admission and active-stream fencing before and during protected release.

A sandboxed opaque/unique origin or an equivalent isolation mechanism is preferred when the browser capability permits it. A single shared active-content origin that allows one artifact to install persistent state/service-worker control over unrelated future tenant/artifact content is not an accepted isolation boundary.

If a capability or delegated URL is used to bridge the authenticated application to the isolated content origin, it is bounded to the intended artifact/delivery generation and SHALL NOT become a general API credential. A reusable bearer credential SHALL NOT remain readable in active-document URL/state after protected delivery admission. Where a browser-visible capability is unavoidable, it SHALL be redeemed/burned or otherwise rendered unusable for subsequent protected access before active content can exploit it, and the delivery profile SHALL prevent referrer/log/history-like propagation from re-exposing it.

The exact isolated hostname/origin, capability representation and sandbox/header composition are deployment/profile choices and remain OPEN until an active-inline product use case exists. The **isolation property is not OPEN**.

Browser-active protected content SHALL NOT execute inline on an application/BFF/session-bearing origin merely because the caller is authorized to download it.

## Range/resume

Byte-range/resumable download support MAY be added per artifact class. If supported, every resumed request re-enters current authorization/releasability/delivery-generation admission and the same browser-delivery/safe-name profile; an old range request does not bypass current erasure fencing or active-content isolation.

## Delayed export/report authorization

User-requested export/report operations reauthorize before protected execution and again before artifact release according to the accepted security baseline.

The fact that an artifact was generated for a user does not grant permanent download authority after membership/permission/tenant access is revoked.

Generated report/preview content that is browser-active follows the same delivery classification and isolation rules as uploaded attachments; provenance from an internal generator does not implicitly make arbitrary HTML/SVG-like output safe to execute on the application/BFF origin.

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

Upload/staging validation SHALL treat declared filename/media type as untrusted metadata. A staged object does not become `safe_inline` or `active_inline_isolated` merely because the uploader declares a browser media type. Any complex archive/document parsing required by import follows the untrusted artifact processing boundary above, including canonical archive-member collision rejection and safe no-follow/no-replace materialization.

## Governed deletion/erasure

Deletion/erasure of an artifact that spans metadata and object storage uses a durable operation/resource state. The API SHALL NOT report confirmed erasure until the accepted upload-publication, delivery capability/lease/active-stream and governance/legal-hold reconciliation conditions have passed.

If state is uncertain, the external operation remains non-terminal/reconciliation-required rather than returning a false success.

## Maximum-state rule

Operation and artifact contracts SHALL remain valid when worker implementation, queue vendor, object store, cell placement, browser-delivery origin, parser/renderer/archive implementation, filesystem semantics or process decomposition changes. A client tracks logical `operation_id` / `artifact_id`, never the transient execution mechanism.

Changing archive/parser/runtime/filesystem implementation SHALL NOT weaken canonical member identity, collision rejection, staging-root containment or scanner-to-consumer byte equivalence.