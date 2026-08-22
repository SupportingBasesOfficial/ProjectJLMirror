# Phase 13 — Runtime Semantic Manifest

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This manifest is the enforcement-oriented join for Phase 13. It binds runtime roles, worker specialization, logical environment class, identity, lifecycle, isolation, network, state ports, capacity, recovery and accepted Phase 11/12 semantics to stable canonical profile IDs.

Implementation-specific deployment objects MAY map to these records but SHALL NOT weaken or rename their semantics without compatibility review.

## Runtime profile schema

Every implementation runtime record carries:

```text
runtime_profile_id
profile_version
worker_specialization_id when runtime.worker@1
environment_class
principal_class
lifecycle_class
isolation_class
ingress_profile
egress_profile
state_ports
secret_reference_classes
required placement/current-authority checks
resource/concurrency isolation
Phase 11 reliability bindings
Phase 12 health/signal/SLI bindings
recovery/fencing obligations
validation vectors
OPEN decisions
```

The Phase 13 baseline additionally fixes `allowed_environment_classes` per runtime profile.

Omission is not `NO_APPLICABLE_CASE`. A conforming implementation SHALL materialize every field either with an exact canonical binding, fixed rule, explicit OPEN owner, or evidence-backed `NO_APPLICABLE_CASE` with enclosing impact/evidence path.

## Canonical logical environment classes

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Environment class describes logical use/isolation and never grants tenant, Product, placement, credential or data authority by label. Physical account/project/subscription/cluster/namespace/region/promotion mapping remains `OPEN-PRT-035` / Phase 14.

## Canonical environment-to-runtime bindings

| Runtime profile | Allowed environment classes | Special rule |
|---|---|---|
| `runtime.web-bff@1` | `environment.development@1`, `environment.validation@1`, `environment.production@1` | no production credential/traffic authority in lower classes |
| `runtime.api@1` | development, validation, production canonical classes | production authority derives from current principals/placement, not environment label |
| `runtime.worker@1` | development, validation, production canonical classes; `environment.recovery@1` only for `worker.reconciliation@1` under explicit recovery authority | recovery mapping cannot claim normal queued/serving workload ownership |
| `runtime.realtime@1` | development, validation, production canonical classes | no normal realtime serving in recovery class |
| `runtime.control-plane@1` | development, validation, production canonical classes | lower-class control plane cannot own production placement |
| `runtime.automation@1` | development, validation, production canonical classes | Product/target authority remains independently required |
| `runtime.untrusted-parser@1` | development, validation, production canonical classes; recovery only when invoked by an accepted recovery operation | parser never gains recovery authority itself |
| `runtime.migration-admin@1` | development, validation, production canonical classes | Phase 14 controls promotion/invocation; environment label does not grant admin authority |
| `runtime.recovery@1` | `environment.validation@1`, `environment.recovery@1` | recovery environment is not normal production serving state; handoff requires current resumption predicates |
| `runtime.edge-optional@1` | development, validation, production canonical classes | edge presence/absence never creates Product or production authority |

For compactness, `development`, `validation`, `production`, and `recovery` in this table mean the exact canonical IDs above; implementation conformance records store the full canonical ID.

`PRTV-044` applies to every runtime/environment mapping. Production-derived data used outside production requires explicit governed export/minimization evidence; production secrets/workload credentials/placement authority are not lower-environment defaults.

## Canonical principal classes

```text
principal.web-bff@1
principal.application-serving@1
principal.worker@1
principal.realtime@1
principal.control-plane@1
principal.automation@1
principal.untrusted-parser@1
principal.migration-admin@1
principal.recovery@1
principal.edge@1
```

## Canonical ingress profiles

```text
ingress.public-browser@1
ingress.authenticated-api@1
ingress.durable-work@1
ingress.protected-realtime@1
ingress.privileged-platform@1
ingress.privileged-operation@1
ingress.staged-untrusted@1
ingress.release-admin@1
ingress.recovery-authorized@1
ingress.public-edge@1
```

Ingress profile identifies an admission/trust boundary. It does not replace API/domain/current-authority checks.

## Canonical lifecycle classes

