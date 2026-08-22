# Phase 13 — OPEN Decisions and Acceptance Blockers

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This registry preserves runtime/platform choices that require implementation, benchmark, security, cost, portability or operational evidence. `OPEN` is not permission for vendor defaults to decide architecture silently.

## Disposition vocabulary

An item may become:

```text
OPEN
SATISFIED
NO_APPLICABLE_CASE
```

`NO_APPLICABLE_CASE` requires explicit condition, owning authority and evidence. Unknown applicability is OPEN.

## OPEN registry

| ID | Decision | Owner | Required evidence / closure gate |
|---|---|---|---|
| OPEN-PRT-001 | cloud/provider implementation | Phase 13/implementation governance | capability, portability, security, residency, cost and failure evidence |
| OPEN-PRT-002 | physical region/availability-zone topology | Product/Platform/Recovery | residency, failure-domain, latency, recovery and cost evidence |
| OPEN-PRT-003 | orchestrator/scheduler product | Platform | lifecycle, identity, isolation, portability and operational evidence |
| OPEN-PRT-004 | container/VM/process/serverless runtime mechanisms by profile | Platform/Security | workload compatibility, isolation and lifecycle evidence |
| OPEN-PRT-005 | service-discovery implementation | Platform/Security | authentication, stale endpoint, failure and portability evidence |
| OPEN-PRT-006 | service-mesh adoption or no-mesh decision | Platform/Security | identity/policy value vs complexity/failure/cost evidence |
| OPEN-PRT-007 | ingress/load-balancing product/topology | Platform/Security | routing, health, connection, DDoS/WAF and portability evidence |
| OPEN-PRT-008 | workload-identity issuer/protocol/mechanism | Security/Platform | revocation, rotation, attestation/trust, portability evidence |
| OPEN-PRT-009 | secret-manager/KMS implementation | Security/Platform | least privilege, rotation, recovery, historical verification and portability evidence |
| OPEN-PRT-010 | configuration-distribution mechanism | Platform | currentness, generation, outage, rollback and scale evidence |
| OPEN-PRT-011 | internal service-authentication protocol details | Security/Platform | identity, revocation, latency, interoperability evidence |
| OPEN-PRT-012 | network-policy enforcement mechanism | Security/Platform | deny/boundary semantics, stale policy, audit and portability evidence |
| OPEN-PRT-013 | external-egress proxy/gateway architecture | Security/Platform | SSRF/redirect/DNS/failure/isolation/cost evidence |
| OPEN-PRT-014 | untrusted-parser sandbox technology | Security/Platform | escape resistance, resource isolation, startup cost, portability evidence |
| OPEN-PRT-015 | automation execution sandbox/runtime technology | Security/Automation/Platform | target isolation, credential/network/resource controls |
| OPEN-PRT-016 | transactional database product/pooler runtime mapping beyond accepted data semantics | Data/Platform | transaction/isolation/tenant/recovery/scale evidence |
| OPEN-PRT-017 | durable broker/job transport product | Platform/Async | Phase 10/11 conformance, isolation, recovery, cost evidence |
| OPEN-PRT-018 | cache/coordination/replay primitive product | Platform | authority classification, fencing, loss/recovery and capacity evidence |
| OPEN-PRT-019 | object/artifact storage product/runtime integration | Platform/Data/Security | lifecycle/fence/erasure/residency/cost evidence |
| OPEN-PRT-020 | customer telemetry storage/runtime mapping | Monitoring/Platform | accepted telemetry semantics, scale, tenant, recovery and cost evidence |
| OPEN-PRT-021 | cell count and initial physical cell topology | Platform/Product | load, failure-domain, residency and cost evidence |
| OPEN-PRT-022 | dedicated-cell placement trigger policy numerics | Product/Platform/Capacity | tenant skew, compliance, workload and cost evidence |
| OPEN-PRT-023 | runtime replica counts by profile | Platform/Capacity | load/failure/startup/maintenance evidence |
| OPEN-PRT-024 | node/instance sizing | Platform/Capacity | benchmark, saturation, cost and failure evidence |
| OPEN-PRT-025 | autoscaling signals, formulas and thresholds | Platform/SRE/Capacity | workload lag/concurrency/latency/cost evidence |
| OPEN-PRT-026 | runtime resource limit/request numerics | Platform/Capacity | load, OOM/throttling, latency and noisy-neighbor evidence |
| OPEN-PRT-027 | workload scheduling/anti-affinity/failure-domain placement rules | Platform/Reliability | blast-radius and maintenance evidence |
| OPEN-PRT-028 | coordinator/lease/leader-election primitive | Platform/Reliability | stale leader fencing, failover and ambiguity evidence |
| OPEN-PRT-029 | placement/config last-known-good cache numerics | Platform/Reliability/Security | outage and stale-authority risk evidence |
| OPEN-PRT-030 | cell bootstrap/provisioning automation mechanism | Platform | reproducibility, identity, secret, conformance evidence |
| OPEN-PRT-031 | cell runtime admission/conformance implementation | Platform/Governance | exact profile validation and evidence provenance |
| OPEN-PRT-032 | relocation data-copy/backfill runtime mechanism | Data/Platform/Recovery | consistency, capacity, fence and rollback evidence |
| OPEN-PRT-033 | migration/admin execution mechanism | Data/Platform/Security | privilege segregation, compatibility, locking/load evidence |
| OPEN-PRT-034 | recovery execution mechanism and physical recovery environment | Recovery/Security/Platform | isolation, access, audit, current-authority continuity evidence |
| OPEN-PRT-035 | physical account/project/subscription/cluster/namespace mapping and Phase 14 promotion mapping for accepted logical environment classes | Phase 14/Platform | promotion, isolation, parity, security, cost and rollback evidence |
| OPEN-PRT-036 | runtime portability/conformance automation tooling | Platform/Governance | multi-implementation mapping quality and maintenance evidence |
| OPEN-PRT-037 | private-connectivity/VPN/peering implementation where required | Security/Platform | trust-boundary, routing, residency and failure evidence |
| OPEN-PRT-038 | runtime filesystem/ephemeral workspace implementation | Platform/Security | classification, cleanup, performance and isolation evidence |
| OPEN-PRT-039 | concrete runtime generation/fence storage/propagation mechanism | Platform/Reliability | stale-instance rejection, restore and replacement evidence |
| OPEN-PRT-040 | runtime cost allocation/chargeback implementation | FinOps/Platform | safe dimensions, accuracy, cardinality and business evidence |

