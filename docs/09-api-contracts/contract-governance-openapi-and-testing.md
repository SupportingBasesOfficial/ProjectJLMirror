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

OpenAPI/schema alone is not sufficient to capture all JLMIRROR semantics. Each operation also conforms to the Phase 09 idempotency, authorization, consistency, audit, tenant and compatibility declarations.

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
step_up
audit_class
consistency_class
idempotency_class
optimistic_concurrency
retry_class
long_running_operation
request_limits
data_classification
```

This metadata may live in OpenAPI extensions or an adjacent validated manifest. Exact encoding is implementation tooling; the fields/semantics are contract requirements.

## Contract review gate

An endpoint is not ready for implementation until review proves:

1. one owning domain/use case;
2. no database/provider/internal-topology leakage;
3. explicit tenant/global scope;
4. explicit authorization action/scope;
5. request/response schema and bounds;
6. retry/idempotency behavior;
7. concurrency behavior where needed;
8. consistency/result semantics;
9. long-running operation behavior where needed;
10. stable errors;
11. audit/observability requirements;
12. compatibility classification;
13. security/privacy classification;
14. required tests.

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
- success response schema;
- expected error shape/codes;
- authorization/tenant isolation behavior;
- idempotency semantics when applicable;
- concurrency preconditions when applicable;
- pagination/cursor behavior when applicable;
- size/complexity limits;
- secret/topology leakage checks.

## Consumer compatibility tests

Critical official clients/BFF flows SHOULD maintain consumer tests against the accepted contract rather than relying only on server unit tests.

A server change that passes internal tests but breaks an accepted client contract is a release defect.

## Breaking-change CI

CI SHALL compare the proposed machine-readable contract against the accepted `main` baseline.

It flags likely breaking changes such as:

- removed path/method;
- removed/renamed response field;
- request field becoming required;
- type/format changes;
- closed enum changes;
- changed status/error contract;
- incompatible parameter changes.

The diff tool cannot prove semantic compatibility. Reviewers still inspect changes to idempotency, authorization, consistency, ownership and retry behavior.

## Golden examples/test vectors

High-risk contracts SHOULD include executable test vectors/examples for cases such as:

- idempotent replay after response loss;
- idempotency-key fingerprint conflict;
- optimistic concurrency mismatch;
- existence-concealing authorization denial;
- cursor continuation under deterministic sort;
- long-running reconciliation state;
- artifact unavailable/erasure-fencing behavior;
- realtime ticket rejection before `101`.

Examples are validated against schema so documentation cannot silently drift.

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
- never infer physical tenant placement;
- avoid hiding operation-resource semantics behind indefinite polling without cancellation/deadline controls.

## Documentation publishing

Published API reference is generated or checked against the accepted machine-readable contract. Human guides may add workflow explanation but SHALL NOT contradict canonical schemas/semantics.

## Security review triggers

Contract changes require explicit security review when they introduce or materially change:

- authentication/credential transport;
- authorization scope;
- cross-tenant capability;
- direct SQL/data administration;
- automation execution;
- artifact upload/download;
- callback/webhook ingress;
- public projection;
- realtime admission;
- sensitive data exposure;
- bulk/export/import limits;
- idempotency/replay behavior for irreversible effects.

## ADR/RFC trigger

A contract change requires a new/revised ADR or RFC when it changes a high-impact accepted architecture/security/data decision rather than merely specializing a representation already delegated to Phase 09.

For example, changing `/api/v1` field naming does not necessarily require an ADR; changing tenant authority, browser credential boundary, consistency ownership or service extraction semantics does.

## Proposed-to-accepted promotion

Phase 09 documents remain `proposed baseline` until the Phase 09 PR receives the required architecture/security/contract review and formal governance promotion.

Implementation SHALL NOT treat a proposed Phase 09 choice as permanent external compatibility debt before acceptance unless an explicitly temporary experimental contract is approved.