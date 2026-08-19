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
Content-coding policy: <accepted profile | none>
Connection rejection policy: <accepted platform profile>
Method override policy: denied-by-default | explicitly accepted profile
Request trailer policy: deny security-sensitive authority | specialized non-security profile
Request-target profile: <accepted canonicalization profile>
Query decoding/multiplicity profile: <accepted canonicalization profile>
Structured request entity profile: <canonical JSON | canonical multipart | explicit media-specific profile | not applicable>
Trusted proxy metadata policy: <platform profile | specialized profile>
Security-sensitive header cardinality: <declared below or inherited platform manifest>
Response header profile: <platform safe-response-header profile | specialized accepted profile>
```

An endpoint SHALL NOT weaken the platform rule that one accepted wire request has one canonical interpretation at every downstream hop.

Ambiguous framing, conflicting authority, malformed target/query decoding, duplicate singleton query values, method-override ambiguity, security-sensitive trailers, content-coding disagreement, unsafe connection reuse or ambiguous security-sensitive headers fail closed before protected application logic consumes them.

If the surface requires raw-body verification, the exact bounded raw bytes associated with the accepted framing are preserved for verification; canonicalization SHALL NOT silently rewrite the signed body before verification.

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

For tenant-scoped routes, canonical path/query decoding occurs before placement resolution. If membership/resource policy is cell-owned, placement resolution -> authoritative routing -> cell admission -> trusted `TenantContext` -> request-contract validation MUST precede the owning authorization decision. Earlier ingress/global checks are narrowing/fail-fast only.

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

Caller-controlled authorization/resource-scope inputs MUST be validated under the trusted route/`TenantContext` before the owning policy consumes them.

## Request

### Path parameters

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `tenant_id` | opaque string | yes/no | Logical tenant scope, never placement authority |

Path fields are extracted only from the canonical request target established at ingress. The endpoint SHALL NOT depend on framework-specific re-decoding/collapse semantics after placement routing.

### Query parameters

Document allowlisted fields/operators, defaults, classification, maximum complexity and multiplicity.

For every query parameter declare:

```text
Multiplicity: singleton | repeated_list_with_canonical_rule | comma_list_under_singleton | not_accepted
Duplicate behavior: reject | <explicit canonical rule>
Order significance: yes/no/not_applicable
Maximum repeated values: <bound/policy>
URL visibility classification: public/non-sensitive | protected/non-URL
```

Duplicate singleton parameters are rejected. Alternate encodings that normalize to the same logical key participate in the same duplicate detection. A query field SHALL NOT have first-value semantics at one hop, last-value semantics at another and list semantics at another.

Confidential/restricted search/filter values SHALL NOT be forced into query strings. Use a bounded body-based query contract, server-side opaque query handle or equivalent reviewed representation when protected query input is required.

### Headers

Declare applicable headers and canonical cardinality/combine semantics:

```text
Header: Authorization
Cardinality: strict_singleton

Header: Idempotency-Key
Cardinality: strict_singleton

Header: If-Match
Cardinality: protocol_defined_list | not_applicable

Header: X-Correlation-Id
Cardinality: strict_singleton | not accepted