## Upstream OPEN ownership

Phase 13 does not duplicate or silently close upstream OPEN decisions. Examples include Phase 12 observability backend/sampling/retention/SLO decisions and Product applicability `OPEN-OBS-037`. Phase 13 runtime presence or vendor selection is not closure evidence for those items unless the owning authority accepts it through its own governance.

## Fixed logical environment classes — not OPEN

Phase 13 fixes:

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Their logical semantics and isolation/authority rules are fixed. `OPEN-PRT-035` owns only physical mapping/promotion implementation, not whether these environment classes exist or what their authority semantics mean.

An environment label is not authorization, placement, Product or tenant authority. Non-production cannot inherit production secrets/data/traffic by convenience. Recovery environment is not normal production serving state and must satisfy current resumption predicates before handoff.

## Fixed properties — not OPEN

The following are fixed by Phase 13:

- core application semantics cannot depend on edge-only runtime constraints;
- runtime roles have explicit principal/isolation/lifecycle/network/state-port profiles;
- every runtime manifest schema field has an exact binding, fixed rule, explicit OPEN owner or evidence-backed `NO_APPLICABLE_CASE`; unnamed vendor/default behavior is not a valid value;
- every concrete `runtime.worker@1` declares exact `worker_specialization_id` values and per-specialization privilege/port/egress/resource budgets;
- logical environment classes and their non-authoritative isolation semantics are fixed;
- network presence is not trust;
- service identity is not tenant authorization;
- caller/provider/message physical routing does not select authoritative placement;
- serving processes do not keep authoritative business/recovery truth only in memory;
- ordinary source/configuration uses secret references, not production secret values;
- runtime secret material is excluded from ordinary config snapshots/signals/events/jobs/artifacts/audit snapshots;
- serving application privilege is distinct from migration/admin/recovery privilege where applicable;
- untrusted parsing/controlled execution use smaller trust envelopes;
- co-location cannot silently create a union principal/secret/state/egress authority;
- cells support provision/validate/admit/drain/replace/relocate capabilities under stable logical contracts;
- `quarantined` generations revalidate through owning authority predicates before normal protected admission;
- predecessor/successor replacement generations remain distinguishable and retired generations do not become active again;
- `runtime_generation`, `configuration_generation`, `workload_credential_generation`, `placement_version` and `network_policy_generation` remain distinct; upstream generations keep their owners;
- state ports preserve accepted logical ownership and authority/failure/recovery semantics even when physically co-located;
- object presence/upload success/direct storage capability does not grant protected artifact release authority;
- stale runtime/config/network generations cannot override current placement/security/governance authority;
- capacity is multidimensional and noisy-neighbor/runaway work is bounded;
- physical topology and environment physical mapping do not enter canonical tenant/API/event/resource identity;
- Product applicability is not inferred from deployed runtime/environment state;
- exact-state evidence and separate merge authorization remain mandatory.

