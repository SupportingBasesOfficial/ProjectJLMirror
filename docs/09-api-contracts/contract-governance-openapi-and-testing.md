# Contract Governance, OpenAPI and Testing

**Status:** proposed baseline  
**Phase:** 09 — API & Contracts

## Principle

The accepted API contract is a versioned engineering artifact. Implementation code conforms to it; controller, DTO, framework parser, proxy behavior or database schema does not silently become the public/security contract merely because it shipped first.

## Canonical sources

Human-readable Phase 09 documents define cross-cutting semantics and governance. Machine-readable HTTP schemas SHALL be maintained in a canonical contract tree when endpoint-level definitions begin.

Proposed layout:

```text
contracts/
  http/
    v1/
      openapi.yaml
      domains/
      components/
      examples/
      test-vectors/
```

Exact composition tooling is implementation-level. The canonical bundled artifact SHALL be reproducible from reviewed sources.

## OpenAPI role

The machine-readable HTTP contract SHALL describe paths/methods, operation IDs, request/response schemas, parameters/headers, success/error status classes, transport-profile security requirements and reusable components.

OpenAPI/schema alone is insufficient. Every operation also conforms to Phase 09 semantics for:

- HTTP framing, method/trailer, path/query and content-coding canonicalization;
- connection rejection/retirement;
- structured request entity canonicalization;
- authentication/authorization/tenant/placement;
- idempotency/concurrency/retry;
- consistency and durable operations;
- response-header construction;
- response caching;
- cursor/query confidentiality and browser transport;
- artifact/browser/parser/archive/XML safety;
- callback/realtime admission;
- observability, compatibility and OPEN discipline.

## Stable operation ID

Every supported operation has a stable `operation_id`/OpenAPI `operationId` reflecting domain semantics, not source-code class names or deployment topology.

Examples:

```text
monitoring.listResources
itsm.createIncident
itsm.resolveIncident
platform.suspendTenant
reporting.createReportRun
```

## Endpoint contract manifest

Each operation definition SHALL carry or reference structured metadata for:

```text
owner_domain
tenant_scope
http_message_profile
body_framing_policy
content_coding_policy
connection_rejection_policy
method_override_policy
request_trailer_policy
security_header_cardinality
trusted_proxy_metadata_policy
request_target_profile
query_multiplicity_policy
structured_request_entity_profile
structured_entity_duplicate_policy
structured_entity_alias_normalization_policy
structured_entity_canonical_propagation_policy
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
response_header_profile
response_header_serialization_owner
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

This metadata may live in OpenAPI extensions or an adjacent validated manifest. Exact encoding is tooling; these semantics are contract requirements.

## Contract review gate

An endpoint is not ready for implementation until review proves:

1. one owning domain/use case;
2. no database/provider/internal-topology leakage;
3. explicit tenant/global scope;
4. inherited/specialized canonical HTTP framing/method/trailer/path/query/content-coding and connection-rejection profile;
5. explicit trusted placement/routing/`TenantContext` boundary with canonical path decoding before placement;
6. canonical structured request entity establishment before request validation/owning authorization/idempotency/use-case consumption of body fields;
7. request-contract validation before owning authorization consumes caller-controlled scope/resource fields;
8. explicit authorization action/scope/authority;
9. BFF Origin/CORS/CSRF profile where applicable;
10. request/response schema, query multiplicity and raw/decoded/header/entity bounds;
11. structured media duplicate/alias/member/part/boundary semantics;
12. retry/idempotency behavior;
13. lockout-safe one-time-secret recovery when applicable;
14. concurrency behavior where needed;
15. consistency/result semantics;
16. long-running operation/current access authority where needed;
17. current-authorization continuation semantics for pagination/history/bulk;
18. cursor confidentiality, exposed-token classification, browser transport and URL/log policy;
19. stable errors;
20. explicit response-header grammar/cardinality/serialization profile;
21. explicit response-cache class, protected-error policy, sharing/variance/revalidation/current-auth policy;
22. artifact/browser delivery, authoritative media type, safe filename and active-content isolation where applicable;
23. isolated/bounded artifact/parser/archive processing, canonical archive member policy and XML DTD/external-resolution policy;
24. callback XML/SSRF and realtime admission policy where applicable;
25. audit/observability requirements;
26. compatibility classification including parser/entity/response-header semantics;
27. security/privacy classification;
28. required tests.

## Canonical HTTP gate

For every externally reachable HTTP surface, review MUST prove one accepted wire request has one canonical interpretation before authentication, tenant routing, idempotency, cache or protected effects. Ambiguous framing, unsafe connection reuse, method override, security-sensitive trailers, competing security headers, conflicting authority/trusted-proxy metadata, non-canonical path/query decoding, duplicate singleton query parameters or content-coding disagreement fail closed.

Where HTTP-version translation or connection pooling exists, tests use the actual deployed parser/pool boundary.

## Structured request entity gate

Every accepted structured request media type SHALL have a canonical parse profile.

Review MUST prove:

- duplicate JSON object member names are rejected by default;
- names that alias after accepted Unicode/name normalization are rejected;
- framework first-value/last-value/merge behavior cannot decide protected semantics;
- multipart boundaries and nested boundaries have one deterministic interpretation;
- duplicate/aliasing security-relevant multipart part names are rejected unless an explicit bounded repeated-part contract exists;
- conflicting per-part `Content-Disposition`, media metadata or nested structure cannot make validators and use cases observe different entities;
- other structured media define equivalent member/field/alias/nesting semantics;
- the canonical parsed entity, not independently reparsed raw bytes, is reused by request validation, owning authorization inputs, idempotency fingerprinting, concurrency/body preconditions, callback semantic processing and use-case command mapping;
- raw body bytes may remain separately available for signature/audit but cannot create an alternate logical body after canonical entity establishment;
- ambiguity fails before owning authorization/effect.

A framework/library that silently chooses first/last/merged duplicate semantics does not satisfy this gate.

## Query/cursor gate

Canonical query decoding/multiplicity is required across all hops. Duplicate singleton parameters are rejected; repeated parameters have explicit order/duplicate/count rules; alternate encodings cannot bypass duplicate detection.

Cursor review distinguishes payload confidentiality from exposed-token sensitivity. Browser-facing protected/reusable continuation tokens use non-URL-visible transport unless the exposed handle itself is explicitly classified non-sensitive for that surface. Logs/analytics/referrers do not persist protected values.

## Response-header gate

Every operation SHALL declare/inherit `response_header_profile` and `response_header_serialization_owner`.

Review MUST prove:

- every emitted dynamic/security-relevant response header has an accepted bounded grammar and cardinality;
- CR/LF/NUL/control characters and obsolete folding cannot inject fields or split responses;
- untrusted caller/provider/resource metadata is validated/encoded before serialization;
- `Location`, `Link`, `ETag`, `Retry-After`, `Content-Disposition`, redirects, cache/security/CORS/authentication headers and request/correlation IDs use protocol/platform grammars rather than arbitrary concatenation;
- singleton response headers cannot be independently appended with conflicting meanings by application, BFF, proxy, gateway or CDN;
- list-valued headers use one protocol-defined combine/serialization rule;
- redirect/`Location` construction cannot copy protected credentials/cursors or create unsafe authority/origin semantics;
- response-header serialization failure after a committed mutation does not rewrite authoritative business truth or invite blind re-execution; accepted idempotency/operation/read recovery remains authoritative.

A framework's default response-header serializer is implementation evidence only after it proves conformance to the profile.

## Artifact/parser gate

Browser-reachable artifact bytes require deliberate delivery classification. Unknown/untrusted/browser-active content fails toward attachment/non-sniffable behavior; filenames are server-derived/unambiguous; active-inline uses an isolated untrusted-content boundary without application/BFF ambient credentials or origin/service-worker trust while preserving current artifact authorization/fencing.

Complex untrusted artifact processing proves least-privilege isolation, restricted egress, bounded resources, staging-root containment, canonical member identity/collision rejection, no-follow atomic/no-replace materialization, scanner-to-consumer byte equivalence, DTD rejection by default, XML active-resolution denial and independent derivative classification.

For XML callbacks, every DTD is rejected by default and external entities/XInclude/schema/stylesheet/resource resolution cannot read local files or reach network/internal services. Any exceptional format profile requires separate review, pinned/trusted resources and isolated deny-by-default authority.

## Schema generation direction

Preferred direction:

```text
accepted contract
  -> generated types/clients/stubs where useful
  -> implementation adapters
```

Not:

```text
internal ORM/controller/parser default
  -> accidental public/security contract