```text
lifecycle.serving-replica@1
lifecycle.durable-worker@1
lifecycle.realtime-serving@1
lifecycle.control-plane-serving@1
lifecycle.bounded-operation@1
lifecycle.parser-job@1
lifecycle.privileged-operation@1
lifecycle.recovery-operation@1
lifecycle.edge-serving@1
```

Cell/runtime-generation lifecycle (`provisioning`, `validating`, `admitted`, `active`, `draining`, `quarantined`, `retired`, `failed`) is an enclosing cell-generation admission/fencing lifecycle and remains distinct from these workload/process lifecycle classes and Phase 12 health.

## Canonical secret-reference classes

```text
secretref.none@1
secretref.web-session@1
secretref.state-port@1
secretref.connector@1
secretref.service-communication@1
secretref.signing-verifier-key@1
secretref.migration-admin@1
secretref.recovery@1
```

These identify permitted secret-reference purposes, never secret values. A runtime receives only selected classes and still needs current workload-principal authorization for each concrete reference.

## Canonical resource-isolation profiles

```text
resource.web@1
resource.api@1
resource.worker-specialized@1
resource.realtime@1
resource.control-plane@1
resource.controlled-execution@1
resource.parser@1
resource.migration-admin@1
resource.recovery@1
resource.edge@1
```

Exact numerics remain OPEN, but each profile requires bounded concurrency/resource accounting and Phase 12 saturation evidence appropriate to its workload.

## Canonical runtime identity/lifecycle bindings

| Runtime | Principal | Lifecycle | Isolation | Ingress | Egress | Secret-reference classes | Resource profile |
|---|---|---|---|---|---|---|---|
| `runtime.web-bff@1` | `principal.web-bff@1` | `lifecycle.serving-replica@1` | `isolation.confidential-web@1` | `ingress.public-browser@1` | `egress.platform-bounded@1` | `secretref.web-session@1`, `secretref.service-communication@1` | `resource.web@1` |
| `runtime.api@1` | `principal.application-serving@1` | `lifecycle.serving-replica@1` | `isolation.application-serving@1` | `ingress.authenticated-api@1` | `egress.platform-bounded@1` plus connector capability only through accepted adapter | `secretref.state-port@1`, `secretref.service-communication@1`, connector/signing classes only through accepted owned operation | `resource.api@1` |
| `runtime.worker@1` | `principal.worker@1` | `lifecycle.durable-worker@1` | `isolation.workload-bulkhead@1` | `ingress.durable-work@1` | specialization-specific | specialization-specific | `resource.worker-specialized@1` |
| `runtime.realtime@1` | `principal.realtime@1` | `lifecycle.realtime-serving@1` | `isolation.realtime@1` | `ingress.protected-realtime@1` | `egress.platform-bounded@1` | `secretref.service-communication@1`, `secretref.state-port@1`, signing/verifier class only where accepted | `resource.realtime@1` |
| `runtime.control-plane@1` | `principal.control-plane@1` | `lifecycle.control-plane-serving@1` | `isolation.control-plane@1` | `ingress.privileged-platform@1` | `egress.platform-bounded@1` | `secretref.state-port@1`, `secretref.service-communication@1`, signing/verifier only for owned dependency | `resource.control-plane@1` |
| `runtime.automation@1` | `principal.automation@1` | `lifecycle.bounded-operation@1` | `isolation.controlled-execution@1` | `ingress.privileged-operation@1` | `egress.connector-bounded@1` or `egress.none@1` per operation | `secretref.connector@1`, `secretref.service-communication@1`, `secretref.state-port@1` only as target requires | `resource.controlled-execution@1` |
| `runtime.untrusted-parser@1` | `principal.untrusted-parser@1` | `lifecycle.parser-job@1` | `isolation.untrusted-content@1` | `ingress.staged-untrusted@1` | `egress.none@1` by default | `secretref.none@1` | `resource.parser@1` |
| `runtime.migration-admin@1` | `principal.migration-admin@1` | `lifecycle.privileged-operation@1` | `isolation.privileged-data-admin@1` | `ingress.release-admin@1` | `egress.privileged-bounded@1` | `secretref.migration-admin@1`, narrowly scoped `secretref.state-port@1` | `resource.migration-admin@1` |
| `runtime.recovery@1` | `principal.recovery@1` | `lifecycle.recovery-operation@1` | `isolation.recovery@1` | `ingress.recovery-authorized@1` | `egress.privileged-bounded@1` | `secretref.recovery@1`, affected state-port, signing/verifier only when current recovery authority requires | `resource.recovery@1` |
| `runtime.edge-optional@1` | `principal.edge@1` | `lifecycle.edge-serving@1` | `isolation.edge-untrusted-boundary@1` | `ingress.public-edge@1` | bounded origin/platform egress | `secretref.service-communication@1` only for bounded origin authentication | `resource.edge@1` |

