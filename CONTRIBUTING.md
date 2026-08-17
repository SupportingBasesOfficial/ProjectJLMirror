# Contributing to JLMIRROR

JLMIRROR is specification-first. A change is not accepted merely because it works locally; it must preserve the product invariants, domain ownership, security boundaries, tenant isolation, operability, and documented contracts.

## Change classes

- **Editorial:** wording or formatting without semantic change.
- **Product:** capabilities, actors, scope, business rules, or acceptance criteria.
- **Architecture:** boundaries, data ownership, communication, runtime, infrastructure, security, reliability, or deployment.
- **Contract:** API, event, job, webhook, schema, or interoperability change.
- **Implementation:** code that realizes an accepted design.

Product and architecture changes require an ADR or RFC when they alter a significant decision or cross-cutting contract.

## Pull requests

Every pull request must state:

1. the problem being solved;
2. the affected canonical documents;
3. the invariants that could be impacted;
4. validation performed;
5. rollout or migration considerations when applicable.

Implementation must not silently redefine product or architecture. If code and canonical specification disagree, resolve the specification decision explicitly rather than treating the code as authoritative.

## Branches

Use focused branches such as `docs/...`, `feat/...`, `fix/...`, `refactor/...`, `security/...`, or `infra/...`.

## Commits

Prefer Conventional Commit-style messages, for example `docs: define product scope`, `feat: add tenant resolver`, `fix: prevent cross-tenant cache key collision`.

## Security

Never commit secrets, customer data, production topology, private credentials, real tokens, or unrestricted connection strings.