Other accepted headers:
<header> -> strict_singleton | protocol_defined_list | multi_value_with_canonical_rule
```

`Authorization` and `Idempotency-Key` cannot reach protected logic with competing values. Security-sensitive duplicates without an explicit protocol-defined canonical rule are rejected rather than resolved by arbitrary first/last/framework behavior.

For BFF cookie-authenticated flows, duplicate security-relevant cookie names cannot produce different authentication/CSRF outcomes across edge and application parsers.

Request trailers SHALL NOT introduce or override authentication/session, idempotency, routing, CSRF/Origin, conditional/precondition, callback-security or realtime authority after initial header admission.

### Body schema

Define typed request fields and semantics.

For each field specify:

- type/format;
- required/optional;
- nullable or not;
- bounds;
- enum open/closed classification;
- data classification;
- mutable/immutable;
- semantic validation.

Unknown request fields are rejected unless an explicit extension namespace is defined.

### Structured request entity canonicalization

A structured request body is not trusted merely because framing and media type are accepted. Before request-contract validation, owning authorization, idempotency fingerprinting or the use case consumes body fields, the endpoint SHALL establish **one canonical parsed entity** under the declared media profile.

For every accepted structured media type declare:

```text
Structured entity media type: <application/json | multipart/form-data | explicit profile>
Member/part-name normalization: <exact profile>
Duplicate member/part rule: reject | <explicit safe semantic rule>
Alias/collision rule: reject after canonical-name normalization
Nesting/container rule: <accepted deterministic profile>
Per-part header/cardinality rule: <multipart only or not applicable>
Boundary rule: <multipart only or not applicable>
Canonical entity propagation: required
```

The canonical entity rules are security requirements:

- **JSON:** duplicate object member names are rejected by default. Names that alias after the accepted Unicode/name-normalization profile are rejected. A parser/library SHALL NOT silently select first value, last value or merge duplicates for protected request fields. Number/string/Unicode handling used by validation/fingerprinting is deterministic under the accepted profile.
- **Multipart:** the outer boundary and every nested boundary are parsed once under one accepted grammar. Duplicate or aliasing security-relevant part names, conflicting per-part `Content-Disposition` names, conflicting per-part media metadata or ambiguous nested multipart structure are rejected unless the endpoint explicitly defines a safe repeated-part semantic. Part-name normalization and multiplicity are bounded and deterministic.
- **Other structured media:** XML, form encoding, protobuf-like, vendor-specific or future formats require an explicit canonical parse profile with equivalent duplicate/alias/name/nesting semantics before protected use.

Raw bytes MAY be retained separately where signatures/audit require them, but after canonical entity establishment the following consumers SHALL observe the **same logical entity**, not independently reparse attacker-controlled raw body bytes:

```text
request-contract validation
owning authorization policy inputs
resource/tenant-scope body inputs where permitted
idempotency fingerprint construction
optimistic-concurrency/body precondition inputs
callback semantic processing after authenticity verification
cache semantics when body participates in an accepted key
use-case/domain command mapping
```

If two accepted parsers could derive different body fields, the request fails closed before owning authorization or protected effect. Parsing once and then handing different independently reparsed raw representations to later layers is prohibited.

If `Content-Encoding`, multipart or another structured transfer is accepted, declare independent raw/decoded/parser bounds. Unsupported or ambiguously ordered decoding is rejected.

## Request limits

```text
Maximum raw body bytes: <value/policy>
Maximum decoded/decompressed bytes: <value/policy or not applicable>
Maximum structured members/parts: <value/policy or not applicable>
Maximum item count: <value/policy>
Maximum string/list/object depth/size: <value/policy>
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