Any additional environment, secret class, egress capability, port or principal power is a semantic compatibility input, not implementation convenience.

## Canonical runtime authority/evidence joins

| Runtime profile | Required ports / authority boundary | Required currentness/admission checks | Accepted Phase 11 reliability bindings | Accepted Phase 12 evidence bindings | Recovery/fencing obligation | Phase 13 vectors | Key OPEN bindings |
|---|---|---|---|---|---|---|---|
| `runtime.web-bff@1` | session/API/realtime-ticket authorities; no tenant DB owner | current session/auth + tenant/placement where required; current credential/config/network policy | `rel.security-session-authority@1`, `rel.performance-cache@1` where cache used | `health.api-bff@1`, `health.security-authority@1`; request/authority signals; API outcome/latency | drain without losing current-authority semantics | `PRTV-001`, `002`, `003`, `004`, `013`, `014`, `016`, `017`, `035`, `037`, `038`, `041`, `042`, `043`, `044` | `OPEN-PRT-003..012`, `023..026`, `035` as applicable |
| `runtime.api@1` | transactional/reliability/audit/observability + bounded ephemeral ports; no migration owner | TenantContext/current placement/auth/config/credential/network policy | transactional/session/cache/config reliability profiles | API/cell/security health; request/config signals; API/cell SLIs | drain/replace without process-local truth | `PRTV-002`, `003`, `004`, `005`, `008`, `009`, `010`, `013`, `014`, `016`, `027`, `028`, `030`, `031`, `035`, `037`, `038`, `039`, `041`, `042`, `043`, `044` | `OPEN-PRT-003..012`, `016`, `018`, `023..026`, `035`, `039` as applicable |
| `runtime.worker@1` | job-event/reliability + specialization ports | tenant/placement/current authority per specialization; current credential/config/network policy; durable work identity | exact specialization binding below | async progress + specialization evidence | drain/lease/redelivery/reconciliation preserves durable responsibility | specialization vectors + `PRTV-037`, `038`, `039`, `042`, `043`, `044`; `041` when secrets exist | `OPEN-PRT-003..018`, `023..029`, `035`, `039` as applicable |
| `runtime.realtime@1` | replay/current-auth/placement/fanout/observability; no general DB owner | current ticket/replay/session/auth/placement + runtime/config/credential/network | realtime/session/replay reliability profiles where accepted | realtime/security health and lifecycle/authority signals | drain/relocation/resync; consumed capability not restored | `PRTV-002`, `003`, `004`, `005`, `008`, `012`, `013`, `014`, `031`, `033`, `035`, `037`, `038`, `039`, `041`, `042`, `043`, `044` | `OPEN-PRT-003..012`, `018`, `023..026`, `035`, `039` as applicable |
| `runtime.control-plane@1` | control-placement/config/identity; no universal tenant DB | current placement/config/security + runtime credential/network | control-plane/placement-cache/config + owned secret-key dependency | control-plane/security health; operation/config/authority signals | stale generation cannot resurrect placement | `PRTV-005`, `006`, `007`, `008`, `009`, `013`, `014`, `015`, `016`, `029`, `030`, `032`, `033`, `035`, `036`, `037`, `038`, `039`, `041`, `042`, `043`, `044` | `OPEN-PRT-001..012`, `021`, `023..031`, `035`, `039` as applicable |
| `runtime.automation@1` | target-scoped credentials, reliability + approved connector/artifact/observability | current operation auth/tenant/target + credential/config/network | privileged + exact external/artifact profile when used | async/security + specialized health; operation state | timeout/cancel remains discoverable; ambiguous effect reconciles | `PRTV-003`, `013`, `014`, `015`, `016`, `018`, `021`, `030`, `031`, `035`, `037`, `038`, `039`, `040`, `041`, `042`, `043`, `044` | `OPEN-PRT-003..015`, `017..019`, `023..026`, `035`, `038`, `039` as applicable |
| `runtime.untrusted-parser@1` | staged input/output only | operation/input + parser profile/config/resource currentness | direct durable reliability N/A; enclosing operation owns it | direct service SLI N/A; enclosing operation/worker evidence | crash/timeout explicit; ephemeral state never acceptance authority | `PRTV-019`, `020`, `030`, `031`, `035`, `037`, `043`, `044` | `OPEN-PRT-003`, `004`, `014`, `026`, `035`, `038` |
| `runtime.migration-admin@1` | dedicated admin mapping + audit; not serving | release/admin scope + schema/config/runtime/credential/network generations/fences | privileged + owning transactional/config profiles | security/async health and operation/authority signals | rollback cannot restore stale authority | `PRTV-003`, `013`, `014`, `015`, `016`, `022`, `023`, `024`, `030`, `031`, `034`, `035`, `037`, `038`, `039`, `041`, `042`, `043`, `044` | `OPEN-PRT-003`, `004`, `009`, `010`, `012`, `016`, `026`, `033`, `035`, `039` |
| `runtime.recovery@1` | current recovery/security/governance, reliability/audit + affected ports | recovery auth + current placement/security/governance/key/reliability + runtime/config/credential/network | privileged/control-plane/replay/secret-key + affected profile | recovery/security + affected health; reconciliation/authority/operation signals | `(R,F]`, quarantine, revalidation before handoff | `PRTV-005`, `008`, `009`, `015`, `016`, `025`, `026`, `027`, `029`, `031`, `033`, `035`, `037`, `038`, `039`, `041`, `042`, `043`, `044` | `OPEN-PRT-002..012`, `016..020`, `026..035`, `037`, `039` as applicable |
| `runtime.edge-optional@1` | optional filter/routing only; no business state-port authority | current origin routing/network/credential; no tenant authority from edge | direct business reliability N/A; origin owns protected semantics | direct canonical service-health authority N/A; origin carries impact | replacement/loss cannot change canonical semantics | `PRTV-001`, `002`, `004`, `030`, `035`, `036`, `037`, `043`, `044` | `OPEN-PRT-001..007`, `011..013`, `023..026`, `035..037` as applicable |

