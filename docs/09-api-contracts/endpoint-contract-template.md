# Canonical Endpoint Contract Template

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Purpose

Every externally consumed endpoint/use case SHALL be designed from this template or an equivalent machine-validated representation before implementation is considered contract-ready.

The template exists to prevent hidden assumptions from becoming permanent compatibility debt.

---

# `<operation_id>` — `<human title>`

## Contract metadata

```text
Status: proposed | accepted | deprecated | superseded
API surface: machine-api | bff | public | callback | realtime-admission
Major version: v1
Owner domain: <accepted bounded context>
Use case: <stable application use case>
Traceability: <FR-* / INV-* / SEC-* / QA-* / ADR-* / design sections>
```

## HTTP contract

```text
Method: GET | POST | PATCH | PUT | DELETE | HEAD
Path: /api/v1/...
Operation ID: <domain.actionResource>
Content-Type: application/json (or explicit alternative)
```

## HTTP message/framing contract

Every HTTP endpoint inherits `http-message-framing-and-canonicalization.md` before authentication, tenant routing, idempotency, cache selection or protected effects.

Declare or inherit:

```text
HTTP message profile: <platform default | specialized accepted profile>
Body framing policy: <accepted profile>
Request-target profile: <accepted canonicalization profile>
Trusted proxy metadata policy: <platform profile | specialized profile>
Security-sensitive header cardinality: <declared below or inherited platform manifest>
```

An endpoint SHALL NOT weaken the platform rule that one accepted wire request has one canonical interpretation at every downstream hop.

Ambiguous `Content-Length`/`Transfer-Encoding`, conflicting body boundaries, conflicting authority/host meanings, malformed request-target normalization, or ambiguous security-sensitive header values fail closed before protected application logic consumes them.

If the surface requires raw-body verification (for example provider signatures), the exact bounded raw bytes associated with the already accepted framing are preserved for verification; framing canonicalization does not rewrite the signed body.

## Purpose

State the externally meaningful business/system behavior. Do not describe controller/service classes or SQL implementation.

## Actors

Allowed logical principal classes:

```text
human_browser_session
machine_api_principal
platform_admin_principal
internal_service_principal
scheduled/system_process
provider_callback_identity
```

State which are accepted and which are rejected.

For BFF/browser endpoints additionally declare:

```text
Credentialed cross-origin allowed: no | explicit allowlist only
Origin/CORS profile: <accepted profile or OPEN profile reference>
CSRF required for state change: yes | no/not applicable
```

Wildcard credentialed browser origins are prohibited. Origin/CORS enforcement is never authorization.

## Tenant/global scope

```text
Tenant requirement: none | required | explicit cross-tenant privileged
Tenant source: path | trusted integration mapping | platform operation target
Physical placement input from caller: prohibited
```

For tenant-scoped routes, document where trusted placement is resolved and where authoritative membership/resource authorization occurs. If membership/resource policy is cell-owned, placement resolution -> authoritative routing -> cell admission -> trusted TenantContext -> request-contract validation MUST precede the owning authorization decision. Earlier ingress/global checks are narrowing/fail-fast only.

Explain any legitimate global scope.

## Authorization

```text
Action: <domain.resource.verb>
Scope: platform | tenant | resource/group refinement
Step-up: none | policy-driven | required
Audit class: none | normal | privileged | security-critical
Existence concealment: yes | no | conditional
Owning authorization authority: <cell/domain/control-plane authority>
Authorization input fields: <validated path/query/body/resource identifiers consumed by policy>
```

Define any resource-level scope rules and distinguish ingress/global prechecks from the final owning authorization decision. Caller-controlled authorization/resource-scope inputs MUST be validated under the trusted route/TenantContext before the owning policy consumes them.

## Request

### Path parameters

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `tenant_id` | opaque string | yes/no | Logical tenant scope, never placement authority |

### Query parameters

Document allowlisted fields/operators, defaults and maximum complexity.

For every query parameter also declare its data classification and whether URL placement is safe. Confidential/restricted search/filter values SHALL NOT be forced into query strings merely because the transport supports them. Where protected query input is required, use a bounded body-based query contract, server-side opaque query handle or equivalent reviewed representation that avoids browser/history/referrer/log exposure.

### Headers

Declare applicable headers and their canonical cardinality/combine semantics:

```text
Header: Authorization
Cardinality: strict_singleton

Header: Idempotency-Key
Cardinality: strict_singleton

Header: If-Match
Cardinality: protocol_defined_list | not_applicable

Header: X-Correlation-Id
Cardinality: strict_singleton | not accepted

Other accepted authentication/content-negotiation/range/provider headers:
<header> -> strict_singleton | protocol_defined_list | multi_value_with_canonical_rule
```

`Authorization` and `Idempotency-Key` cannot reach protected logic with competing values. Security-sensitive duplicate fields without an explicit protocol-defined canonical rule are rejected rather than resolved by arbitrary first/last/framework behavior.

For BFF cookie-authenticated flows, declare the accepted cookie/session/CSRF parsing profile. Duplicate security-relevant cookie names cannot produce different authentication/CSRF outcomes across edge and application parsers.

### Body schema

Define typed request fields and semantics.

For each field specify:

- type/format;
- required/optional;
- nullable or not;
- bounds;
- enum open/closed classification;
- data classification;
- whether mutable/immutable;
- semantic validation.

Unknown request fields: rejected unless an explicit extension namespace is defined.

## Request limits

```text
Maximum body bytes: <value/policy>
Maximum item count: <value/policy>
Maximum string/list depth/size: <value/policy>
Maximum header bytes/count: <value/policy or OPEN platform profile>
Timeout/deadline class: <policy>
Query complexity class: <policy>
```

If a numeric limit is not yet accepted, mark it `OPEN` rather than implying unlimited.

## Consistency

Choose/document:

```text
committed_authoritative
accepted_async
stale_tolerant_projection
historical_window
reconciliation_required_possible
```

Explain read-after-write expectations where material.

## Transaction/effect boundary

State:

- authoritative owner;
- local transaction scope;
- external effects, if any;
- outbox/audit obligations;
- whether a durable operation is created.

No external network call is assumed to be part of an ordinary local database transaction.

## Idempotency

```text
Class: none | optional | required | intrinsic
Effective server-derived scope: <description>
Fingerprint fields: <semantic request fields>
Completed replay behavior: <status/result>
In-progress duplicate behavior: <409 or same 202 operation>
Different-fingerprint behavior: 409 idempotency.key_reused
Retention/recovery window: <accepted policy or OPEN>
One-time-secret response: none | initial-presentation-only
Secret response-loss recovery: <not applicable | safe metadata + explicit rotate/reissue/create/revoke flow>
Surviving recovery authority: <not applicable | concrete still-valid authority/staged overlap/privileged recovery>
Credential cutover semantics: <not applicable | non-disruptive create | staged overlap | immediate with proven alternate authority>
```

For external effects, describe stable `operation_id` / reconciliation behavior.

If the endpoint creates/rotates/reissues non-retrievable secret material, document that the secret is excluded from idempotent replay state, a same-key response-loss retry cannot recreate the effect or re-present the secret, and the explicit authorized recovery action does not require possession of the lost secret. If the operation can invalidate an existing credential, prove which still-valid authority survives to recover or use a staged/overlap cutover; a nominal recovery endpoint without usable authority is insufficient.

## Optimistic concurrency

```text
Required: yes | no
Validator: ETag / opaque revision
If-Match required: yes | no
Missing precondition: 428 concurrency.precondition_required
Mismatch: 412 concurrency.revision_mismatch
```

Explain why concurrency is or is not required.

## Success responses

List every normal success status and schema.

Example:

```text
201 Created -> <Resource>
202 Accepted -> <Operation>
204 No Content -> no body
```

Define `Location` behavior when applicable.

For a secret-bearing success, explicitly identify the one-time secret field(s), response cache class `no_store`, logging/redaction restrictions and response-loss behavior.

For any endpoint that uploads, returns, previews, streams or delegates artifact/binary bytes, additionally declare:

```text
Browser delivery applicable: yes | no
Browser delivery profile: opaque_download | safe_inline | active_inline_isolated | not_applicable
Authoritative media-type source: <server-controlled validation/classification policy>
Caller filename/extension/Content-Type trusted for browser execution: no
Safe download-name policy: <server-derived canonical/fallback policy>
Content-Disposition filename semantics: <single logical filename; coherent filename/filename* profile>
MIME sniffing: prohibited / nosniff-equivalent
Active-content origin isolation: required | not applicable
Ambient application/BFF credentials on active-content origin: prohibited | not applicable
Delegated delivery capability scope: <artifact/delivery-generation bound or not applicable>
Untrusted server-side content processing: none | isolated_bounded
Processing boundary: <isolated parser/renderer/worker profile or not applicable>
Processing secret access: none | narrowly scoped explicit capability
Processing egress: denied/restricted under accepted outbound policy
Expansion/resource limits: <bytes/nesting/members/CPU/memory/time/output policy or OPEN with implementation blocked>
Archive extraction containment: <staging-root confinement/no traversal/symlink/device escape or not applicable>
XML active external resolution: disabled | isolated deny-by-default resolver | not applicable
Embedded macro/script execution: prohibited unless separately accepted
Embedded URL retrieval: prohibited except through accepted outbound/SSRF policy
Derived artifact classification: independent required | not applicable
```

Unknown/untrusted/browser-active content defaults to `opaque_download`. A caller-controlled upload media type, filename or extension never authorizes inline execution. The download name is server-derived under a canonical policy that removes control/bidi/path ambiguity, avoids misleading executable extensions and can fall back to a neutral server-generated name.

`active_inline_isolated` requires a dedicated untrusted-content browser boundary with no application/BFF ambient credential or DOM/service-worker trust and must preserve current authorization/releasability/delivery-generation/active-stream fencing.

Complex document/archive/media parsing, preview, conversion, extraction or rendering of untrusted bytes uses an isolated least-privilege bounded processing profile. It SHALL NOT run with ordinary API/BFF application secrets or unrestricted egress merely because the uploader is authorized. Archive/decompression expansion, recursion, CPU/memory/time and generated-output volume are bounded. Archive extraction cannot escape its staging root through absolute/parent paths, separator tricks, links or special files. XML/XML-derived parsing disables DTD/external entities/XInclude/external schema/stylesheet/resource resolution by default or uses an explicitly isolated deny-by-default resolver. A derived preview/conversion receives independent artifact identity/classification and does not inherit `safe_inline` automatically.

## Response cache contract

Every endpoint MUST choose a cache class:

```text
Class: no_store | private_revalidate | public_shared | artifact_delivery_guarded
Shared cache allowed: yes | no | only with proven guarded delivery
Variance dimensions: <public-safe dimensions or none>
Validator/revalidation: <ETag/conditional/none/policy>
Freshness/TTL: <accepted value/policy or OPEN>
Authorization re-evaluation before reuse: <required/not applicable>
Sensitive response fields: <none/list>
Protected error variants: <no_store/private policy>
```

Rules:

- the cache contract applies to success and error/conditional response variants;
- secret-bearing responses are always `no_store`;
- protected authentication/authorization/existence-concealing errors cannot become shared-cacheable by default;
- protected API/BFF responses cannot become shared-cacheable from framework/CDN defaults;
- `Vary` or equivalent keying is not authorization;
- `public_shared` requires a deliberately public projection independent of protected caller authority;
- protected artifact caching must preserve current authorization/releasability/delivery-generation/active-stream fencing and browser-delivery profile or fall back to non-shared behavior;
- cache/proxy keying MUST consume the same canonical host/path/query/header semantics accepted by the owning service; ambiguous requests are not cache candidates.

Exact public/private lifetime tuning may remain `OPEN-API-017`; absence of an accepted cache contract blocks implementation.

## Error contract

List stable problem codes that callers may branch on.

Minimum classes considered:

```text
authentication.*
authorization.*
resource.not_found
validation.*
concurrency.*
idempotency.*
secret.delivery_not_replayable
rate_limit.*
dependency.*
domain-specific conflicts
```

Do not expose raw database/provider exception text.

Transport/framing ambiguity errors are intentionally sparse and SHALL NOT reveal which parser/hop would have interpreted the rejected message differently.

## Retry contract

State:

```text
Automatic retry safe: yes | no | only with valid idempotency key
Safe statuses/classes: <documented>
Ambiguous external outcome: <operation/reconciliation behavior>
One-time-secret response loss: <not applicable | explicit non-replayable recovery>
Retry-After: may/shall/not used
```

A request rejected before canonical message acceptance does not create an idempotency claim or imply that a protected effect executed.

## Long-running operation

If applicable:

```text
Operation type: <name>
Operation URI: /api/v1/.../operations/{operation_id}
Cancellation supported: yes/no
Terminal states: <subset>
Result resource: <type/reference>
Operation read authority: <current action/scope>
Cancel/retry/resume authority: <current action/scope>
Result dereference authority: <current target-resource action/scope>
```

`operation_id`/URL is never bearer authority. Poll/cancel/retry/resume/result access re-establishes current tenant/principal/resource authorization.

## Pagination/filter/sort

For collection endpoints:

```text
Default sort: <deterministic order>
Cursor mode: live | snapshot-like | historical-window
Allowed filters: ...
Allowed sorts: ...
Allowed includes: ...
Default limit: <value/policy>
Maximum limit: <value/policy>
Total count: absent | exact | approximate | optional
Current authorization re-evaluated on each page: yes
Cursor security binding: <tenant/query/sort plus any needed principal/scope dimensions>
Cursor payload confidentiality: <no protected payload | server-side opaque handle | confidential+integrity-protected envelope | equivalent>
Cursor URL/logging policy: <redacted/hash/reference; no raw protected cursor logging/referrer propagation>
Sensitive query parameters allowed in URL: <no | explicit public/non-sensitive allowlist>
```

A cursor/snapshot/watermark never freezes authorization. Each protected continuation request re-establishes current authority, and included/bulk items remain independently authorized where required.

"Opaque" does not mean confidential. If cursor state would reveal protected tenant/filter/search/last-item data through URL/history/log/referrer exposure, use confidentiality protection or server-side state. Base64/signing alone is insufficient for protected cursor payloads.

## Data classification

Classify request/response fields:

```text
public
internal
confidential
restricted/credential
regulated/PII where applicable
```

Declare redaction/logging restrictions.

## Audit

State:

- audit required or not;
- actor/tenant/action/resource/outcome fields;
- whether audit record/intent must commit atomically with mutation;
- high-risk reason/approval/step-up metadata where applicable.

## Observability

Declare:

```text
request_id required
correlation_id propagation
operation_id linkage
tenant-safe metrics/log dimensions
provider/external-call linkage where applicable
http message/framing rejection telemetry where applicable
```

No secrets in observability payloads. Raw protected cursor/query values are not logged merely because they appear in the URL. Rejected ambiguous requests log safe rejection classes rather than competing credential/header/body values.

## Compatibility classification

Classify externally important fields/enums and security/behavior policy dimensions. Document:

- open/closed enum behavior;
- additive evolution options;
- known future extension points;
- deprecated aliases, if any;
- what would require a new major;
- whether changing authorization/scope/idempotency/retry/consistency semantics is breaking;
- whether changing HTTP framing/header cardinality/trusted-proxy/request-target interpretation is security-sensitive;
- whether changing response cache class, shared-cache eligibility, variance or current-authorization revalidation is breaking/security-sensitive;
- whether weakening cursor confidentiality/URL-redaction semantics is security-sensitive;
- whether changing browser-delivery/media-type/safe-filename/active-content-isolation or untrusted-content-processing semantics is security-sensitive or breaking for supported clients.

A framing/canonicalization, cache, cursor confidentiality, artifact browser-delivery/safe-filename or untrusted-content-processing policy becoming more permissive is never treated as an implementation-only optimization.

## Security abuse cases

List relevant abuse/failure cases such as:

- conflicting `Content-Length`/`Transfer-Encoding` or multiple body lengths;
- duplicate/conflicting `Authorization`, `Idempotency-Key` or other security-sensitive singleton input;
- conflicting `Host`/authority/trusted-forwarding metadata;
- malformed/ambiguous request target causing gateway/service route disagreement;
- HTTP-version translation causing edge/application interpretation mismatch;
- wrong tenant ID;
- known resource ID from another tenant;
- authorization attempted against stale/wrong cell placement;
- authorization consuming unvalidated caller-controlled resource/scope fields;
- revoked principal;
- stale revision;
- duplicate idempotency key;
- lost one-time-secret response;
- secret rotation with no surviving recovery authority;
- shared-cache cross-principal/tenant leakage;
- protected error cache leakage;
- stale cursor after authority revocation;
- cursor exposing confidential filter/search/resource state through URL/history/log/referrer;
- confidential query/search value placed directly in URL;
- operation ID used as bearer authority;
- wildcard/untrusted credentialed BFF origin;
- browser-active artifact executing on application/BFF origin;
- forged upload media type/filename causing inline execution or ambiguous/misleading download naming;
- Unicode bidi/control/path/double-extension filename deception;
- malicious archive/document causing parser RCE, SSRF, XXE, path traversal or expansion/resource exhaustion;
- generated preview incorrectly trusted as safe inline content;
- oversized body;
- expensive filter/include abuse;
- replayed callback/ticket;
- callback-supplied SSRF target;
- XML callback attempting local-file/network external-entity/include/schema resolution;
- provider outage;
- cross-tenant existence probing.

