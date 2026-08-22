# Phase 13 — Runtime Semantic Manifest

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This manifest is the enforcement-oriented join for Phase 13. It binds runtime roles, worker specialization, identity, lifecycle, isolation, network, state ports, capacity, recovery and accepted Phase 11/12 semantics to stable canonical profile IDs.

Implementation-specific deployment objects MAY map to these records but SHALL NOT weaken or rename their semantics without compatibility review.

## Runtime profile schema

Every runtime profile records:

```text
runtime_profile_id
profile_version
worker_specialization_id when runtime.worker@1
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

Omission is not `NO_APPLICABLE_CASE`. A conforming implementation SHALL materialize every field either with an exact canonical binding, an explicit fixed rule, an explicit OPEN owner, or an evidence-backed `NO_APPLICABLE_CASE` with enclosing impact/evidence path.

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

A principal class defines maximum logical authority for the runtime profile. Concrete workload credentials rotate underneath it.

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

Ingress profile identifies an admission/trust boundary. It does not replace the API/domain/current-authority checks inside that boundary.

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

Cell/runtime-generation lifecycle (`provisioning`, `validating`, `admitted`, `active`, `draining`, `quarantined`, `retired`, `failed`) is an enclosing cell-generation admission/fencing lifecycle and remains distinct from these workload/process lifecycle classes and from Phase 12 health.

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

These identify permitted secret-reference purposes, never secret values. A runtime receives only the selected classes and still needs current workload-principal authorization for each concrete reference.

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
| `runtime.api@1` | `principal.application-serving@1` | `lifecycle.serving-replica@1` | `isolation.application-serving@1` | `ingress.authenticated-api@1` | `egress.platform-bounded@1` plus connector capability only through accepted adapter | `secretref.state-port@1`, `secretref.service-communication@1`, connector/signing classes only through an accepted owned operation | `resource.api@1` |
| `runtime.worker@1` | `principal.worker@1` | `lifecycle.durable-worker@1` | `isolation.workload-bulkhead@1` | `ingress.durable-work@1` | specialization-specific | specialization-specific | `resource.worker-specialized@1` |
| `runtime.realtime@1` | `principal.realtime@1` | `lifecycle.realtime-serving@1` | `isolation.realtime@1` | `ingress.protected-realtime@1` | `egress.platform-bounded@1` | `secretref.service-communication@1`, `secretref.state-port@1`, signing/verifier class only where accepted capability requires it | `resource.realtime@1` |
| `runtime.control-plane@1` | `principal.control-plane@1` | `lifecycle.control-plane-serving@1` | `isolation.control-plane@1` | `ingress.privileged-platform@1` | `egress.platform-bounded@1` | `secretref.state-port@1`, `secretref.service-communication@1`, signing/verifier class only for owned dependency | `resource.control-plane@1` |
| `runtime.automation@1` | `principal.automation@1` | `lifecycle.bounded-operation@1` | `isolation.controlled-execution@1` | `ingress.privileged-operation@1` | `egress.connector-bounded@1` or `egress.none@1` per accepted operation | `secretref.connector@1`, `secretref.service-communication@1`, `secretref.state-port@1` only as target profile requires | `resource.controlled-execution@1` |
| `runtime.untrusted-parser@1` | `principal.untrusted-parser@1` | `lifecycle.parser-job@1` | `isolation.untrusted-content@1` | `ingress.staged-untrusted@1` | `egress.none@1` by default | `secretref.none@1` | `resource.parser@1` |
| `runtime.migration-admin@1` | `principal.migration-admin@1` | `lifecycle.privileged-operation@1` | `isolation.privileged-data-admin@1` | `ingress.release-admin@1` | `egress.privileged-bounded@1` | `secretref.migration-admin@1`, narrowly scoped `secretref.state-port@1` | `resource.migration-admin@1` |
| `runtime.recovery@1` | `principal.recovery@1` | `lifecycle.recovery-operation@1` | `isolation.recovery@1` | `ingress.recovery-authorized@1` | `egress.privileged-bounded@1` | `secretref.recovery@1`, affected `secretref.state-port@1`, `secretref.signing-verifier-key@1` only when current recovery authority requires it | `resource.recovery@1` |
| `runtime.edge-optional@1` | `principal.edge@1` | `lifecycle.edge-serving@1` | `isolation.edge-untrusted-boundary@1` | `ingress.public-edge@1` | bounded origin/platform egress | `secretref.service-communication@1` only for bounded origin authentication where selected | `resource.edge@1` |

Any additional secret class, egress capability, port or principal power is a semantic compatibility input, not an implementation convenience.

## Canonical runtime authority/evidence joins

| Runtime profile | Required ports / authority boundary | Required currentness/admission checks | Accepted Phase 11 reliability bindings | Accepted Phase 12 evidence bindings | Recovery/fencing obligation | Phase 13 vectors | Key OPEN bindings |
|---|---|---|---|---|---|---|---|
| `runtime.web-bff@1` | session/API/realtime-ticket authorities; no tenant DB owner | current session/auth + tenant/placement where contract requires; current workload credential/config/network policy | `rel.security-session-authority@1`, `rel.performance-cache@1` where cache used | `health.api-bff@1`, `health.security-authority@1`; `obs.request.outcome@1`, `obs.security.authority-freshness@1`; `sli.api.outcome@1`, `sli.api.latency@1` | drain without losing session/current-authority semantics; stale runtime/config cannot restore revoked authority | `PRTV-001`, `002`, `003`, `004`, `013`, `014`, `016`, `017`, `035`, `037`, `038`, `041`, `042`, `043` | `OPEN-PRT-003..012`, `OPEN-PRT-023..026` as implementation bindings; exact selected subset recorded by implementation |
| `runtime.api@1` | `port.transactional@1`, `port.reliability-state@1`, `port.audit@1`, `port.observability@1`, bounded `port.ephemeral@1`; no migration owner | trusted TenantContext/current placement + current auth/config/workload credential/network policy | `rel.cell-transactional-store@1`, `rel.security-session-authority@1`, `rel.performance-cache@1`, `rel.configuration-authority@1` | `health.api-bff@1`, `health.cell@1`, `health.security-authority@1`; `obs.request.outcome@1`, `obs.configuration.generation@1`; `sli.api.outcome@1`, `sli.api.latency@1`, `sli.cell.admission@1` | drain/replace without process-local truth; stale generation/port binding cannot resume protected effects | `PRTV-002`, `003`, `004`, `005`, `008`, `009`, `010`, `013`, `014`, `016`, `027`, `028`, `030`, `031`, `035`, `037`, `038`, `039`, `041`, `042`, `043` | `OPEN-PRT-003..012`, `016`, `018`, `023..026`, `039` as applicable |
| `runtime.worker@1` | `port.job-event-transport@1`, `port.reliability-state@1` plus specialization ports | trusted tenant/placement/current authority per specialization; current workload credential/config/network policy; accepted durable work identity | exact specialization binding below; generic worker identity is insufficient | `health.async-worker@1`, `obs.async.progress@1` plus specialization evidence below | drain/lease/redelivery/reconciliation preserves durable responsibility; stale worker generations fenced | specialization vectors plus `PRTV-037`, `038`, `039`, `042`, `043`; `PRTV-041` whenever secret material exists | `OPEN-PRT-003..018`, `023..029`, `039` as applicable; implementation records exact subset per specialization |
| `runtime.realtime@1` | replay/current-auth/placement/fanout/observability capabilities; no general DB owner | current ticket/replay/session/auth/placement + runtime/config/workload credential/network policy | `rel.realtime-fanout@1`, `rel.security-session-authority@1`, `rel.replay-consume-state@1` where accepted | `health.realtime@1`, `health.security-authority@1`; `obs.realtime.lifecycle@1`, `obs.security.authority-freshness@1`; `sli.realtime.delivery@1` | drain/relocation/resync; consumed capability and stale socket cannot regain authority | `PRTV-002`, `003`, `004`, `005`, `008`, `012`, `013`, `014`, `031`, `033`, `035`, `037`, `038`, `039`, `041`, `042`, `043` | `OPEN-PRT-003..012`, `018`, `023..026`, `039` as applicable |
| `runtime.control-plane@1` | `port.control-placement@1`, configuration/identity authorities; no universal tenant operational DB | current global placement/config/security authority + runtime/workload credential/network policy | `rel.control-plane-placement@1`, `rel.placement-reference-cache@1`, `rel.configuration-authority@1`, `rel.secret-key-authority@1` only for dependencies actually used | `health.control-plane@1`, `health.security-authority@1`; `obs.operation.state@1`, `obs.configuration.generation@1`, `obs.security.authority-freshness@1`; `sli.control-plane.admission@1` | stale CP/runtime generation cannot resurrect placement; replacement/restore revalidates current global authority | `PRTV-005`, `006`, `007`, `008`, `009`, `013`, `014`, `015`, `016`, `029`, `030`, `032`, `033`, `035`, `036`, `037`, `038`, `039`, `041`, `042`, `043` | `OPEN-PRT-001..012`, `021`, `023..031`, `039` as applicable |
| `runtime.automation@1` | target-scoped credentials, `port.reliability-state@1`, approved connector/artifact/observability ports only | current operation authorization/tenant/target + workload credential/config/network policy | `rel.privileged-operations@1`, plus exact external/artifact profile only when accepted operation uses it | `health.async-worker@1`, `health.security-authority@1` and specialized health where applicable; `obs.operation.state@1`; `sli.async.progress@1` / specialized outcome | timeout/cancel/host death leaves discoverable outcome; ambiguous external effect reconciles; target credential cannot outlive accepted authority | `PRTV-003`, `013`, `014`, `015`, `016`, `018`, `021`, `030`, `031`, `035`, `037`, `038`, `039`, `040` when artifact output applies, `041`, `042`, `043` | `OPEN-PRT-003..015`, `017..019`, `023..026`, `038`, `039` as applicable |
| `runtime.untrusted-parser@1` | staged input/output only; no general DB/secret authority | operation/input identity + parser profile/config/resource limit currentness | direct durable reliability=`NO_APPLICABLE_CASE`: enclosing import/artifact/operation profile owns durable responsibility | direct service SLI=`NO_APPLICABLE_CASE`; enclosing `obs.operation.state@1` and durable-work health/SLI carry impact | parser crash/timeout is explicit outcome; ephemeral state never becomes acceptance/release authority | `PRTV-019`, `020`, `030`, `031`, `035`, `037`, `043`; forbidden secret access is tested by `PRTV-020` | `OPEN-PRT-003`, `004`, `014`, `026`, `038` |
| `runtime.migration-admin@1` | dedicated schema/data-admin mapping + `port.audit@1`; not serving traffic | current release/admin scope + schema/config/runtime/workload credential/network policy generations and destructive fences | `rel.privileged-operations@1`, plus owning transactional/configuration profiles for scope | `health.security-authority@1`, `health.async-worker@1` for durable work; `obs.operation.state@1`, `obs.security.authority-freshness@1`; `sli.async.progress@1` where durable | rollback/forward recovery cannot restore stale authority; serving app cannot inherit admin principal | `PRTV-003`, `013`, `014`, `015`, `016`, `022`, `023`, `024`, `030`, `031`, `034`, `035`, `037`, `038`, `039`, `041`, `042`, `043` | `OPEN-PRT-003`, `004`, `009`, `010`, `012`, `016`, `026`, `033`, `035`, `039` as applicable |
| `runtime.recovery@1` | current recovery/security/governance authorities, `port.reliability-state@1`, `port.audit@1`, affected ports by scope | recovery authorization + current placement/security/governance/secret-key/reliability fences; runtime/config/workload credential/network policy currentness | `rel.privileged-operations@1`, `rel.control-plane-placement@1`, `rel.replay-consume-state@1`, `rel.secret-key-authority@1`, plus affected profile | `health.recovery@1`, `health.security-authority@1`, affected health; `obs.recovery.reconciliation@1`, `obs.security.authority-freshness@1`, `obs.operation.state@1`; `sli.recovery.convergence@1` | `(R,F]` reconciliation and quarantine before protected resume; old snapshot cannot become current authority | `PRTV-005`, `008`, `009`, `015`, `016`, `025`, `026`, `027`, `029`, `031`, `033`, `035`, `037`, `038`, `039`, `041`, `042`, `043` | `OPEN-PRT-002..012`, `016..020`, `026..034`, `037`, `039` as applicable |
| `runtime.edge-optional@1` | optional filter/routing/acceleration only; no business state-port authority | current origin routing/network policy/workload credential where used; no tenant/domain authority from edge presence | direct business reliability=`NO_APPLICABLE_CASE`: origin BFF/API/realtime owns protected semantics | direct canonical service-health authority=`NO_APPLICABLE_CASE`; edge diagnostics may feed `obs.request.outcome@1`, impact stays in origin profiles | replacement/loss cannot change canonical semantics; no durable business/recovery truth at edge | `PRTV-001`, `002`, `004`, `030`, `035`, `036`, `037`, `043` | `OPEN-PRT-001..007`, `011..013`, `023..026`, `036`, `037` as applicable |

OPEN ranges above constrain implementation choices; a concrete implementation records the exact selected OPEN IDs and closure evidence. A range does not imply every choice is applicable to every deployment.

## Canonical worker specialization join

Every concrete `runtime.worker@1` declares one or more exact worker specialization IDs. Each selected specialization receives separate queue/transport ownership, ports, secret/egress permissions and concurrency/bulkhead accounting even when physically co-located.

| Worker specialization | Required ports | Egress / secret-reference classes | Accepted reliability bindings | Specialized Phase 12 evidence | Additional vectors / resource rule |
|---|---|---|---|---|---|
| `worker.outbox-publication@1` | `port.job-event-transport@1`, `port.reliability-state@1`, owning transactional outbox access | `egress.platform-bounded@1`; `secretref.state-port@1`, `secretref.service-communication@1` | `rel.outbox-publication@1`, `rel.broker-job-transport@1` | `health.async-worker@1`, `obs.async.progress@1`, `sli.async.progress@1` | `PRTV-011`, `027`, `030`, `031`, `039`, `042`, `043`; independent `resource.worker-specialized@1` budget |
| `worker.async-consumer@1` | `port.job-event-transport@1`, `port.reliability-state@1`, owning transactional port where effects commit | `egress.platform-bounded@1` unless accepted operation requires connector; `secretref.state-port@1`, `secretref.service-communication@1` | `rel.consumer-inbox-effect@1`, `rel.broker-job-transport@1` | `health.async-worker@1`; `health.message-equivalence@1` where duplicate-sensitive comparison applies | `PRTV-005`, `011`, `026`, `028`, `030`, `031`, `039`, `042`, `043`; independent worker budget |
| `worker.provider-integration@1` | `port.job-event-transport@1`, `port.reliability-state@1`, owning transactional port, observability | `egress.connector-bounded@1`; `secretref.connector@1`, `secretref.state-port@1`, `secretref.service-communication@1` | `rel.external-provider@1` plus exact durable transport/effect profile used | `health.provider-adapter@1`, `health.async-worker@1`, `sli.provider.outcome@1` | `PRTV-011`, `015`, `018`, `030`, `031`, `039`, `041`, `042`, `043`; destination/provider bulkhead |
| `worker.webhook-delivery@1` | `port.job-event-transport@1`, `port.reliability-state@1`, observability | `egress.connector-bounded@1`; connector/signing reference classes only as accepted webhook contract requires | `rel.webhook-delivery@1` | `health.webhook-delivery@1`; Phase 12 Product-gated SLI/alert unchanged | `PRTV-011`, `015`, `017`, `018`, `030`, `031`, `039`, `041`, `042`, `043`; destination/tenant bulkhead |
| `worker.reporting-export@1` | `port.job-event-transport@1`, `port.reliability-state@1`, owning transactional/report ports, `port.artifact@1`/staging when output protected | `egress.platform-bounded@1`; `secretref.state-port@1`, `secretref.service-communication@1` | `rel.reporting-derived@1`; `rel.artifact-storage@1` when protected artifact output exists | `health.async-worker@1`, `health.artifact@1` where applicable | `PRTV-011`, `015`, `030`, `031`, `039`, `040`, `041`, `042`, `043`; report/export bulkhead |
| `worker.customer-telemetry@1` | `port.job-event-transport@1`, `port.reliability-state@1`, `port.customer-telemetry@1` | `egress.platform-bounded@1`; `secretref.state-port@1`, `secretref.service-communication@1` | `rel.customer-telemetry-acceptance@1` | `health.customer-telemetry@1`, `sli.customer-telemetry.acceptance@1` | `PRTV-011`, `030`, `031`, `039`, `042`, `043`; telemetry-ingest bulkhead |
| `worker.artifact-lifecycle@1` | `port.job-event-transport@1`, `port.reliability-state@1`, `port.artifact@1`, `port.object-staging@1` where used | `egress.platform-bounded@1`; `secretref.state-port@1`, object/storage reference only through accepted port mapping | `rel.artifact-storage@1` | `health.artifact@1`; Product applicability unchanged for direct delivery SLI | `PRTV-011`, `015`, `025`, `030`, `031`, `039`, `040`, `041`, `042`, `043`; artifact bulkhead |
| `worker.reconciliation@1` | `port.reliability-state@1` plus exact affected ports; job transport when durable queued work | bounded platform/connector egress only if affected operation requires it; secret classes strictly derived from affected owner | exact affected reliability profile; `rel.privileged-operations@1` only when scope is privileged | `health.recovery@1` or `health.async-worker@1` as applicable; `sli.recovery.convergence@1` only when recovery-owned | `PRTV-008`, `025`, `026`, `029`, `030`, `031`, `038`, `039`, `042`, `043`; affected-scope bulkhead |

`PRTV-037` applies whenever multiple worker specializations are physically co-located. `PRTV-041` applies to any specialization that receives secret material, including future accepted extensions. Generic worker deployment state never resolves Product-gated Phase 12 applicability.

## Canonical isolation profiles

- `isolation.confidential-web@1` — browser-session confidentiality without domain DB ownership.
- `isolation.application-serving@1` — normal application least privilege and tenant-scoped state access.
- `isolation.workload-bulkhead@1` — workload-specific concurrency/network/secret/state isolation.
- `isolation.realtime@1` — long-lived connection capacity separated from normal API/worker capacity.
- `isolation.control-plane@1` — global placement/lifecycle authority separated from tenant operational state.
- `isolation.controlled-execution@1` — target-scoped automation with explicit resource/credential/egress envelope.
- `isolation.untrusted-content@1` — parser/transform sandbox with no implicit network/secret/data authority.
- `isolation.privileged-data-admin@1` — migration/query/admin privilege unavailable to serving principals.
- `isolation.recovery@1` — recovery/reconciliation authority with current-state fencing.
- `isolation.edge-untrusted-boundary@1` — external traffic boundary, never business authorization authority.

## Canonical egress profiles

```text
egress.none@1
egress.platform-bounded@1
egress.connector-bounded@1
egress.privileged-bounded@1
```

A runtime's egress profile is a maximum capability; application-level destination/authorization checks still apply.

## Canonical cell-generation lifecycle records

Per-generation cell/runtime admission lifecycle uses:

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

Replacement is a multi-generation operation, not a single-generation lifecycle value. Predecessor and successor retain distinct lifecycle/generation evidence.

Phase 12 health values remain separate. Implementations SHALL NOT collapse lifecycle and health into one boolean or one vendor readiness field.

## Canonical generation set

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

These do not replace upstream authorization/revocation, schema, artifact-delivery, replay, governance or cryptographic/verifier generations. A mapping preserves which authority owns each generation.

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

- every canonical runtime row SHALL instantiate every schema field through the identity/lifecycle table and authority/evidence table;
- every selected `runtime.worker@1` SHALL declare exact `worker_specialization_id` values and inherit runtime-level plus specialization-level bindings;
- every specialization declares its ports, egress/secret classes, reliability, Phase 12 evidence, resource/bulkhead rule and vectors;
- a conditional specialized binding names the accepted owner that activates it; implementation presence is insufficient;
- `NO_APPLICABLE_CASE` requires reason and enclosing impact/evidence path;
- implementation OPEN bindings are recorded exactly when an implementation is selected; this baseline may declare bounded candidate OPEN ranges without choosing them;
- adding/changing an accepted Phase 11/12 profile relevant to a runtime is a Phase 13 compatibility input; join becomes incomplete until reviewed;
- vendor/orchestrator readiness/health fields are adapters, never replacements for Phase 12 profile meaning;
- `PRTV-037..043` are cross-cutting enforcement vectors and cannot be omitted where applicable.

## Co-location decision record

Any implementation co-locating profiles records evidence for:

```text
profiles/specializations co-located
combined effective principal
secret/state-port access union
network/egress union
resource/bulkhead enforcement
lifecycle/drain compatibility
failure blast radius
reason co-location does not weaken each profile
```

Absent this evidence, more privileged/risky profiles remain separated.

## Product applicability

Runtime implementation SHALL NOT resolve `OPEN-OBS-037` or other Product-scope OPEN decisions by deploying/not deploying a component. A prepared runtime profile may exist without proving Product enablement.

## Manifest blockers

Acceptance is blocked when:

- a runtime schema field is missing, implicit or delegated to an unnamed vendor/default rather than an exact binding/rule/OPEN/N/A disposition;
- a runtime or worker-specialization row lacks explicit upstream/evidence/fault-vector bindings;
- vendor resource names replace canonical runtime/port/profile identities;
- co-location creates a privilege/egress/state union broader than accepted profiles;
- network presence is treated as trust;
- lifecycle is collapsed into process liveness/readiness;
- quarantine can bypass revalidation;
- replacement conflates predecessor and successor runtime generations;
- one generation identity is used as universal currentness authority;
- state-port physical co-location merges logical authority/failure/recovery semantics;
- object presence/capability becomes artifact release authority;
- secret material may leak through ordinary runtime state/signals;
- a privileged/parser/automation profile inherits ordinary application or unrestricted infrastructure authority by convenience;
- physical topology enters canonical tenant/API/event/resource identity;
- Product scope/applicability is inferred from runtime deployment state.