OPEN ranges constrain candidate implementation decisions. A concrete implementation expands the range to exact selected `OPEN-PRT-*` IDs and records each disposition/evidence; ranges are not implementation-time defaults.

## Canonical worker specialization join

Every concrete `runtime.worker@1` declares exact worker specialization IDs. Each selected specialization receives separate queue/transport ownership, ports, secret/egress permissions and concurrency/bulkhead accounting even when co-located.

| Worker specialization | Required ports | Egress / secret-reference classes | Accepted reliability bindings | Specialized Phase 12 evidence | Additional vectors / resource rule |
|---|---|---|---|---|---|
| `worker.outbox-publication@1` | job-event, reliability, owning transactional outbox | platform egress; state/service refs | outbox + broker transport | async health/progress SLI | `PRTV-011`, `027`, `030`, `031`, `039`, `042`, `043`; independent worker budget |
| `worker.async-consumer@1` | job-event, reliability, owning transactional effect port | platform egress unless accepted connector; state/service refs | inbox-effect + broker | async + message-equivalence where applicable | `PRTV-005`, `011`, `026`, `028`, `030`, `031`, `039`, `042`, `043`; independent budget |
| `worker.provider-integration@1` | job-event, reliability, transactional/observability | connector egress; connector/state/service refs | external-provider + exact transport/effect | provider + async health/provider SLI | `PRTV-011`, `015`, `018`, `030`, `031`, `039`, `041`, `042`, `043`; provider/destination bulkhead |
| `worker.webhook-delivery@1` | job-event, reliability, observability | connector egress; connector/signing refs as accepted | webhook delivery | webhook health; Product-gated SLI unchanged | `PRTV-011`, `015`, `017`, `018`, `030`, `031`, `039`, `041`, `042`, `043`; destination/tenant bulkhead |
| `worker.reporting-export@1` | job-event, reliability, report/transactional, artifact/staging when protected | platform egress; state/service refs | reporting-derived + artifact when applicable | async/artifact health | `PRTV-011`, `015`, `030`, `031`, `039`, `040`, `041`, `042`, `043`; export bulkhead |
| `worker.customer-telemetry@1` | job-event, reliability, customer-telemetry | platform egress; state/service refs | customer-telemetry acceptance | customer-telemetry health/SLI | `PRTV-011`, `030`, `031`, `039`, `042`, `043`; telemetry bulkhead |
| `worker.artifact-lifecycle@1` | job-event, reliability, artifact, object staging | platform egress; state/storage refs through port mapping | artifact storage | artifact health; Product delivery applicability unchanged | `PRTV-011`, `015`, `025`, `030`, `031`, `039`, `040`, `041`, `042`, `043`; artifact bulkhead |
| `worker.reconciliation@1` | reliability + exact affected ports; job transport when durable | bounded platform/connector only when affected operation requires; secret classes from owner | exact affected reliability; privileged only when required | recovery or async health; recovery SLI only when recovery-owned | `PRTV-008`, `025`, `026`, `029`, `030`, `031`, `038`, `039`, `042`, `043`; affected-scope bulkhead |

