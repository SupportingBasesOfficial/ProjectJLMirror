# Contract Governance, OpenAPI and Testing

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

The accepted API contract is a versioned engineering artifact. Implementation code is required to conform to it; implementation is not allowed to silently become the contract because a controller, DTO or database schema happened to ship first.

## Canonical sources

The human-readable Phase 09 documents define cross-cutting semantics and governance. Machine-readable HTTP schemas SHALL be maintained in a canonical contract tree when endpoint-level definitions begin.

Proposed repository layout:

```text
contracts/
  http/
    v1/
      openapi.yaml
      domains/
        platform.yaml
        identity.yaml
        organization.yaml
        monitoring.yaml
        alerting.yaml
        itsm.yaml
        automation.yaml
        infrastructure.yaml
        aiops.yaml
        finops.yaml
        commercial.yaml
        reporting.yaml
        integrations.yaml
        data-admin.yaml
        governance.yaml
      components/
        common.yaml
        errors.yaml
        operations.yaml
        pagination.yaml
        security.yaml
      examples/
      test-vectors/
```

Exact composition tooling is implementation-level. The canonical bundled artifact SHALL be reproducible from reviewed sources.

## OpenAPI role

The machine-readable HTTP contract SHALL describe:

- paths/methods;
- operation IDs;
- request/response schemas;
- parameters/headers;
- success/error status classes;
- security requirements at a transport-profile level;
- stable reusable components;
- examples where they materially clarify semantics.

OpenAPI/schema alone is not sufficient to capture all JLMIRROR semantics. Each operation also conforms to the Phase 09 HTTP message/framing/method/trailer/path/query/content-coding canonicalization, idempotency, authorization, consistency, audit, tenant, response-cache, cursor confidentiality/transport, artifact-browser-delivery, safe-filename, untrusted-content/archive processing, XML parser-resolution and compatibility declarations.

## Stable operation ID

Every externally supported operation has a stable `operation_id`/OpenAPI `operationId` that reflects domain semantics, for example:

```text
monitoring.listResources
itsm.createIncident
itsm.resolveIncident
platform.suspendTenant
reporting.createReportRun
```

Renaming source-code handlers SHALL NOT require renaming the contract operation ID.

## Endpoint contract manifest

Each operation definition SHALL carry/refer to structured metadata for:

```text
owner_domain
tenant_scope
http_message_profile
body_framing_policy
content_coding_policy
method_override_policy
request_trailer_policy
security_header_cardinality
trusted_proxy_metadata_policy
request_target_profile
query_multiplicity_policy
protocol_translation_profile
authorization_action
authorization_scope
authorization_input_fields
owning_authorization_authority
step_up
audit_class
browser_origin_policy
csrf_requirement
consistency_class
idempotency_class
optimistic_concurrency
retry_class
one_time_secret_behavior
secret_recovery_authority
credential_cutover_semantics
long_running_operation
operation_access_authorization
pagination_authorization_freshness
cursor_confidentiality_policy
cursor_exposed_token_classification
cursor_browser_transport_policy
cursor_url_logging_policy
sensitive_query_url_policy
request_limits
response_cache_class
shared_cache_eligibility
cache_variance
cache_revalidation
current_authorization_before_cache_reuse
protected_error_cache_policy
cache_freshness_policy
artifact_browser_delivery_profile
artifact_authoritative_media_type_policy
artifact_safe_filename_policy
artifact_content_disposition_policy
artifact_mime_sniffing_policy
active_content_isolation_profile
artifact_delegated_delivery_scope
artifact_untrusted_processing_profile
artifact_processing_secret_scope
artifact_processing_egress_policy
artifact_processing_resource_bounds
artifact_archive_extraction_policy
artifact_archive_member_identity_policy
artifact_xml_dtd_policy
artifact_xml_external_resolution_policy
derived_artifact_classification_policy
callback_xml_dtd_policy
callback_xml_external_resolution_policy
callback_outbound_fetch_policy
data_classification
```

This metadata may live in OpenAPI extensions or an adjacent validated manifest. Exact encoding is implementation tooling; the fields/semantics are contract requirements.

## Contract review gate

An endpoint is not ready for implementation until review proves:

1. one owning domain/use case;
2. no database/provider/internal-topology leakage;
3. explicit tenant/global scope;
4. inherited or specialized canonical HTTP message/framing/method/trailer/path/query/content-coding profile, security-sensitive header cardinality and trusted-proxy semantics;
5. explicit trusted placement/routing/TenantContext boundary where tenant-scoped, with canonical path decoding before placement;
6. request-contract validation occurs before owning authorization consumes caller-controlled scope/resource fields;
7. explicit authorization action/scope and owning authorization authority;
8. BFF/browser Origin/CORS/CSRF profile where applicable;
9. request/response schema, query multiplicity and raw/decoded/header bounds;
10. retry/idempotency behavior;
11. lockout-safe one-time-secret response-loss/recovery when applicable;
12. concurrency behavior where needed;
13. consistency/result semantics;
14. long-running operation behavior and current access authority where needed;
15. current-authorization continuation semantics for pagination/history/bulk where applicable;
16. cursor payload confidentiality, exposed-token classification, browser transport, URL-log policy and sensitive query URL policy where collection/query contracts apply;
17. stable errors;
18. explicit response-cache class, protected-error policy, shared-cache eligibility, variance/revalidation/current-auth policy;
19. artifact/binary browser-delivery profile, authoritative media-type policy, safe-filename policy and active-content isolation where applicable;
20. isolated/bounded untrusted artifact-processing profile, archive staging-root containment, canonical member collision policy, no-follow/no-replace materialization and XML DTD/external-resolution policy where parsing/rendering/preview/conversion/extraction occurs;
21. callback XML DTD/external-resolution and outbound-fetch/SSRF policy where applicable;
22. audit/observability requirements;
23. compatibility classification, including HTTP parser/path/query, cache/retry/auth/consistency/cursor/browser-delivery/archive/content-processing/parser semantics;
24. security/privacy classification;
25. required tests.

For every externally reachable HTTP surface, review MUST prove the `http-message-framing-and-canonicalization.md` property: one accepted wire request has one canonical interpretation at every participating hop before authentication, tenant routing, idempotency, cache or protected effects. Ambiguous framing, method override, security-sensitive trailers, competing security headers, conflicting authority/trusted-proxy metadata, non-canonical path/query decoding, duplicate singleton query parameters or content-coding parser disagreement fail closed. If HTTP-version translation exists, the test path includes the real translation boundary rather than only the application controller.

For protected collection/query contracts, review MUST prove canonical query decoding/multiplicity across all hops. Duplicate singleton parameters are rejected, repeated parameters have one explicit order/duplicate/count rule, and alternate encodings cannot bypass duplicate detection.

For cursor contracts, review MUST distinguish payload confidentiality from token transport. "Opaque" is not confidential; an encrypted/self-contained protected cursor can still be a reusable protected continuation token. Browser-facing protected continuation tokens SHALL use non-URL-visible transport unless the exposed handle itself is explicitly classified non-sensitive for that browser surface. Normal logs/analytics/referrers SHALL NOT persist raw protected cursor/query values.

For browser-reachable artifact bytes, review MUST prove that authorization to download is not treated as authority for inline execution. Unknown/untrusted/browser-active content fails toward attachment/non-sniffable download semantics, download filenames are server-derived and unambiguous, and any active-inline profile uses an isolated untrusted-content boundary without application/BFF ambient credentials or origin/service-worker trust while preserving current artifact authorization and fencing.

For complex untrusted artifact processing, review MUST prove isolation from ordinary API/BFF secrets and unrestricted egress, bounded CPU/memory/time/decompressed-output/nesting/member counts, archive staging-root containment, canonical member identity with duplicate/normalization/platform collision rejection, no-follow atomic/no-replace materialization, scanner-to-consumer byte equivalence, no implicit macro/script/embedded-URL execution, **DTD rejection by default**, XML active external-resolution denial and independent classification of derivative artifacts.

For XML callback profiles, review MUST prove that **every DTD declaration is rejected by default**, and external entities/XInclude/external schema/stylesheet/resource resolution cannot read local files or reach network/internal services. Any exceptional DTD/resolver format profile requires separate review, pinned/trusted resources, isolation, deny-by-default file/network access and bounded interpretation.

## Schema generation direction

Generated code MAY be produced from accepted schemas. Generated schemas from arbitrary implementation DTOs SHALL NOT automatically become canonical contracts without review.

The preferred direction is:

