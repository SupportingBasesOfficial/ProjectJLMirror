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

OpenAPI/schema alone is not sufficient to capture all JLMIRROR semantics. Each operation also conforms to the Phase 09 idempotency, authorization, consistency, audit, tenant, response-cache, artifact-browser-delivery, untrusted-content-processing and compatibility declarations.

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
artifact_content_disposition_policy
artifact_mime_sniffing_policy
active_content_isolation_profile
artifact_delegated_delivery_scope
artifact_untrusted_processing_profile
artifact_processing_secret_scope
artifact_processing_egress_policy
artifact_processing_resource_bounds
derived_artifact_classification_policy
callback_outbound_fetch_policy
data_classification
```

This metadata may live in OpenAPI extensions or an adjacent validated manifest. Exact encoding is implementation tooling; the fields/semantics are contract requirements.

## Contract review gate

An endpoint is not ready for implementation until review proves:

1. one owning domain/use case;
2. no database/provider/internal-topology leakage;
3. explicit tenant/global scope;
4. explicit trusted placement/routing/TenantContext boundary where tenant-scoped;
5. request-contract validation occurs before owning authorization consumes caller-controlled scope/resource fields;
6. explicit authorization action/scope and owning authorization authority;
7. BFF/browser Origin/CORS/CSRF profile where applicable;
8. request/response schema and bounds;
9. retry/idempotency behavior;
10. lockout-safe one-time-secret response-loss/recovery when applicable;
11. concurrency behavior where needed;
12. consistency/result semantics;
13. long-running operation behavior and current access authority where needed;
14. current-authorization continuation semantics for pagination/history/bulk where applicable;
15. stable errors;
16. explicit response-cache class, protected-error policy, shared-cache eligibility, variance/revalidation/current-auth policy;
17. artifact/binary browser-delivery profile, authoritative media-type policy and active-content isolation where applicable;
18. isolated/bounded untrusted artifact-processing profile where parsing/rendering/preview/conversion/extraction occurs;
19. callback outbound-fetch/SSRF policy where applicable;
20. audit/observability requirements;
21. compatibility classification, including cache/retry/auth/consistency/browser-delivery/content-processing semantics;
22. security/privacy classification;
23. required tests.

For browser-reachable artifact bytes, review MUST prove that authorization to download is not treated as authority for inline execution. Unknown/untrusted/browser-active content fails toward attachment/non-sniffable download semantics, and any active-inline profile uses an isolated untrusted-content boundary without application/BFF ambient credentials or origin/service-worker trust while preserving current artifact authorization and fencing.

For complex untrusted artifact processing, review MUST prove isolation from ordinary API/BFF secrets and unrestricted egress, bounded CPU/memory/time/decompressed-output/nesting/member counts, no implicit macro/script/embedded-URL execution, and independent classification of generated derivative artifacts.

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
- operation-resource current authorization when applicable;
- response-cache class/headers/revalidation/non-reuse semantics including protected errors;
- artifact browser-delivery/media-type/isolation semantics where bytes are browser reachable;
- untrusted artifact-processing isolation/resource/egress/output-classification semantics where parsing/rendering occurs;
- callback outbound-fetch/SSRF boundary where applicable;
- size/complexity limits;
- secret/topology leakage checks.

Artifact/binary contract tests additionally prove, where applicable:

- uploader filename/extension/media type cannot force executable inline delivery;
- unknown/untrusted/browser-active content falls back to attachment/non-sniffable download behavior;
- filename metadata cannot inject response headers;
- `safe_inline` is restricted to explicitly accepted validated classes;
- active-inline content cannot execute with application/BFF ambient credentials or origin/service-worker trust;
- delegated delivery remains artifact/delivery-generation bounded and preserves current authorization/releasability/active-stream fencing;
- range/resume/CDN paths cannot weaken the accepted browser-delivery profile;
- archive/decompression recursion and expanded output remain bounded;
- parser/renderer cannot access ordinary application secrets or unrestricted network destinations;
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
- authorization action/scope/authority or authorization-input changes;
- BFF origin/credential policy changes;
- idempotency/retry classification changes;
- consistency-class changes;
- response cache class/shared-cache eligibility changes;
- protected-error cache policy changes;
- cache variance/validator/revalidation/current-authorization reuse changes;
- artifact browser-delivery profile becoming more permissive;
- artifact authoritative media-type/content-disposition/sniffing policy changes;
- active-content isolation or delegated-delivery scope changes;
- untrusted artifact-processing profile moving to a less isolated runtime or gaining broader secret/network authority;
- artifact-processing expansion/resource bounds becoming weaker or derived-output classification being removed;
- pagination/operation current-authorization semantics becoming weaker;
- one-time-secret recovery/cutover changes that could remove a previously safe recovery authority;
- callback outbound destination/redirect policy becoming more permissive.

The diff tool cannot prove semantic compatibility. Reviewers still inspect changes to idempotency, authorization, consistency, ownership, retry, credential recovery, continuation authority, artifact browser execution/processing, callback egress and cache behavior.

A deployment/framework/CDN/browser-delivery/parser-runtime configuration change that alters an endpoint's effective accepted cache, active-content or untrusted-processing semantics is subject to the same governance even if no OpenAPI schema changed.

## Golden examples/test vectors

High-risk contracts SHOULD include executable test vectors/examples for cases such as:

- idempotent replay after response loss;
- idempotency-key fingerprint conflict;
- one-time-secret response loss with surviving recovery authority;
- sole-credential rotation rejected or staged when recovery authority would otherwise be lost;
- optimistic concurrency mismatch;
- existence-concealing authorization denial;
- request validation before owning authorization consumes caller-controlled resource scope;
- stale cursor rejected/re-authorized after revocation;
- operation poll/cancel rejected after authority revocation;
- cross-principal/tenant protected cache non-reuse;
- protected error non-reuse;
- cache-policy compatibility regression;
- BFF wildcard/untrusted credentialed origin rejection;
- browser-active artifact forced to safe download on application/BFF origin;
- active-inline artifact isolated from application/BFF ambient credentials and origin trust;
- forged upload media type unable to opt into inline execution;
- archive/decompression bomb bounded without exhausting the business runtime;
- parser/renderer exploit or embedded URL cannot reach application secrets/private network under the processing profile;
- derived preview remains non-inline until independently classified;
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
- tolerate compatible unknown response fields/open enum values;
- implement automatic retry only where operation metadata proves retry safety;
- expose stable problem/error codes;
- treat one-time-secret response loss as explicit non-automatic recovery;
- never treat cursor or operation ID as authorization;
- never infer physical tenant placement;
- preserve server-declared artifact download/inline semantics rather than overriding them from filename or guessed media type;
- avoid hiding operation-resource semantics behind indefinite polling without cancellation/deadline controls.

## Documentation publishing

Published API reference is generated or checked against the accepted machine-readable contract. Human guides may add workflow explanation but SHALL NOT contradict canonical schemas/semantics.

## Security review triggers

Contract changes require explicit security review when they introduce or materially change:

- authentication/credential transport;
- authorization scope/authority or authorization input fields;
- trusted routing/TenantContext ordering;
- BFF credentialed origin/CORS/CSRF behavior;
- cross-tenant capability;
- direct SQL/data administration;
- automation execution;
- artifact upload/download, browser-delivery class, media-type policy, active-content isolation or untrusted parser/renderer processing;
- callback/webhook ingress or callback-driven outbound retrieval;
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

For example, changing `/api/v1` field naming does not necessarily require an ADR; changing tenant authority, browser credential boundary, consistency ownership or service extraction semantics does.

## Proposed-to-accepted promotion

Phase 09 documents remain `proposed baseline` until the Phase 09 PR receives the required architecture/security/contract review and formal governance promotion.

Implementation SHALL NOT treat a proposed Phase 09 choice as permanent external compatibility debt before acceptance unless an explicitly temporary experimental contract is approved.