## Contract tests

List mandatory tests including happy path and invariant/fault cases.

At minimum, externally reachable endpoints test the applicable canonical HTTP ingress cases from `http-message-framing-and-canonicalization.md`, including cross-hop/protocol-translation behavior when infrastructure introduces multiple HTTP parsers.

At minimum, protected mutation endpoints test:

- conflicting framing rejected before authentication/idempotency/effect;
- duplicate/conflicting authentication/idempotency headers cannot reach protected logic with competing values;
- gateway and owning service consume one canonical request target/authority interpretation;
- authorized success;
- unauthenticated denial;
- wrong-tenant denial;
- authoritative placement/routing + trusted request-contract validation before cell-owned authorization where applicable;
- authorization policy does not consume unvalidated caller-controlled scope/resource fields;
- insufficient permission;
- validation bounds;
- idempotency/concurrency where applicable;
- one-time-secret response-loss behavior where applicable;
- lockout-safe surviving recovery authority/cutover where secret rotation can invalidate existing authority;
- response-cache headers/semantics and cross-principal/tenant non-reuse, including protected error variants;
- compatibility tests for cache-policy changes;
- current authorization on pagination/operation continuation where applicable;
- cursor confidentiality and URL/logging non-disclosure where applicable;
- sensitive filter/search query values are not forced into URL-visible transport when classified protected;
- BFF origin/CORS/CSRF behavior where applicable;
- callback outbound-fetch/SSRF boundary where applicable;
- callback XML profiles reject active external resolution/local-file/network entity behavior where applicable;
- audit/operation linkage;
- safe error leakage;
- retry after response loss where applicable.

Artifact/binary endpoints additionally test, where applicable:

- uploader-controlled filename/extension/media type cannot force executable inline delivery;
- unknown/untrusted/browser-active content falls back to attachment/non-sniffable download semantics;
- CRLF, controls, bidi, separators, reserved/special names and misleading extensions cannot create ambiguous or deceptive `Content-Disposition` names;
- `filename`/`filename*` (when both emitted) resolve to the same logical safe name without duplicate/conflicting parameters;
- safe fallback naming works when attacker metadata cannot be normalized safely;
- `safe_inline` accepts only the explicitly allowlisted validated content classes;
- `active_inline_isolated` does not receive application/BFF ambient credentials or origin/service-worker trust;
- delegated active-content delivery remains bound to the intended artifact/delivery generation and cannot become a general API credential;
- range/resume/CDN paths preserve the same browser-delivery classification and current artifact fencing;
- malicious archive/document expansion is bounded and cannot consume unbounded CPU/memory/time/output;
- archive extraction cannot escape staging root through path traversal, absolute paths, links or special files;
- parser/renderer processing cannot access ordinary application secrets or unrestricted network destinations;
- XML/XML-derived processing cannot resolve local/network external entities/includes/schemas unless an explicitly accepted isolated resolver profile exists;
- embedded scripts/macros/URLs are not executed/fetched implicitly;
- derived preview/conversion output is independently identified/classified before inline delivery.

## OPEN items

Explicitly list unresolved items. An omitted decision is not silently considered accepted.

## Evolution notes

Explain how this contract remains stable if:

- the domain is extracted into a service;
- tenant moves cells/regions;
- storage engine changes;
- provider adapter changes;
- client types multiply;
- request volume/cardinality grows substantially;
- gateway/reverse proxy/HTTP version changes while canonical request semantics stay equivalent;
- a CDN/reverse proxy/cache layer is added or replaced;
- cursor implementation moves between server-side state and a protected self-contained envelope;
- artifact delivery moves to a dedicated untrusted-content origin or another equivalent browser-isolation mechanism;
- artifact parsing/preview/conversion moves to a different isolated runtime or vendor without changing external artifact identity/contract.