State authoritative owner, local transaction scope, external effects, outbox/audit obligations and whether a durable operation is created.

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
Recovery continuity: <inherit platform (R,F] recovery quarantine/reconciliation | specialized accepted profile | not applicable>
One-time-secret response: none | initial-presentation-only
Secret response-loss recovery: <not applicable | safe metadata + explicit rotate/reissue/create/revoke flow>
Surviving recovery authority: <not applicable | concrete still-valid authority/staged overlap/privileged recovery>
Credential cutover semantics: <not applicable | non-disruptive create | staged overlap | immediate with proven alternate authority>
```

Idempotency admission begins only after canonical HTTP acceptance and canonical structured-entity establishment for fields used by the fingerprint. A raw body that could parse into two different logical entities cannot create a claim.

For external effects, describe stable `operation_id` / reconciliation behavior.

For effectful idempotent endpoints, recovery continuity inherits the accepted Gate B recovery model unless a stricter accepted profile applies. After restore/PITR/partial state loss or mismatched recovery generations, missing/older claim/result/tombstone state is **recovery uncertainty**, not proof that the operation never executed. Effectful admission remains quarantined/fail-closed until surviving operation/outcome/outbox-inbox/audit/provider/external-effect authorities establish the applicable `(R,F]` continuity boundary. The concrete backup/storage/generation mechanism is implementation-level; the no-blind-retry property is not.

If the endpoint creates/rotates/reissues non-retrievable secret material, the secret is excluded from replay state, same-key response-loss retry cannot recreate the effect or re-present the secret, and explicit recovery does not require possession of the lost secret. If the operation can invalidate an existing credential, prove a still-valid recovery authority or staged/overlap cutover.

## Optimistic concurrency

```text
Required: yes | no
Validator: ETag / opaque revision
If-Match required: yes | no
Missing precondition: 428 concurrency.precondition_required
Mismatch: 412 concurrency.revision_mismatch
```

`If-Match` follows one canonical protocol-defined parse meaning and cannot be introduced through trailers.

## Success responses

List every normal success status and schema.

```text
201 Created -> <Resource>
202 Accepted -> <Operation>
204 No Content -> no body
```

Define `Location` behavior when applicable.

For a secret-bearing success, identify the one-time secret fields, response cache class `no_store`, logging/redaction restrictions and response-loss behavior.

## Response header contract

Every emitted response header inherits or declares a safe response-header construction profile. Dynamic header values SHALL NOT be assembled by unvalidated string concatenation.

For every emitted dynamic or security-relevant header declare/inherit:

```text
Header: <name>
Grammar/profile: <protocol-defined or platform-defined grammar>
Cardinality: strict_singleton | protocol_defined_list | multi_value_with_canonical_rule
Value source: server-derived | validated caller/provider/resource metadata
Control characters: rejected
Serialization owner: <single authoritative layer/profile>
```

The profile SHALL prevent CR/LF/NUL/control injection, obsolete folding, field delimiter injection, duplicate singleton conflict and unsafe comma/semicolon/quoted-string composition. `Location`, `Link`, `ETag`, `Retry-After`, `Content-Disposition`, cache/security/CORS/authentication headers, request/correlation IDs and redirects use accepted grammars rather than arbitrary strings.

Proxy/BFF/CDN/application layers SHALL NOT independently append another conflicting singleton value. A response-header serialization failure after a business commit does not rewrite authoritative business truth; the client recovers through accepted idempotency/operation/read semantics.

## Artifact/binary response contract

For endpoints that upload, return, preview, stream or delegate artifact/binary bytes, additionally declare:

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
Archive member canonicalization/collision policy: <canonical names + duplicate/alias rejection + atomic no-replace or not applicable>
XML DTD policy: reject-by-default | separately accepted exceptional isolated profile | not applicable
XML external resolution: disabled | isolated deny-by-default resolver | not applicable
Embedded macro/script execution: prohibited unless separately accepted
Embedded URL retrieval: prohibited except through accepted outbound/SSRF policy
Derived artifact classification: independent required | not applicable
```

Unknown/untrusted/browser-active content defaults to `opaque_download`. Caller-controlled media metadata never authorizes inline execution. Download names are server-derived with a neutral fallback.

`active_inline_isolated` requires a dedicated untrusted-content browser boundary with no application/BFF ambient credential or DOM/service-worker trust and preserves current authorization/releasability/delivery-generation/active-stream fencing.

Complex untrusted parsing uses isolated least privilege with bounded resources and restricted egress. Archive extraction cannot escape staging root and establishes canonical member identity before materialization; duplicate/colliding Unicode/case/path/platform aliases are rejected and materialization is no-follow atomic/no-replace or equivalent. XML parsing rejects every DTD declaration by default and disables active external resolution unless a separately accepted isolated profile exists. Derived outputs receive independent identity/classification.

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

- cache contract applies to success, conditional, redirect and error variants;
- secret-bearing responses are always `no_store`;
- protected authentication/authorization/existence-concealing errors cannot become shared-cacheable by default;
- protected API/BFF responses cannot become shared-cacheable from framework/CDN defaults;
- `Vary` is not authorization;
- `public_shared` requires a deliberately public projection;
- protected artifact caching preserves current authorization/releasability/delivery-generation/active-stream/browser-delivery semantics;
- cache/proxy keying consumes the same canonical method/host/path/query/header/body semantics accepted by the owning service where body semantics participate in cache eligibility/keying.

Exact lifetime tuning may remain `OPEN-API-017`; absence of an accepted cache contract blocks implementation.

## Error contract

List stable problem codes callers may branch on:

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

Transport/framing/path/query/structured-entity ambiguity errors are deliberately sparse and SHALL NOT reveal which parser would have accepted an alternate interpretation.

## Retry contract

```text
Automatic retry safe: yes | no | only with valid idempotency key
Safe statuses/classes: <documented>
Ambiguous external outcome: <operation/reconciliation behavior>
One-time-secret response loss: <not applicable | explicit non-replayable recovery>
Retry-After: may/shall/not used
```

A request rejected before canonical message/entity acceptance does not create an idempotency claim or imply that a protected effect executed.