```

Reusable components are shared only when semantics are truly identical.

## Contract tests

Every implemented endpoint SHALL test at minimum:

- accepted method/path;
- canonical framing/method/trailer/path/query/content-coding and connection-rejection behavior;
- security-sensitive request-header cardinality;
- trusted proxy/authority normalization;
- query duplicate/multiplicity semantics;
- structured request entity canonicalization for every accepted body media type;
- duplicate/alias JSON member rejection;
- multipart duplicate/alias part-name, per-part metadata and boundary ambiguity rejection where applicable;
- canonical entity reuse across request validation, owning authorization inputs, idempotency fingerprint and use-case mapping;
- required/forbidden fields and unknown-field rejection;
- authorization/tenant isolation and placement ordering;
- BFF Origin/CORS/CSRF;
- idempotency, one-time-secret recovery and concurrency where applicable;
- pagination/cursor current authorization, confidentiality and browser-history-safe transport;
- operation-resource current authorization;
- response-header grammar/cardinality/control-character/duplicate-singleton safety;
- multi-hop response-header serialization when proxies/CDNs/BFFs participate;
- response-cache class/revalidation/non-reuse including protected errors;
- artifact/browser/parser/archive/XML safety where applicable;
- callback raw-body/signature + DTD/XML/SSRF boundary;
- realtime canonical ingress before `101`;
- size/complexity limits;
- secret/topology/confidential URL leakage checks.

### Mandatory structured-entity vectors

At least the applicable vectors exist for body-bearing protected endpoints:

- JSON with two identical `resource_id` members;
- JSON member names that collide under accepted normalization;
- duplicate authorization-relevant `role`, `tenant_id`, action or scope-like body fields where such fields exist;
- multipart repeated singleton part names;
- conflicting `name=`/`filename=` or per-part content metadata;
- malformed/ambiguous outer and nested multipart boundaries;
- repeated multipart fields with explicitly accepted list semantics preserving one deterministic order/rule;
- parser A/parser B differential test proving the canonical profile rejects any input they would interpret differently;
- idempotency fingerprint equals the canonical logical entity, never one parser's arbitrary duplicate choice.

### Mandatory response-header vectors

At least the applicable vectors include:

- CR/LF/NUL/control injection into dynamic `Location`, `Link`, redirect or custom metadata;
- duplicate singleton response header introduced by application + proxy/BFF/CDN;
- conflicting `Content-Disposition` parameters;
- malformed/ambiguous `ETag` or `Retry-After` construction;
- unsafe URI/authority construction in `Location`/redirect;
- list-valued header serialization producing one canonical meaning across hops;
- response-header serialization failure after mutation commit proving no automatic mutation re-execution.

Artifact/binary tests additionally cover media authority, safe filename, active-inline isolation, range/CDN fencing, archive expansion/containment/member collision/no-replace, parser secret/egress isolation, DTD/external-resolution denial and derivative classification.

## Consumer compatibility tests

Critical official clients/BFF flows SHOULD maintain consumer tests against the accepted contract rather than relying only on server unit tests.

A server change that passes internal tests but breaks an accepted client contract is a release defect.

## Breaking/security-sensitive change CI

CI SHALL compare the proposed machine-readable contract and validated semantic manifest against accepted `main`.

It flags likely breaking/security-sensitive changes including:

- removed path/method/response field;
- request requiredness/type or closed-enum changes;
- status/error contract changes;
- HTTP framing/method/trailer/content-coding/connection-rejection profile changes;
- security-sensitive request-header cardinality changes;
- trusted proxy/authority/path/query normalization changes;
- query multiplicity/duplicate behavior changes;
- **structured request entity profile changes**, including duplicate member/part handling, alias normalization, multipart boundary semantics or canonical-entity propagation;
- protocol translation/parser-boundary changes;
- authorization action/scope/authority/input changes;
- BFF origin/credential changes;
- idempotency/retry/concurrency/consistency changes;
- **response-header profile changes**, including grammar, cardinality, serialization owner or multi-hop append/combine behavior;
- response cache/shared-cache/protected-error/variance/revalidation changes;
- cursor confidentiality/token classification/browser transport/logging changes;
- protected query values becoming URL-visible;
- artifact browser/media/filename/active-content changes;
- parser isolation/egress/resource/archive-member/XML policy weakening;
- one-time-secret recovery/cutover weakening.

Automated schema diff is advisory. Reviewers still inspect semantic changes to HTTP parsing, structured entity interpretation, response headers, authorization, idempotency, cache, continuations, artifacts/parsers, callbacks and recovery.

A deployment/framework/gateway/reverse-proxy/parser/CDN change is subject to the same governance if it alters effective semantics even when OpenAPI does not change.

## Release-blocking failures

The following block implementation/release regardless of happy-path tests:

- two accepted HTTP hops can interpret one request differently;
- rejected/ambiguous transport leaves unsafe reusable connection state;
- placement uses a non-canonical path/query;
- duplicate query semantics differ across layers;
- a structured body can produce two logical entities under accepted parsers;
- duplicate/alias JSON members can be first/last/merged differently;
- multipart duplicate/alias parts, per-part metadata or boundaries can make validation/auth/idempotency/use case observe different values;
- request validation or owning authorization reparses raw structured body independently after canonical entity establishment;
- idempotency fingerprint uses a different entity interpretation than authorization/use case;
- unvalidated response data can inject CRLF/control delimiters/additional headers;
- security-relevant singleton response headers can be emitted twice with different meanings across app/proxy/CDN layers;
- dynamic response headers have no declared grammar/cardinality/serialization owner;
- response-header serialization failure after commit can cause automatic duplicate mutation execution;
- physical tenant placement becomes caller-selectable;
- cell-owned authorization occurs before trusted placement/`TenantContext`/request validation;
- owning authorization consumes unvalidated caller-controlled fields;
- long-lived platform credentials reach first-party browser JS;
- BFF trusts wildcard/untrusted credentialed origins;
- secret-bearing responses are cacheable/replayable;
- protected cache can cross principal/tenant boundaries;
- protected cursor/token leaks through browser history/log/referrer policy;
- stale cursor/operation/artifact authority survives revocation;
- artifact browser/parser/archive/XML invariants can be bypassed;
- callback tenant binding/replay/raw-bound/SSRF/XML safety can be bypassed;
- realtime can receive `101` without canonical ingress/current auth/replay single-winner admission;
- a schema-compatible change weakens any accepted security semantic without governed review.

## Golden examples/test vectors

High-risk contracts SHOULD maintain executable vectors for:

- CL/TE and duplicate security-header ambiguity;
- connection reuse after rejection;
- path/query normalization before placement;
- structured JSON/multipart differential parsing;
- canonical body entity -> auth/idempotency/use-case equivalence;
- safe response-header serialization and multi-hop duplication;
- one-time-secret response loss;
- optimistic concurrency;
- protected cache non-reuse;
- protected browser cursor transport;
- active-content artifact isolation;
- archive collision/no-replace behavior;
- DTD/XXE/SSRF rejection;
- callback raw-body/signature equivalence;
- realtime pre-`101` replay admission.

Examples are validated against schema/manifest so docs cannot silently drift.

## SDKs and mocks

Mocks MAY accelerate development but do not prove domain/security semantics.

Official SDKs preserve opaque IDs/cursors/revisions, current authorization semantics, browser-history-safe continuation transport, retry safety, one-time-secret recovery and artifact delivery semantics. SDK behavior does not relax server canonicalization/entity parsing/response-header requirements.

## Security review triggers

Explicit security review is required for material changes to:

- HTTP framing/method/trailer/content-coding/connection reuse;
- path/query/trusted-proxy semantics;
- structured body parser/media profile, duplicate/alias/member/part/boundary semantics or canonical entity propagation;
- authentication/authorization/tenant routing;
- BFF CORS/CSRF/origin;
- cross-tenant capability/direct query/automation;
- idempotency/replay/one-time-secret recovery;
- response-header grammar/cardinality/serialization ownership;
- response cache semantics;
- cursor confidentiality/token transport;
- artifact browser/media/filename/parser/archive/XML handling;
- callback/realtime ingress;
- sensitive data exposure/bulk/export/import bounds.

## ADR/RFC trigger

A contract change requires a new/revised ADR or RFC when it changes a high-impact accepted architecture/security/data decision rather than specializing representation already delegated to Phase 09.

## Proposed-to-accepted promotion

Phase 09 remains `proposed baseline` until the PR receives required architecture/security/contract review and formal governance promotion.

Implementation SHALL NOT treat a proposed Phase 09 choice as permanent compatibility debt before acceptance unless an explicitly temporary experimental contract is approved.