All worker specializations inherit `PRTV-044` from the selected runtime/environment mapping. `PRTV-037` applies whenever multiple specializations are co-located; `PRTV-041` applies to any specialization receiving secret material.

## Canonical isolation profiles

```text
isolation.confidential-web@1
isolation.application-serving@1
isolation.workload-bulkhead@1
isolation.realtime@1
isolation.control-plane@1
isolation.controlled-execution@1
isolation.untrusted-content@1
isolation.privileged-data-admin@1
isolation.recovery@1
isolation.edge-untrusted-boundary@1
```

## Canonical egress profiles

```text
egress.none@1
egress.platform-bounded@1
egress.connector-bounded@1
egress.privileged-bounded@1
```

## Canonical cell-generation lifecycle records

```text
provisioning
validating
admitted
active
draining
quarantined
retired
failed
```

Replacement is multi-generation; predecessor/successor remain distinct. Phase 12 health remains separate.

## Canonical generation set

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

These do not replace upstream authorization/revocation, schema, artifact-delivery, replay, governance or cryptographic/verifier generations.

## Canonical state ports

```text
port.control-placement@1
port.transactional@1
port.reliability-state@1
port.audit@1
port.customer-telemetry@1
port.artifact@1
port.ephemeral@1
port.job-event-transport@1
port.observability@1
port.secret-key@1
port.object-staging@1
```

Vendor client/endpoint/SDK identifiers never become canonical port IDs.

## Join completeness rules

- every implementation runtime record includes exact `environment_class` and the class must be allowed for the runtime profile;
- every runtime schema field is instantiated through exact binding/fixed rule/OPEN/N/A;
- every selected worker declares exact specialization and inherits runtime-level plus specialization bindings;
- every specialization declares ports, egress/secret classes, reliability, Phase 12 evidence, resource rule and vectors;
- conditional binding names the accepted owner; implementation presence is insufficient;
- N/A requires reason and enclosing impact/evidence path;
- implementation OPEN bindings expand to exact IDs when selected;
- vendor/orchestrator readiness/health fields are adapters, not Phase 12 replacements;
- `PRTV-037..044` are cross-cutting and cannot be omitted where applicable.

## Co-location decision record

Any co-location records selected profiles/specializations, effective principal, secret/state-port union, network/egress union, resource/bulkhead enforcement, lifecycle/drain compatibility, blast radius and why no profile is weakened. Absent evidence, profiles remain separated.

## Product applicability

Runtime/environment implementation SHALL NOT resolve `OPEN-OBS-037` or other Product OPEN decisions by deploying/not deploying a component.

## Manifest blockers

Acceptance is blocked when a runtime schema/environment field is missing/implicit; a runtime/worker row lacks upstream/evidence/vector bindings; environment class grants production authority or allows ungoverned data/credential bleed; vendor resource names replace canonical identities; co-location broadens authority; network presence is trust; lifecycle/health collapse; quarantine bypasses revalidation; replacement conflates generations; one generation becomes universal authority; physical port co-location merges authority; object presence becomes artifact release authority; secret material leaks; privileged/parser/automation profiles inherit broad authority; physical/environment topology enters canonical tenant/API/event/resource identity; or Product scope is inferred from runtime/environment state.