## Provider callback-specific contract

For `API surface: callback`, declare all of the following in addition to the generic request contract:

```text
Provider authentication profile: <provider-specific accepted profile>
Authenticated exact representation: <raw body / body+headers / protocol metadata profile>
Freshness evidence: <timestamp | nonce | sequence | provider metadata | none>
Freshness binding: <covered by authenticator | independently trusted protocol metadata | weaker-trust profile>
Freshness window/sequence policy: <accepted value/policy or OPEN-API-022>
Replay identity source: <canonical structured entity | authenticated protocol metadata | accepted platform identity>
Replay identity scope: <trusted tenant/integration/source dimensions>
Replay admission: atomic_create_or_observe
Durable coupling: <same authority transaction | durable inbox/work/effect linkage | stable operation reconciliation>
Replay retention: <accepted policy or OPEN-API-022>
Replay recovery continuity: <inherit platform (R,F] recovery quarantine/reconciliation | specialized accepted profile>
Cross-authority ambiguity: <durable reconciliation behavior>
Acknowledgement durability: <completed synchronously | durable async responsibility before success>
```

Rules:

- freshness evidence used for security is bound to the same authenticated callback instance; a clock-window check alone does not make unbound metadata authoritative;
- body-carried freshness/replay identity is derived from the same canonical structured entity used by callback/domain mapping;
- replay admission is atomic create-or-observe and produces one logical executor under concurrent delivery;
- replay admission cannot permanently consume an identity while required work has no durable responsibility unless a durable recoverable reconciliation state exists;
- if a cross-authority irreversible effect may have succeeded but its outcome is not yet durably recorded, the stable operation/replay state enters or remains in reconciliation and **no new effect attempt is admitted until authoritative reconciliation resolves the prior outcome**;
- replay retention expiry does not convert unresolved ambiguous irreversible work or still-supported recovery state into blind execution eligibility;
- after replay-store restore/PITR/partial loss or mismatched recovery generations, missing/older replay state is recovery uncertainty rather than `unused`; affected callback admission remains quarantined/fail-closed until surviving inbox/effect/provider-ack/audit/reconciliation authorities prove continuity, and a still-fresh authenticated retry cannot bypass that gate;
- callback success acknowledgement never precedes the declared required durable-responsibility boundary.

Exact authenticator algorithm, signed-header set, numeric window, replay storage product, retention duration, provider-facing acknowledgement status mapping, recovery-generation encoding and transaction/recovery topology remain `OPEN-API-022` or platform recovery-profile decisions until accepted for the provider profile.

## Realtime admission-specific contract

For `API surface: realtime-admission`, declare all of the following in addition to the generic HTTP/browser contract:

```text
Ticket scope: <principal + logical tenant + bounded realtime connection scope>
Ticket expiry policy: <accepted short-lived policy or OPEN profile reference>
Current authority checks: <current session/credential + membership/permission/tenant access>
Placement/admission generation check: <current required | not applicable>
Replay admission: atomic_shared_single_winner_consume
Burn-on-ambiguity: required
Replay recovery continuity: <missing restored state rejects until continuity re-established | trusted epoch/generation invalidates outstanding tickets>
Subscription authorization separation: required
```

Rules:

- ticket evidence is validated before `101` and is never treated as a general API credential;
- ticket scope and expiry are validated together with expected Origin and the canonical ingress request;
- current session/credential, membership/permission/tenant access and current placement/admission generation are checked before successful upgrade where applicable;
- the final replay mutation is an atomic shared single-winner consume across replicas; `unused? -> consume later`, replica-local memory or another read/check flow does not satisfy this contract;
- after successful consume, a crash or failure before completing `101` leaves the ticket burned; the client must obtain a fresh ticket;
- replay-store restart/loss/restore cannot make a consumed ticket redeemable. Missing replay state is rejection unless accepted continuity is re-established or a trusted epoch/generation advance invalidates outstanding old tickets;
- a successful connection grants only the bounded connection authority; later subscription authorization remains separate and Phase 10 must preserve it.

Exact ticket TTL, representation/encoding, replay-store product, epoch/generation representation and gateway/runtime topology remain implementation/OPEN choices. Atomic single-winner, burn-on-ambiguity, current-authority/placement checks and fail-closed replay recovery are not OPEN.

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

