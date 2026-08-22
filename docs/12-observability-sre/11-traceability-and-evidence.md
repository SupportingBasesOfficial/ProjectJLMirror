# Phase 12 — Traceability and Evidence

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This document binds Phase 12 claims to accepted upstream authority and identifies downstream consumers/evidence obligations.

## Upstream traceability

| Upstream authority | Phase 12 obligation |
|---|---|
| ADR-014 | OTel-compatible context/semantic propagation; separate signals; audit separation; redaction/cardinality; reconstructable synthetic flow |
| QA-OBS-001 | request -> persistence -> queue -> worker -> integration diagnosis without secrets |
| QA-SEC-001 / SEC-SEC-002 | zero secret leakage in errors/logs/traces/metrics/audit snapshots |
| SEC-TEN-003 | tenant-isolation semantics in observability dimensions |
| SEC-AUD-001..004 | audit separate, protected accountability evidence |
| accepted telemetry plane | customer monitoring durable acceptance/current projections remain distinct from platform observability |
| Phase 09 request/error contracts | server request ID, bounded correlation, safe URL/query/error telemetry |
| Phase 10 message contracts | message/correlation/causation/replay identities, tenant/classification semantics and protected duplicate-equivalence evidence rules |
| Phase 11 reliability profiles | every exact `rel.*@version` profile receives an explicit Phase 12 signal/health/SLI/alert/fault join without redefining its failure/degradation semantics |
| Phase 11 message-equivalence continuity | temporary comparison dependency outage, historical continuity loss and compromised trust remain distinguishable and non-authoritative in telemetry |
| Review and Assurance Governance | exact-state evidence; tools observe/report/block but do not silently mutate or authorize merge |

## Canonical reliability-profile evidence join

`10-observability-semantic-manifest.md` is the mandatory same-key join for the complete accepted Phase 11 reliability-profile set.

Traceability completeness is evaluated over the set of accepted Phase 11 keys, not over prose topics. For each key, evidence SHALL establish:

```text
Phase 11 reliability_profile_id@version
 -> Phase 12 diagnostic signal binding
 -> health binding
 -> SLI applicability decision
 -> alert applicability decision
 -> validation/fault vectors
 -> security/cardinality constraints
```

A later Phase 11 profile addition/change is therefore a compatibility input to Phase 12. Conformance remains incomplete until the join is updated or an evidence-backed successor mapping exists.

For a direct `no_applicable_case` SLI/alert decision, evidence SHALL show why treating the reliability correctness property as an SLO/error-budget or ordinary alert would be semantically wrong/redundant and which consuming service outcome captures operational impact where applicable.

## Message-equivalence evidence trace

The duplicate-sensitive chain is explicitly:

```text
Phase 10 protected equivalence evidence
 -> Phase 11 rel.consumer-inbox-effect@1 / rel.replay-consume-state@1
 -> Phase 11 comparison authority dependency where applicable
 -> Phase 12 obs.message-equivalence.admission@1
 -> Phase 12 obs.message-equivalence.verifier@1
 -> health.message-equivalence@1
 -> OBSV-031..036
```

The Phase 12 evidence proves **visibility of the accepted state**, not message equality itself. Authoritative duplicate/effect/replay decisions remain in their Phase 10/11 owning authorities.

Evidence SHALL demonstrate that telemetry cannot be used as a cross-tenant/cross-consumer equality oracle and that comparison-work observability remains bounded.

## Downstream consumers

### Phase 13 — Platform & Runtime

Consumes:

- workload-specific health/readiness semantics;
- observability identity/network/security requirements;
- signal production/collection capability requirements;
- pipeline backpressure/resource-isolation requirements;
- runtime generation/config correlation properties;
- protected comparison-health emission/query boundaries without learning equality authority.

Phase 13 maps these to runtime topology but cannot redefine them.

### Phase 14 — Deployment & Release

Consumes:

- health/readiness/degradation signals for rollout admission;
- SLI/error-budget semantics;
- compatibility/profile versioning;
- telemetry/security release blockers;
- exact release evidence requirements.

A green dashboard is not release authority by itself.

### Phase 15 — Operations & Incident Readiness

Consumes:

- alert action classes/ownership;
- diagnostic entry-point requirements;
- health/recovery semantics;
- signal retention/access constraints;
- synthetic/game-day evidence obligations.

Phase 15 supplies concrete runbooks/on-call/incident process.

## Evidence matrix

| Claim | Design evidence now | Future conformance/runtime evidence |
|---|---|---|
| correlation continuity | Phase 12 propagation contract | synthetic end-to-end traces + break injection |
| no secret leakage | security/cardinality contract | automated leakage/adversarial tests |
| bounded cardinality | profile/manifest constraints | load/skew/cardinality measurements |
| health distinction | health contract | dependency/recovery/drain fault tests |
| SLI validity | formula/population/missing-data contract | baseline and runtime measurement |
| alert actionability | alert contract | injected incidents + alert-quality evaluation |
| telemetry pipeline resilience | capacity/pipeline contract | outage/backpressure/drop/load tests |
| compatibility | change classification | mixed-version/rollback tests |
| recovery visibility | health/manifest/recovery signals | restore/reconciliation rehearsal |
| complete Phase 11 coverage | canonical 20-profile join in manifest | machine/static join completeness validation |
| duplicate-sensitive comparison visibility | manifest + health/security rules + OBSV-031..036 | outage/continuity/trust/equality-oracle/load fault tests |

## Permanent evidence requirements

Implementation/release evidence SHALL preserve enough provenance to identify:

- repository/source state;
- semantic profile/config version;
- test/scanner/runtime profile where material;
- relevant environment/runtime identity;
- result and timestamp/order;
- whether evidence is design, conformance, release or production evidence.

Evidence for one profile/HEAD/configuration is not silently reused for a materially different one.

## Evidence integrity

Observability evidence can itself be incomplete, delayed, sampled, duplicated or compromised. Therefore:

- absence is not success by default;
- provenance/config identity matters;
- health/SLI consumers declare missing-data behavior;
- evidence pipelines have their own integrity signals;
- no single telemetry backend becomes unreviewed system-of-record authority for business/security/recovery truth;
- a healthy comparison-telemetry path is not proof that historical equivalence was established;
- missing comparison telemetry is not proof of non-duplication or retry eligibility.

## Native Assurance integration

Phase 12 review follows the accepted Native Assurance Gate. Deterministic GitHub Actions results are additional exact-SHA evidence, not normative authority.

A new HEAD after any correction requires applicable checks and semantic review to run again. External reviewer quota/outage is operational context only.

## Traceability blockers

Acceptance is blocked when a fixed Phase 12 property has no upstream authority/rationale, when an accepted Phase 11 profile lacks an explicit manifest join, or when a critical downstream consumer would need to invent its own incompatible meaning.
