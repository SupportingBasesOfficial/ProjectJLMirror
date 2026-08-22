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
| OPEN-RLS-017 | configuration distribution/promotion mechanism | Platform/Release | generation/currentness/rollback evidence |
| OPEN-RLS-018 | secret change orchestration mechanism | Security/Platform | rotation/revocation/least privilege |
| OPEN-RLS-019 | production approval mechanism | Governance/Release | currentness, attribution, bypass controls |
| OPEN-RLS-020 | canary selection mechanism | Release/Platform | bounded target and representativeness |
| OPEN-RLS-021 | rollout wave sizes | Capacity/SRE | runtime evidence |
| OPEN-RLS-022 | rollout durations/soak periods | SRE/Release | failure detection evidence |
| OPEN-RLS-023 | automatic pause thresholds | SRE/Release | Phase 12 runtime evidence |
| OPEN-RLS-024 | automatic abort thresholds | SRE/Release | fault/false-positive evidence |
| OPEN-RLS-025 | schema migration execution tool | Data/Release | locking, privilege, rollback evidence |
| OPEN-RLS-026 | backfill execution/scheduler | Data/Platform | resume/idempotency/capacity evidence |
| OPEN-RLS-027 | deployment/migration coordination store | Release/Data | fencing/currentness/recovery evidence |
| OPEN-RLS-028 | emergency approval mechanism | Governance/Security | audit, scope, expiry evidence |
| OPEN-RLS-029 | drift detection implementation | Platform/Release | fidelity, semantics, noise evidence |
| OPEN-RLS-030 | artifact/evidence retention numerics | Governance/Security | legal/incident/recovery/cost evidence |
| OPEN-RLS-031 | release evidence store | Governance/Release | immutability/searchability/retention |
| OPEN-RLS-032 | release evidence signing/anchoring | Security/Governance | tamper/equivocation threat evidence |
| OPEN-RLS-033 | artifact retirement/delete automation | Release/Governance | retention/rollback/incident evidence |
| OPEN-RLS-034 | environment decommission tooling | Platform/Operations | stale-access/data/recovery proof |
| OPEN-RLS-035 | release cost attribution implementation | FinOps/Release | accuracy/cardinality/cost evidence |
| OPEN-RLS-036 | supply-chain portability rehearsal tooling | Release/Governance | alternative implementation evidence |

## Fixed properties

Not OPEN:

- one immutable artifact identity is promoted rather than rebuilt per environment;
- source/build/artifact/promotion/deployment/runtime verification are distinct trust stages;
- release/build/deploy/migration/runtime principals are least-privilege and logically separated;
- mutable tags/locations do not replace artifact identity;
- artifact/provenance mismatch fails closed;
- secret values are excluded from artifacts and ordinary evidence;
- mixed-version compatibility is explicit;
- expand/migrate/contract is preserved;
- rollback never erases later authority/effects/evidence;
- ambiguous external effects remain reconciliation-required;
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
6. production secrets can enter artifacts/logs/provenance/SBOM;
7. environment mapping grants authority by label;
8. current promotion/deployment authority is not revalidated on resume;
9. runtime admission can bypass Phase 12/13 security/recovery predicates;
10. rollout target scope can be caller-controlled;
11. mixed-version API/event/schema/runtime/config combinations are unspecified;
12. destructive contract can race supported old runtimes;
13. backfill is non-resumable/unbounded or relies on one long ordinary transaction;
14. migration privilege is shared with serving runtime by default;
15. abort/timeout can convert ambiguous effect into absence/retry;
16. rollback can resurrect revoked/erased/retired authority or erase audit/effects;
17. emergency change can edit production artifact in place or bypass accountability;
18. drift auto-fix can silently mutate canonical state;
19. artifact retirement/deletion destroys required evidence unsafely;
20. environment/cell decommission can leave stale placement, credentials, data or routes;
21. release evidence lacks exact artifact/config/target/profile provenance;
22. applicable `RLV-*` vectors lack owner/expected result/evidence;
23. tool/vendor/numeric choices are asserted without evidence or OPEN owner;
24. deterministic/AI/tool status is represented as Phase acceptance, merge authorization or production release authorization.

## Closure rule

Closing an OPEN decision authorizes only the named mechanism within accepted semantics; it does not grant broader Product, Security, merge or release authority.