`operation_id`/URL is never bearer authority. Poll/cancel/retry/resume/result access re-establishes current authorization.

## Pagination/filter/sort

For collection endpoints:

```text
Default sort: <deterministic order>
Cursor mode: live | snapshot-like | historical-window
Allowed filters: ...
Allowed sorts: ...
Allowed includes: ...
Query multiplicity rules: <per parameter>
Default limit: <value/policy>
Maximum limit: <value/policy>
Total count: absent | exact | approximate | optional
Current authorization re-evaluated on each page: yes
Cursor security binding: <tenant/query/sort plus needed principal/scope dimensions>
Cursor payload confidentiality: <no protected payload | server-side opaque handle | confidential+integrity-protected envelope | equivalent>
Cursor exposed-token classification: url_safe_non_sensitive_handle | protected_continuation_token
Browser cursor transport: query allowed only for non-sensitive handle | non-URL-visible protected transport
Cursor URL/logging policy: <redacted/hash/reference>
Sensitive query parameters allowed in URL: <no | explicit public/non-sensitive allowlist>
```

A cursor/snapshot/watermark never freezes authorization. Each continuation re-establishes current authority.

"Opaque" does not mean confidential. A confidential token may still be a reusable protected continuation capability. Browser-facing protected continuation tokens SHALL NOT be required in address/history-visible query strings unless the exposed handle is explicitly classified non-sensitive for that surface.

## Data classification

Classify request/response fields as applicable:

```text
public
internal
confidential
restricted/credential
regulated/PII
```

Declare redaction/logging restrictions.

## Audit

State whether audit is required; actor/tenant/action/resource/outcome fields; atomic audit intent obligations; and high-risk reason/approval/step-up metadata where applicable.

## Observability

Declare:

```text
request_id required
correlation_id propagation
operation_id linkage
tenant-safe metrics/log dimensions
provider/external-call linkage where applicable
canonical-ingress/entity rejection telemetry where applicable
```

No secrets in observability payloads. Rejected ambiguous requests log safe rejection classes rather than competing raw values.

## Compatibility classification

Classify externally important fields/enums and security/behavior dimensions. Document whether changes to the following are breaking/security-sensitive:

- authorization/scope/idempotency/retry/consistency;
- idempotency restore/PITR/partial-loss recovery continuity;
- HTTP framing/header/method/trailer/content-coding/trusted-proxy/path/query interpretation;
- structured request entity parsing, duplicate/alias/member/part semantics and canonical propagation;
- response-header grammar/cardinality/serialization ownership;
- response-cache class/shared eligibility/variance/current-auth revalidation;
- callback authentication/freshness binding/replay identity/atomic admission/durable coupling/replay retention/replay recovery continuity/acknowledgement durability/post-effect ambiguity/reconciliation;
- realtime ticket scope/expiry/current-authority/placement checks/atomic single-winner/burn-on-ambiguity/replay recovery continuity/subscription separation;
- cursor confidentiality/browser transport/URL redaction;
- browser-delivery/media-type/safe-filename/active-content isolation;
- untrusted-content/archive/XML processing.

A security policy becoming more permissive is never treated as an implementation-only optimization.

## Security abuse cases

Consider, where applicable:

- conflicting `Content-Length`/`Transfer-Encoding` or multiple body lengths;
- unsafe connection reuse after rejected framing/body;
- duplicate/conflicting auth/idempotency headers;
- method override or security-trailer injection;
- conflicting Host/authority/trusted-forwarding metadata;
- repeated slash/dot-segment/encoded-separator/non-canonical path ambiguity;
- duplicate singleton query parameters/alternate encodings;
- duplicate JSON object members or names that alias after normalization;
- multipart duplicate/aliasing part names, conflicting per-part metadata or ambiguous nested boundaries;
- one parser validating/authorizing one body meaning while another parser executes another;
- content-coding/decompression interpretation mismatch;
- response header CRLF/control injection or conflicting singleton serialization;
- wrong tenant/cross-tenant resource identity;
- stale revision/revoked principal;
- lost one-time-secret response/lockout;
- idempotency state restored/partially lost so a missing claim is misclassified as never executed;
- shared-cache leakage;
- protected cursor in browser history;
- operation ID as bearer authority;
- wildcard credentialed BFF origin;
- browser-active artifact on application origin;
- deceptive artifact filename/media type;
- malicious archive/parser/DTD/XXE/SSRF/resource exhaustion;
- callback freshness evidence not bound to authenticated input;
- callback replay admission race or consumed-without-durable-work state;
- callback replay/ambiguity record expiry while unresolved work or outcome remains;
- callback replay store restored/partially lost so a missing replay record is misclassified as unused;
- callback success acknowledgement before durable responsibility;
- callback crash after a possibly successful external irreversible effect but before durable outcome recording, followed by unsafe re-execution instead of reconciliation;
- realtime read/check replay admission or replica-local replay state admitting multiple winners;
- realtime ticket consumed and then made reusable after crash/failed upgrade;
- realtime replay store restored/lost so missing state is misclassified as unused;
- replayed callback/ticket;
- provider outage.