```text
accepted contract
  -> generated types/clients/stubs where useful
  -> implementation adapters
```

not:

```text
internal ORM/controller class
  -> accidental public contract
```

## Shared schemas

Reusable contract components are used only when semantics are truly identical.

A generic `Status`, `Metadata`, `Resource`, `User` or `Error` schema SHALL NOT be shared across unrelated domains merely to reduce file count if doing so erases domain meaning or couples future evolution.

## Contract tests

Every implemented endpoint SHALL have contract tests that validate at minimum:

- accepted methods/path;
- canonical HTTP message/framing/method/trailer/path/query/content-coding behavior and applicable cross-hop/protocol-translation ambiguity rejection;
- security-sensitive header cardinality/combine semantics;
- trusted proxy/authority/request-target normalization cannot diverge between edge and owning service;
- duplicate singleton query parameters/alternate encoding collisions are rejected and repeated-list parameters have one canonical rule;
- required/forbidden fields;
- unknown request-field rejection;
- request fields used for authorization/resource selection are validated before owning policy consumes them;
- success response schema;
- expected error shape/codes;
- authorization/tenant isolation behavior;
- BFF Origin/CORS/CSRF behavior where applicable;
- idempotency semantics when applicable;
- lockout-safe one-time-secret response-loss/recovery when applicable;
- concurrency preconditions when applicable;
- pagination/cursor current-authorization behavior when applicable;
- cursor payload confidentiality plus browser-history-safe transport when token is protected/reusable;
- confidential query/filter/search input is not forced into URL-visible transport;
- operation-resource current authorization when applicable;
- response-cache class/headers/revalidation/non-reuse semantics including protected errors;
- artifact browser-delivery/media-type/safe-filename/isolation semantics where bytes are browser reachable;
- untrusted artifact-processing isolation/resource/egress/archive-member/XML/output-classification semantics where parsing/rendering occurs;
- callback raw-body/signature processing observes the same canonical framing and exact bounded raw bytes;
- callback rejects every DTD by default and enforces XML external-resolution/outbound-fetch/SSRF boundary where applicable;
- realtime upgrade cannot bypass canonical HTTP ingress before `101`;
- size/complexity limits;
- secret/topology/confidential-URL leakage checks.

Artifact/binary contract tests additionally prove, where applicable:

- uploader filename/extension/media type cannot force executable inline delivery;
- unknown/untrusted/browser-active content falls back to attachment/non-sniffable download behavior;
- filename metadata cannot inject or ambiguate response headers;
- controls/bidi/path separators/reserved names/misleading extensions cannot create a deceptive saved filename;
- `filename`/`filename*` encode one coherent logical name and a server-generated fallback exists;
- `safe_inline` is restricted to explicitly accepted validated classes;
- active-inline content cannot execute with application/BFF ambient credentials or origin/service-worker trust;
- delegated delivery remains artifact/delivery-generation bounded and preserves current authorization/releasability/active-stream fencing;
- range/resume/CDN paths cannot weaken the accepted browser-delivery profile;
- archive/decompression recursion and expanded output remain bounded;
- archive extraction cannot escape staging root through traversal, absolute paths, links or special/device files;
- duplicate archive members and names colliding after Unicode normalization, case folding, trailing-dot/space or target-platform path conversion are rejected;
- archive materialization uses no-follow atomic/no-replace semantics or equivalent so a scanned member cannot be overwritten/aliased before later consumption;
- parser/renderer cannot access ordinary application secrets or unrestricted network destinations;
- XML/XML-derived processing rejects every DTD by default and cannot resolve external entities/includes/schemas/stylesheets/local files/network resources outside a separately reviewed exceptional profile;
- embedded script/macro execution and attacker-controlled URL retrieval do not occur implicitly;
- generated preview/conversion output receives independent artifact identity/classification before release.

## Consumer compatibility tests

Critical official clients/BFF flows SHOULD maintain consumer tests against the accepted contract rather than relying only on server unit tests.

A server change that passes internal tests but breaks an accepted client contract is a release defect.

## Breaking-change CI

CI SHALL compare the proposed machine-readable contract and validated semantic manifest against the accepted `main` baseline.

It flags likely breaking/security-sensitive changes such as:

- removed path/method;
- removed/renamed response field;
- request field becoming required;
- type/format changes;
- closed enum changes;
- changed status/error contract;
- incompatible parameter changes;
- HTTP message/framing/method/trailer/content-coding profile becoming more permissive;
- security-sensitive header cardinality/combine semantics changing;
- trusted proxy/authority/path/query normalization policy changing;
- query multiplicity or duplicate-parameter behavior changing;
- protocol translation introducing/removing a parser boundary without equivalent ambiguity tests;
- authorization action/scope/authority or authorization-input changes;
- BFF origin/credential policy changes;
- idempotency/retry classification changes;
- consistency-class changes;
- response cache class/shared-cache eligibility changes;
- protected-error cache policy changes;
- cache variance/validator/revalidation/current-authorization reuse changes;
- cursor protection moving from confidential/server-side opaque to merely encoded/signed plaintext;
- protected cursor moving into browser-history-visible transport;
- cursor/query logging/referrer policy becoming more permissive;
- confidential query values becoming URL-visible;
- artifact browser-delivery profile becoming more permissive;
- artifact authoritative media-type/content-disposition/safe-filename/sniffing policy changes;
- active-content isolation or delegated-delivery scope changes;
- untrusted artifact-processing profile moving to a less isolated runtime or gaining broader secret/network authority;
- archive extraction containment, canonical member collision policy or atomic no-replace behavior becoming weaker;
- XML DTD/external-resolution policy becoming weaker;
- artifact-processing expansion/resource bounds becoming weaker or derived-output classification being removed;
- callback DTD/XML external-resolution or outbound destination/redirect policy becoming more permissive;
- pagination/operation current-authorization semantics becoming weaker;
- one-time-secret recovery/cutover changes that could remove a previously safe recovery authority.

The diff tool cannot prove semantic compatibility. Reviewers still inspect changes to HTTP framing/path/query canonicalization, idempotency, authorization, consistency, ownership, retry, credential recovery, continuation authority/confidentiality/transport, artifact browser execution/filename/archive processing, callback parser/egress and cache behavior.

A deployment/framework/gateway/reverse-proxy/HTTP-runtime/CDN/browser-delivery/parser/archive-runtime configuration change that alters an endpoint's effective accepted message interpretation, query multiplicity, cache, cursor transport/confidentiality, active-content, safe-filename, canonical archive-member or XML-processing semantics is subject to the same governance even if no OpenAPI schema changed.

## Golden examples/test vectors

High-risk contracts SHOULD include executable test vectors/examples for cases such as:

- conflicting `Content-Length`/`Transfer-Encoding` rejected before auth/body processing;
- multiple conflicting body lengths rejected across the deployed proxy/application path;
- duplicate/conflicting `Authorization` and `Idempotency-Key` rejected rather than first/last-selected;
- method override/security trailer rejection;
- Host/authority or untrusted forwarded-metadata conflict rejected;
- repeated slash/dot-segment/encoded separator/malformed percent/non-canonical UTF-8 path cannot route one tenant/resource while placement/application resolves another;
- duplicate singleton query (`cursor`, `limit`, auth-relevant filter) rejected independent of encoding/order;
- HTTP-version translation cannot turn invalid framing into accepted protected work;
- content-coding mismatch cannot make edge/signature/application process different entity representations;
- callback signature verification and adapter processing observe the same bounded raw body;
- ambiguous realtime upgrade rejected before `101`;
- idempotent replay after response loss;
- idempotency-key fingerprint conflict;
- one-time-secret response loss with surviving recovery authority;
- sole-credential rotation rejected or staged when recovery authority would otherwise be lost;
- optimistic concurrency mismatch;
- existence-concealing authorization denial;
- request validation before owning authorization consumes caller-controlled resource scope;
- stale cursor rejected/re-authorized after revocation;
- protected cursor payload remains confidential;
- protected browser continuation token uses non-URL-visible transport and is absent from browser history;
- confidential search/filter input uses non-URL-visible representation;
- operation poll/cancel rejected after authority revocation;
- cross-principal/tenant protected cache non-reuse;
- protected error non-reuse;
- cache-policy compatibility regression;
- BFF wildcard/untrusted credentialed origin rejection;
- browser-active artifact forced to safe download on application/BFF origin;
- active-inline artifact isolated from application/BFF ambient credentials and origin trust;
- forged upload media type unable to opt into inline execution;
- bidi/control/path/double-extension filename input resolves to safe canonical fallback/header semantics;
- archive/decompression bomb bounded without exhausting the business runtime;
- archive traversal/link escape cannot write outside staging root;
- duplicate/Unicode/case/platform-colliding archive names are rejected before extraction;
- atomic no-follow/no-replace extraction prevents post-scan overwrite/type substitution;
- parser/renderer exploit or embedded URL cannot reach application secrets/private network under the processing profile;
- XML DTD/internal entity/default-attribute attempts are rejected under default profile;
- XML external entity/XInclude/schema attempts cannot read local files or perform network retrieval;
- derived preview remains non-inline until independently classified;
- callback DTD/XXE/local-file/network-resolution rejection;
- callback-supplied SSRF target rejection;
- cursor continuation under deterministic sort;
- long-running reconciliation state;
- artifact unavailable/erasure-fencing behavior;
- realtime ticket rejection before `101`.

