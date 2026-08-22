# Phase 14 — OPEN Decisions and Acceptance Blockers

**Status:** proposed baseline

## Disposition

```text
OPEN
SATISFIED
NO_APPLICABLE_CASE
```

Unknown applicability remains OPEN.

## OPEN registry

| ID | Decision | Owner | Closure evidence |
|---|---|---|---|
| OPEN-RLS-001 | CI/CD product/mechanism | Platform/Release | least privilege, failure, portability, cost |
| OPEN-RLS-002 | source hosting/merge enforcement implementation | Platform/Governance | branch/ruleset/evidence capability |
| OPEN-RLS-003 | dependency scanner | Security/Release | coverage, false-positive/negative, maintenance |
| OPEN-RLS-004 | SAST/secret scanning release set | Security | coverage and cost evidence |
| OPEN-RLS-005 | build runner/executor | Platform/Security | isolation, identity, reproducibility |
| OPEN-RLS-006 | hermetic/reproducible build mechanism | Release | feasibility and equivalence evidence |
| OPEN-RLS-007 | dependency/package registry | Platform/Security | integrity, availability, provenance |
| OPEN-RLS-008 | artifact/container registry | Platform/Security | immutability, identity, retention, portability |
| OPEN-RLS-009 | SBOM format/tool | Security/Release | component coverage/interoperability |
| OPEN-RLS-010 | provenance/attestation format | Security/Release | binding/verifiability/portability |
| OPEN-RLS-011 | signing mechanism/algorithm | Security/Crypto | threat model and lifecycle evidence |
| OPEN-RLS-012 | signing/verifier KMS/HSM/keyless backend | Security | rotation/revocation/recovery evidence |
| OPEN-RLS-013 | promotion record store/mechanism | Release | atomicity/audit/currentness evidence |
| OPEN-RLS-014 | deployment controller/orchestrator integration | Platform/Release | Phase 13 semantic mapping |
| OPEN-RLS-015 | IaC tool/mechanism | Platform/Release | review, drift, state, recovery evidence |
| OPEN-RLS-016 | physical environment/account/cluster mapping | Platform/Release | Phase 13 isolation + promotion evidence |
| OPEN-RLS-017 | configuration distribution/promotion and validation-to-target evidence mechanism | Platform/Release/Security | exact generation/currentness, semantic-diff/equivalence or target-specific validation, rollback and secret-reference safety evidence |
| OPEN-RLS-018 | secret change orchestration mechanism | Security/Platform | rotation/revocation/least privilege |
| OPEN-RLS-019 | production approval mechanism | Governance/Release | currentness, attribution, bypass controls |
| OPEN-RLS-020 | canary selection mechanism | Release/Platform | bounded target and representativeness |
| OPEN-RLS-021 | rollout wave sizes | Capacity/SRE | runtime evidence |
| OPEN-RLS-022 | rollout durations/soak periods | SRE/Release | failure detection evidence |
| OPEN-RLS-023 | automatic pause thresholds | SRE/Release | Phase 12 runtime evidence |
| OPEN-RLS-024 | automatic abort thresholds | SRE/Release | fault/false-positive evidence |
| OPEN-RLS-025 | schema migration execution tool | Data/Release | locking, privilege, rollback evidence |
| OPEN-RLS-026 | backfill execution/scheduler | Data/Platform | resume/idempotency/capacity evidence |
| OPEN-RLS-027 | deployment/migration coordination store and fencing mechanism | Release/Data | create-or-observe, one-current-transition, stale-executor fencing, ambiguity/recovery evidence |
| OPEN-RLS-028 | emergency approval mechanism | Governance/Security | audit, scope, expiry evidence |
| OPEN-RLS-029 | drift detection implementation | Platform/Release | fidelity, semantics, noise evidence |
| OPEN-RLS-030 | artifact/evidence retention numerics | Governance/Security | legal/incident/recovery/cost evidence |
| OPEN-RLS-031 | release evidence store | Governance/Release | immutability/searchability/retention |
| OPEN-RLS-032 | release evidence signing/anchoring | Security/Governance | tamper/equivocation threat evidence |
| OPEN-RLS-033 | artifact retirement/delete automation | Release/Governance | retention/rollback/incident evidence |
| OPEN-RLS-034 | environment decommission tooling | Platform/Operations | stale-access/data/recovery proof |
| OPEN-RLS-035 | release cost attribution implementation | FinOps/Release | accuracy/cardinality/cost evidence |
| OPEN-RLS-036 | supply-chain portability rehearsal tooling | Release/Governance | alternative implementation evidence |
| OPEN-RLS-037 | trusted release-policy storage/distribution/currentness mechanism | Governance/Security/Release | candidate-independent policy provenance, rollback/recovery and stale-policy rejection |
| OPEN-RLS-038 | running artifact identity/runtime verification mechanism | Platform/Release | observed bytes/immutable identity equivalence, mixed-runtime and failure evidence |
| OPEN-RLS-039 | untrusted-source validation isolation mechanism | Security/Platform/Release | secret/token/network denial, workflow self-escalation tests, bounded cost |

## Fixed properties

Not OPEN:

- one immutable artifact identity is promoted rather than rebuilt per environment;
- the one-artifact rule does not imply one configuration identity across environments;
- each target deployment binds the exact target configuration identity/generation and semantic profile;
- validation evidence for one environment-scoped configuration is reusable for another only with explicit release-relevant semantic compatibility/equivalence evidence or target-specific applicable validation;
- production secret values are not copied into validation to manufacture configuration equality; secret-reference purpose/policy and consuming semantics are compared without disclosing secret material;
- source candidate vs accepted source trust is explicit; branch/event/validation success does not confer trusted release authority;
- untrusted source validation cannot receive production/release/migration/signing authority by trigger or candidate workflow choice;
- the trusted release-policy profile/version used for principal selection and release admission is not controlled unilaterally by the candidate source;
- source/build/artifact/promotion/deployment/runtime verification are distinct trust stages;
- effectful deployment has stable logical operation identity, create-or-observe retry semantics and release-target fencing;
- incompatible concurrent deployments cannot both become current for one target;
- timeout/process death/lost response is not deployment-effect absence and ambiguous outcome must reconcile before retry;
- Phase 14 release-target state remains distinct from Phase 13 placement/runtime/business/security authority;
- release/build/deploy/migration/runtime principals are least-privilege and logically separated;
- mutable tags/locations do not replace artifact identity;
- runtime verification establishes the running artifact identity/equivalent rather than trusting deploy receipt/vendor green alone;
- artifact/provenance mismatch fails closed;
- secret values are excluded from artifacts and ordinary evidence;
- mixed-version compatibility is explicit;
- expand/migrate/contract is preserved;
- cell/runtime/schema-affecting releases preserve the accepted Data staging/reference-cell step as `validation.reference-cell@1` inside `environment.validation@1` unless evidence-backed N/A applies;
- Control Plane cell current/target runtime-schema compatibility metadata remains an explicit placement/rollout safety input rather than deployment-tool inference;
- rollback never erases later authority/effects/evidence;
- restored/rolled-back release policy cannot resurrect retired approval/principal/verifier authority;
- ambiguous external/release effects remain reconciliation-required;
- progressive production rollout is bounded/pauseable/abortable;
- environment label/tool defaults are not release authority;
- drift detection does not silently auto-mutate canonical state;
- CI green is evidence, not merge or release authorization.

## Acceptance blockers

Phase 14 SHALL NOT be accepted while any applicable condition remains:

1. production is rebuilt from source instead of promoting the validated immutable artifact;
2. artifact identity depends only on mutable tag/location;
3. build inputs/toolchain cannot be reconstructed or materially verified;
4. artifact provenance/integrity authenticity is undefined;
5. one CI/CD principal can silently source-edit/build/forge/publish/promote/deploy/migrate/approve itself without bounded independent controls;
6. untrusted/not-yet-accepted source can obtain production/release/migration/signing secrets, privileged network reachability or trusted artifact publication authority by trigger context;
7. candidate workflow/policy can select a broader token/runner/environment/secret inheritance or rewrite the policy that decides its own trust without independent accepted authority;
8. production secrets can enter artifacts/logs/provenance/SBOM;
9. environment mapping grants authority by label;
10. current promotion/deployment/release-policy authority is not revalidated on resume/recovery;
11. runtime admission can bypass Phase 12/13 security/recovery predicates;
12. running artifact identity cannot be proven equivalent to the approved immutable artifact;
13. rollout target scope can be caller-controlled;
14. two incompatible deployment operations can both advance the same protected target or a stale executor can overwrite newer release-target state;
15. deployment timeout/crash/lost response can be treated as no effect or bypassed with a new operation ID before reconciliation;
16. a cell/runtime/schema-affecting release can skip required `validation.reference-cell@1` evidence because tooling lacks a staging concept;
17. stale/caller-controlled cell compatibility metadata can make an incompatible runtime/schema combination placement/deployment eligible;
18. validation evidence can be reused for a materially different target configuration without exact target config identity/profile plus compatibility/equivalence evidence or target-specific validation;
19. production secret copying or matching config key names can be treated as proof that target configuration semantics were validated;
20. mixed-version API/event/schema/runtime/config combinations are unspecified;
21. destructive contract can race supported old runtimes/cell compatibility states;
22. backfill is non-resumable/unbounded or relies on one long ordinary transaction;
23. migration privilege is shared with serving runtime by default;
24. abort/timeout can convert ambiguous external/release effect into absence/retry;
25. rollback can resurrect revoked/erased/retired authority or erase audit/effects;
26. restore/rollback can make retired release-policy/approval/verifier or stale release-target authority current merely because old pipeline state is reachable;
27. emergency change can edit production artifact in place or bypass accountability/fencing;
28. drift auto-fix can silently mutate canonical state;
29. artifact retirement/deletion destroys required evidence unsafely;
30. environment/cell decommission can leave stale placement, credentials, data or routes;
31. release evidence lacks exact source-trust/policy/artifact/target-config/target/profile/operation/target-state/validation-scope/cell-compatibility provenance;
32. applicable `RLV-001..049` vectors lack owner/expected result/evidence;
33. tool/vendor/numeric choices are asserted without evidence or OPEN owner;
34. deterministic/AI/tool status is represented as Phase acceptance, merge authorization or production release authorization.

## Closure rule

Closing an OPEN decision authorizes only the named mechanism within accepted semantics; it does not grant broader Product, Security, merge or release authority.
