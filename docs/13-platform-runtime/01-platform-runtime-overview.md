# Phase 13 — Platform & Runtime Overview

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

Phase 13 defines the portable logical runtime capabilities required to execute the accepted JLMIRROR contracts and satisfy accepted Phase 11 reliability and Phase 12 observability semantics without turning a cloud, orchestrator, service mesh, secret manager, broker or other infrastructure product into architecture by default.

Phase 13 refines runtime responsibility, isolation, lifecycle, identity, communication, state ports, capacity, environment classes and relocation. It does not redefine Product scope, tenant identity, authorization, transaction ownership, failure semantics, observability semantics or release/incident authority.

## Accepted authority inherited

Phase 13 inherits, without weakening:

- the accepted modular-monolith + independent-worker architecture;
- Control Plane + cell-based data plane;
- logical tenant identity independent of physical placement;
- trusted placement and destination-cell admission;
- `network presence != trust`;
- BFF/browser confidentiality and independently secured API boundaries;
- current authorization and placement re-establishment where required;
- Phase 10 durable-message/idempotency/recovery semantics;
- Phase 11 failure, degradation, ambiguity, reconciliation and recovery-continuity profiles;
- Phase 12 health, signal, SLI, alert, classification and Product-applicability semantics;
- secret references rather than production secret values in source/ordinary configuration;
- least-privilege separation between normal application runtime and migration/administrative authorities;
- the `(R,F]` recovery-continuity model and `uncertainty != absence`.

## Phase 13 laws

```text
RUNTIME LOCATION != AUTHORITY
NETWORK REACHABILITY != TRUST
PROCESS LIVENESS != WORKLOAD READINESS
SERVICE IDENTITY != TENANT AUTHORIZATION
RUNTIME INSTANCE ID != BUSINESS IDENTITY
PHYSICAL TOPOLOGY != CANONICAL API/EVENT/RESOURCE IDENTITY
ENVIRONMENT LABEL != AUTHORIZATION OR TENANT AUTHORITY
SECRET REFERENCE != SECRET VALUE
CONFIGURATION AVAILABILITY != CONFIGURATION CURRENTNESS
RESTART != RECOVERY COMPLETION
REPLICA COUNT != CAPACITY MODEL
ORCHESTRATOR STATE != BUSINESS/SECURITY/RECOVERY TRUTH
```

## Logical runtime classes

Phase 13 defines these stable logical classes; one implementation may combine compatible classes physically only when their trust, lifecycle and resource envelopes remain enforceable:

- `runtime.web-bff@1` — confidential first-party web session/composition boundary;
- `runtime.api@1` — general-purpose synchronous application/domain runtime;
- `runtime.worker@1` — durable asynchronous workload runtime, specialized by workload profile;
- `runtime.realtime@1` — protected realtime admission/delivery/resync runtime;
- `runtime.control-plane@1` — tenant/cell placement and global platform-management runtime;
- `runtime.automation@1` — controlled automation execution runtime;
- `runtime.untrusted-parser@1` — isolated parsing/transformation boundary for untrusted or active content;
- `runtime.migration-admin@1` — privileged schema/data-administration runtime;
- `runtime.recovery@1` — privileged recovery/reconciliation runtime;
- `runtime.edge-optional@1` — optional edge/CDN/WAF/composition capability that cannot become required for core domain execution.

Runtime class is a security/reliability profile, not automatically a separately deployed service.

## Control Plane and cells

The Control Plane remains small and authoritative for placement/lifecycle intent. Cells remain the default tenant execution, failure-containment and horizontal-scale unit.

A cell runtime SHALL be capable of provisioning from accepted configuration/identity inputs; validating dependencies/runtime conformance before admission; admitting only tenants/placement generations recognized by the cell; serving accepted workload classes with explicit health/readiness profiles; draining new admission while durable work reaches safe boundaries; replacement without changing logical tenant/resource identities; relocation under accepted placement/fencing/reconciliation authority; and remaining quarantined when recovery/current authority cannot be proven.

Cell lifecycle and cell health are separate dimensions. `active` lifecycle does not imply every workload is healthy; a `draining` health/admission posture does not erase durable obligations.

## State and authority separation