Examples are validated against schema/manifest so documentation cannot silently drift.

## Mocking

Mock servers generated from schemas MAY accelerate UI/integration development. Mock behavior SHALL NOT be treated as proof of server-side domain/security semantics.

Mocks for protected operations should model important denial/error states, not only happy-path `200` responses.

## SDKs

Official SDK generation MAY be introduced from accepted contracts.

SDKs SHALL:

- preserve opaque IDs/cursors/revisions;
- treat cursors as non-inspectable transport values and not decode/log protected cursor payloads;
- use browser-history-safe/non-URL transport for protected browser continuation tokens according to the endpoint contract;
- tolerate compatible unknown response fields/open enum values;
- implement automatic retry only where operation metadata proves retry safety;
- expose stable problem/error codes;
- treat one-time-secret response loss as explicit non-automatic recovery;
- never treat cursor or operation ID as authorization;
- never infer physical tenant placement;
- preserve server-declared artifact download/inline and safe-filename semantics rather than overriding them from filename or guessed media type;
- avoid hiding operation-resource semantics behind indefinite polling without cancellation/deadline controls.

SDK behavior does not relax edge/server HTTP message canonicalization; malformed/ambiguous wire requests are server-side security failures regardless of client library intent.

## Documentation publishing

Published API reference is generated or checked against the accepted machine-readable contract. Human guides may add workflow explanation but SHALL NOT contradict canonical schemas/semantics.

## Security review triggers

Contract changes require explicit security review when they introduce or materially change:

- HTTP message framing, method/trailer/content-coding, header cardinality, path/query normalization/multiplicity, trusted proxy metadata or protocol translation;
- authentication/credential transport;
- authorization scope/authority or authorization input fields;
- trusted routing/TenantContext ordering;
- BFF credentialed origin/CORS/CSRF behavior;
- cross-tenant capability;
- direct SQL/data administration;
- automation execution;
- cursor confidentiality, exposed-token classification, browser transport, URL/query exposure or continuation logging policy;
- artifact upload/download, safe filename, browser-delivery class, media-type policy, active-content isolation or untrusted parser/renderer/archive processing;
- archive canonical member identity/collision/materialization semantics;
- callback/webhook ingress, DTD/XML parser external-resolution behavior or callback-driven outbound retrieval;
- public projection;
- realtime admission;
- sensitive data exposure;
- bulk/export/import limits;
- pagination/history continuation authorization semantics;
- operation read/cancel/retry/resume/result authorization;
- idempotency/replay behavior for irreversible effects;
- one-time-secret creation/rotation/recovery/cutover semantics;
- response-cache class, protected-error caching, shared-cache eligibility, variance, freshness or current-auth revalidation semantics.

## ADR/RFC trigger

A contract change requires a new/revised ADR or RFC when it changes a high-impact accepted architecture/security/data decision rather than merely specializing a representation already delegated to Phase 09.

For example, changing `/api/v1` field naming does not necessarily require an ADR; changing tenant authority, browser credential boundary, trusted HTTP message interpretation, consistency ownership or service extraction semantics does.

## Proposed-to-accepted promotion

Phase 09 documents remain `proposed baseline` until the Phase 09 PR receives the required architecture/security/contract review and formal governance promotion.

Implementation SHALL NOT treat a proposed Phase 09 choice as permanent external compatibility debt before acceptance unless an explicitly temporary experimental contract is approved.