## Contract tests

Every externally reachable endpoint tests applicable canonical HTTP ingress cases from `http-message-framing-and-canonicalization.md`.

Protected mutation/body-bearing endpoints additionally test:

- conflicting framing rejected before auth/idempotency/effect;
- duplicate/conflicting authentication/idempotency inputs rejected;
- gateway and service consume one canonical path/query/authority interpretation;
- duplicate JSON object members rejected under the default JSON profile;
- aliasing JSON names cannot bypass duplicate detection;
- multipart duplicate/alias part names and conflicting per-part metadata fail closed unless explicitly supported;
- ambiguous/nested multipart boundaries cannot cause validation/auth/idempotency/use-case disagreement;
- one canonical parsed entity is reused for validation, authorization inputs, idempotency fingerprint and command mapping;
- structured entity rejected before owning authorization when accepted parsers could disagree;
- authorized success/unauthenticated denial/wrong-tenant denial;
- placement -> `TenantContext` -> request validation -> owning authorization ordering;
- idempotency/concurrency and response-loss recovery;
- restore/PITR/partial-loss of idempotency state cannot turn missing/older claim/result/tombstone into new execution authority before `(R,F]` continuity reconciliation;
- response-header CRLF/control/duplicate-singleton injection attempts fail safely;
- proxy/framework cannot append a second conflicting security-relevant response singleton;
- response cache non-reuse/compatibility;
- current continuation authorization/cursor confidentiality and browser transport;
- BFF Origin/CORS/CSRF;
- callback raw-body/signature, authenticated freshness binding, atomic replay admission, replay retention, replay restore/PITR continuity, acknowledgement durability, post-effect/pre-outcome-record crash, durable-coupling/reconciliation, SSRF/XML protections;
- safe audit/error/observability behavior.

For `realtime-admission`, additionally test ticket scope/expiry, expected Origin, current session/membership/permission/tenant access, current placement generation where applicable, simultaneous cross-replica single-winner consume, burn-on-ambiguity after consume-before-`101` failure, replay-store restart/loss/restore, trusted epoch/generation invalidation behavior and subscription-authorization separation.

Artifact/binary endpoints additionally test media authority, safe filename/header construction, active-inline isolation, range/CDN fencing, archive bounds/containment/member collision/no-replace semantics, parser secret/egress isolation, DTD/external-resolution denial and independent derivative classification.

## OPEN items

Explicitly list unresolved items. An omitted decision is not silently considered accepted.

## Evolution notes

Explain how the contract remains stable if:

- the domain is extracted into a service;
- tenant moves cells/regions;
- storage/provider/gateway/parser changes;
- backup/recovery topology or idempotency/replay storage changes while recovery-continuity semantics remain identical;
- request volume/cardinality grows substantially;
- HTTP protocol/version or proxy layers change while canonical semantics stay equivalent;
- the structured-body parser/library changes while canonical entity semantics remain identical;
- response-header serialization moves between framework/proxy layers without changing the accepted profile;
- a provider callback authenticator/SDK/replay implementation changes while freshness binding, replay retention, replay recovery continuity, acknowledgement durability and post-effect reconciliation semantics remain identical;
- realtime gateway/runtime/replay store changes while ticket scope/expiry/current-authority/placement/single-winner/burn/recovery-continuity semantics remain identical;
- CDN/cache is added or replaced;
- cursor implementation changes without weakening browser transport/history policy;
- artifact delivery/processing moves runtimes/vendors without weakening security invariants.