Runtime processes own execution responsibility, not authoritative durability by memory. Durable/authoritative state is reached through typed ports defined by Phase 13, including transactional, control-plane placement, reliability-state, audit, customer-telemetry, artifact, ephemeral/cache, broker/job and secret/key authorities.

A process restart, reschedule or replica replacement SHALL NOT convert missing local state into absence of prior effects, consumed capabilities, revocations, recovery obligations or governance decisions.

## Identity and communication

Every protected machine-to-machine call has an authenticated workload/service principal; explicit allowed capability/service scope; independently reconstructed tenant/current authority where required; bounded destination/network policy; and observable provenance without secret disclosure.

Workload identity authenticates the caller runtime. It never grants tenant/domain authority solely because two workloads share a network, cell, cluster, namespace or host.

## Configuration, credentials and authority generations

Ordinary runtime configuration carries secret references and non-secret semantic configuration. Secret/key material is obtained only by a workload identity whose profile permits the reference.

Phase 13 canonical runtime generations are:

```text
runtime_generation
configuration_generation
workload_credential_generation
placement_version
network_policy_generation
```

Secret/key/version generations owned by upstream cryptographic, provider, replay, artifact or governance contracts remain under those owners and are referenced rather than renamed by Phase 13.

These generations are diagnostic/fencing inputs only within their owning authorities. One generation cannot silently substitute for another.

## Logical environment classes

Phase 13 fixes four portable logical environment classes.

### `environment.development@1`

Used for local/shared development, integration and experimentation. It SHALL NOT receive authoritative production tenant traffic, production placement authority or production workload credentials by default. Synthetic/non-production data is the default. Any exceptional production-derived dataset requires explicit governed export/minimization authority and remains non-authoritative.

### `environment.validation@1`

Used for pre-production conformance, security, performance, fault, compatibility and release-candidate validation. Runtime semantics SHOULD be production-equivalent where fidelity is required, but the environment has no production serving authority by label. Production-derived data/credentials are not copied in by convenience; governed test data or narrowly authorized evidence paths are required.

### `environment.production@1`

Used for authoritative customer-serving workloads and current production Control Plane/cell/data authorities. Full accepted security, tenant, recovery, observability and governance contracts apply. Production authority comes from current principals/placement/configuration/governance, not from the string `production` alone.

### `environment.recovery@1`

Used for isolated restore, reconciliation, forensic/recovery validation and resumption preparation under `runtime.recovery@1`. It may access production recovery material only through explicit recovery authority. It is not a normal serving environment and cannot become production merely because recovered state is reachable; handoff/resumption requires current production placement/security/governance/recovery predicates.

### Environment invariants

- environment class is orthogonal to tenant/resource/API/event identity;
- no canonical business/resource ID embeds an environment-specific physical account/cluster/region identifier;
- credentials, secret references, state ports and network policies remain environment-scoped and least-privilege;
- non-production environment class does not authorize production secrets/data/traffic;
- production data copied to lower classes requires explicit governance, minimization and isolation evidence;
- moving an artifact/configuration/runtime mapping between environment classes is a Phase 14 promotion/deployment concern and never changes Product truth by itself;
- physical cloud account/project/subscription, cluster, namespace, region and promotion-pipeline mapping remain implementation/Phase 14 decisions.

## Portability

Phase 13 contracts use logical runtime classes, environment classes, capabilities, ports, lifecycle states and evidence. Vendor-specific objects map to these contracts; they do not redefine them.

Replacing cloud/orchestrator/runtime/network/secret-manager/storage products MUST NOT require changing canonical tenant IDs, API/event semantics, Phase 11 failure classes, Phase 12 health/SLI meanings or logical environment-class semantics.

## Boundary with later phases

Phase 13 does not define source-to-artifact build/promotion authority, rollout/canary/rollback policy, infrastructure-as-code tooling, SBOM/signing/provenance mechanisms or human incident command/runbooks/on-call process.

Those belong to Phase 14/15. Phase 13 supplies the runtime and logical environment contracts those phases must deploy and operate.

## Acceptance orientation

Phase 13 can reach `READY_FOR_MERGE` only when runtime roles, isolation, lifecycle, identity, network, state ports, privileged execution, capacity/relocation, logical environment classes, compatibility, security, recovery, validation, OPEN decisions and traceability form one enforceable system and no vendor/default silently becomes normative.