## Acceptance blockers

Phase 13 SHALL NOT be accepted while any applicable condition remains:

1. a runtime role lacks explicit principal, isolation, lifecycle, network or state-port boundaries;
2. any required runtime manifest field is missing, implicit, derived from an unnamed vendor/default, or lacks an exact binding/fixed rule/OPEN/N/A disposition;
3. a concrete `runtime.worker@1` lacks an exact worker specialization or its specialization lacks explicit reliability/evidence/privilege/port/egress/resource bindings;
4. logical environment classes are undefined, physically conflated with authority, or allow non-production/recovery labels to grant production capability;
5. production secrets/data/tenant traffic can flow to lower environment classes without explicit governed authority/minimization;
6. an implementation requires edge-only runtime behavior for core domain correctness;
7. internal network reachability can replace workload authentication/application authority;
8. machine/service identity can become implicit wildcard tenant authorization;
9. callers/messages/providers can choose physical tenant placement;
10. stale placement/runtime/config/network authority can be admitted as current without owning evidence;
11. one generation identity can substitute for another currentness/authority dimension;
12. cell lifecycle collapses into one liveness/readiness boolean;
13. quarantined runtime can return directly to active without revalidating owning current-authority predicates;
14. replacement collapses predecessor/successor generations or allows a retired generation to regain normal authority;
15. drain/restart/scale-down can erase or repeat durable protected effects blindly;
16. secret values are stored in ordinary config/events/jobs/signals/artifacts/audit snapshots or shared broadly across profiles;
17. serving application roles hold migration/admin/recovery super-authority by default;
18. co-location of runtime profiles/worker specializations silently unions principal, secret, state-port, egress or failure/resource authority;
19. untrusted parsing or automation has unrestricted secret/state/network access;
20. connector egress lacks bounded destination/redirect/protocol/response/concurrency controls;
21. a state-port mapping weakens accepted transaction/durability/fencing/recovery semantics;
22. physical co-location of state ports collapses audit, transactional, reliability, telemetry or other logical authorities;
23. cache/broker/vendor behavior is treated as business-correctness authority without accepted owner contract;
24. artifact/object bytes or storage capability can be released without current artifact lifecycle/delivery-generation/lease/governance authority;
25. recovery/restored runtime can reactivate retired security/governance/placement authority;
26. cell replacement/relocation cannot fence stale source/runtime authority;
27. second-cell provisioning would require canonical tenant/API/event identity changes;
28. capacity uses one scalar and leaves tenant/workload/provider/recovery skew unbounded;
29. coordinator/leader failure can create concurrent protected authority without fencing;
30. vendor health/readiness semantics can redefine accepted Phase 12 health/quarantine meaning;
31. vendor replacement requires semantic contract rewrite rather than adapter/conformance mapping;
32. runtime deployment/configuration/environment label is represented as Product or application authority;
33. any applicable cross-cutting vector `PRTV-037..044` is absent from the owning runtime/worker/environment manifest binding or lacks expected outcome/evidence;
34. validation/fault vectors otherwise lack owner/expected outcome/evidence path;
35. a technology/numeric/physical-environment choice is asserted without evidence or explicit OPEN ownership;
36. deterministic/AI/vendor-tool green status is represented as Phase acceptance or merge authorization.

## Closure rule

Closing an OPEN item authorizes only the named implementation/mechanism decision within the accepted Phase 13 properties. It does not grant broader Product, release or operational authority.