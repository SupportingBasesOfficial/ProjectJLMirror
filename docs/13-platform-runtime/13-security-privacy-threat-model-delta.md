# Phase 13 — Security, Privacy and Threat-Model Delta

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document records the Phase 13 threat-model delta introduced by concrete runtime, identity, network, isolation, state-port and cell-lifecycle capabilities. It does not replace the accepted Security Requirements or system threat model.

## Trust boundaries added/refined

Phase 13 makes explicit:

- public/edge -> BFF/API/realtime ingress;
- serving runtime -> workload-identity authority;
- serving runtime -> secret/key authority;
- runtime -> transactional/reliability/audit/customer-telemetry/observability/artifact/ephemeral ports;
- runtime -> external provider/destination egress;
- Control Plane -> cell placement/admission distribution;
- source cell -> target cell during replacement/relocation;
- normal serving runtime -> automation/parser/admin/recovery runtime;
- privileged orchestrator -> child execution identity;
- physical co-location -> logical runtime/worker/port authority boundaries;
- runtime lifecycle/currentness -> Phase 12 health/diagnostic representation.

## Threats and required controls

### PRT-TM-001 — Network-presence confused deputy
A reachable internal workload attempts protected operations without required machine/application authority.  
Controls: authenticated workload principal, capability-scoped authorization, independent tenant/current-authority evaluation, explicit network policy. Vectors: `PRTV-002`, `PRTV-003`.

### PRT-TM-002 — Service-principal overreach
A valid service principal is reused across tenants/domains/workload classes more broadly than intended.  
Controls: least-privilege principal classes, runtime/worker binding, tenant/domain checks, independent revocation and audit. Vectors: `PRTV-003`, `PRTV-013`, `PRTV-014`.

### PRT-TM-003 — Physical-placement injection
Caller/message/provider/config attempts to select cell/database/schema/cluster/secret target.  
Controls: trusted Control Plane placement resolution, destination-cell admission/version check, caller physical metadata rejected as authority. Vectors: `PRTV-004`, `PRTV-005`.

### PRT-TM-004 — Stale runtime/currentness resurrection
Old/restored runtime or one green generation regains authority after relocation, revocation, erasure or policy change while another owning generation is stale.  
Controls: canonical distinct `runtime_generation`, `configuration_generation`, `workload_credential_generation`, `placement_version`, `network_policy_generation`; upstream generations retain owners; stale-admission rejection; recovery quarantine. Vectors: `PRTV-009`, `PRTV-016`, `PRTV-025`, `PRTV-042`.

### PRT-TM-005 — Secret authority aggregation
One broad runtime principal can read connector, database, signing, admin and recovery secrets.  
Controls: canonical secret-reference classes, workload-scoped policy, dedicated privileged principals, no universal serving secret principal. Vectors: `PRTV-015`, `PRTV-037`.

### PRT-TM-006 — Secret disclosure through runtime state
Secret values leak into environment/config snapshots, logs, events/jobs, diagnostics, crash dumps, artifacts or ordinary audit snapshots.  
Controls: references not values, Phase 12 classification/redaction, bounded diagnostics, leakage tests. Vector: `PRTV-041`.

### PRT-TM-007 — Egress/SSRF escape
Connector/parser/automation input causes access to unintended protocol/address/destination/redirect target.  
Controls: bounded egress profiles, resolution/connect/redirect revalidation, protocol/address restrictions, parser deny-by-default egress, response/time/concurrency bounds. Vectors: `PRTV-018`, `PRTV-019`, `PRTV-021`.

### PRT-TM-008 — Parser/execution sandbox escape
Untrusted content or automation obtains host/platform/state/secret capability beyond its profile.  
Controls: smaller execution trust envelope, deny-by-default privileges/network, bounded resources, isolated workspace, no inherited admin credential. Vectors: `PRTV-019`, `PRTV-020`, `PRTV-021`.

### PRT-TM-009 — Privileged runtime reuse
Migration/admin/recovery credentials are reused for ordinary serving or handed unrestricted to child execution.  
Controls: dedicated principal/lifecycle/ingress profiles, scoped child identity, audited operation, explicit target/environment authority. Vectors: `PRTV-023`, `PRTV-024`, `PRTV-037`.

### PRT-TM-010 — State-port semantic substitution
A convenient cache/broker/object/storage behavior is treated as stronger correctness authority than accepted contracts allow.  
Controls: typed ports, explicit authority class, semantic compatibility, vendor adapter boundaries. Vectors: `PRTV-027`, `PRTV-028`.

### PRT-TM-011 — State-port authority collapse
One physical backend or broad credential implements several ports and merges audit, business, reliability, customer-telemetry or observability authority.  
Controls: logical port ownership remains enforceable, least-privilege credentials and independent failure/recovery semantics. Vector: `PRTV-039`.

### PRT-TM-012 — Cell admission/replacement race
Source/target or old/new cell generations both accept protected work during relocation/replacement.  
Controls: placement/admission generation, predecessor/successor distinction, destination validation, stale source fencing, orchestrator-owned transition. Vectors: `PRTV-005`, `PRTV-033`, `PRTV-038`.

### PRT-TM-013 — Recovery authority rollback
Restored infrastructure reintroduces revoked credentials/permissions/placement, old verifier/key paths, erased-data authority or stale legal-hold state.  
Controls: `(R,F]` reconciliation, current Security/Governance authorities, recovery quarantine, generation/fence validation, separate recovery principal. Vectors: `PRTV-025`, `PRTV-026`, `PRTV-038`, `PRTV-042`.

### PRT-TM-014 — Runtime health authority laundering
Orchestrator/vendor green status is treated as proof of authorization, placement, recovery completion or safe release.  
Controls: Phase 12 semantic mapping, lifecycle/health separation, application admission checks, tool status as evidence only. Vectors: `PRTV-008`, `PRTV-035`, `PRTV-038`.

### PRT-TM-015 — Resource exhaustion/noisy neighbor
Tenant/provider/destination/parser/query/recovery/worker specialization exhausts global compute, connections, state-port or egress capacity.  
Controls: multidimensional admission/concurrency budgets, worker specialization bulkheads, tenant/destination isolation, saturation signals, bounded retry/backlog. Vectors: `PRTV-030`, `PRTV-034`, `PRTV-037`.

### PRT-TM-016 — Leader split brain
Old and new coordinator both act after lease/failover ambiguity.  
Controls: fenced epoch/lease semantics, stale-leader rejection, durable outcome/reconciliation, no process-memory truth. Vector: `PRTV-029`.

### PRT-TM-017 — Topology/privacy leakage
Public APIs/logs/diagnostics expose physical cell/cluster/database/node/provider topology or privileged secret references.  
Controls: logical canonical IDs, protected diagnostics, Phase 12 classification/cardinality controls, minimum public health disclosure.

### PRT-TM-018 — Product-scope laundering through deployment
Presence/absence of runtime component or feature flag is interpreted as Product enablement/non-applicability.  
Controls: upstream Product authority remains owner; `OPEN-OBS-037` preserved. Vector: `PRTV-017`.

### PRT-TM-019 — Artifact release bypass
Object existence, upload success or direct storage capability is treated as authorization to release protected bytes.  
Controls: `port.artifact@1` lifecycle metadata, current delivery generation/lease/governance authority, restricted storage credentials. Vector: `PRTV-040`.

### PRT-TM-020 — Co-location privilege union
Runtime profiles or worker specializations are physically combined and silently inherit the union of principals, secrets, state ports, egress or resource/failure authority.  
Controls: explicit co-location decision record, effective-policy diff, separate budgets/credentials where required. Vector: `PRTV-037`.

### PRT-TM-021 — Manifest omission / vendor-default authority
Implementation omits a required principal/lifecycle/ingress/egress/secret/port/currentness/resource/reliability/observability/recovery/vector/OPEN binding and relies on a vendor default.  
Controls: complete runtime semantic manifest, explicit binding/OPEN/N/A disposition, machine conformance. Vector: `PRTV-043`.

### PRT-TM-022 — Portability security regression
Vendor replacement preserves nominal API but weakens identity, isolation, network, durability, fence, manifest or recovery guarantees.  
Controls: semantic manifest mapping, compatibility classification, portability rehearsal and negative tests. Vectors: `PRTV-027`, `PRTV-035`, `PRTV-036`, `PRTV-043`.

## Tenant-isolation implications

- workload/service principals do not replace tenant context;
- state-port credentials enforce least privilege and data-layer tenant controls where applicable;
- cell/dedicated-cell placement changes isolation/capacity, not tenant identity or Product semantics;
- cross-cell direct operational mutation is not enabled by connectivity;
- administrative cross-tenant capability remains explicit privileged authority;
- co-location never widens tenant scope implicitly.

## Privacy/data-minimization implications

Runtime metadata SHALL minimize physical topology, secret/key references beyond operational need, tenant/resource IDs in high-cardinality telemetry, parser/automation inputs/outputs, provider destination/config details, and recovery/erasure/legal-hold internals.

Diagnostic usefulness does not authorize broad retention/searchability. Phase 12 retention/classification and Security governance remain authoritative.

## Cryptographic and secret continuity

Phase 13 supplies runtime access/rotation/revocation capabilities but does not select cryptographic algorithms or KMS vendor.

Runtime recovery/rollback SHALL NOT recreate a retired key path when current governance requires erasure, nor retire historical verification authority still needed for accepted evidence without an equality/verification-preserving migration.

## Accountability

Privileged runtime lifecycle, migration/admin, secret/key administration, recovery/fence advancement and cross-tenant platform operations require protected audit/accountability evidence. Ordinary runtime logs do not substitute for audit, even if physically stored in the same backend.

## Security compatibility blockers

A Phase 13 change is security-sensitive when it broadens effective principal, secret references, egress destinations, state ports, tenant scope, physical placement control, parser/automation capability, recovery authority, artifact release capability, co-location union, generation substitution, manifest implicitness, or weakens stale-generation/fence behavior.

## Evidence requirements

Future conformance/runtime evidence includes privilege-denial tests, credential rotation/revocation, stale-generation rejection, parser/automation isolation, SSRF/egress tests, cross-cell placement races, recovery rollback, secret-leak scans, noisy-neighbor tests, split-brain fencing, state-port authority separation, artifact release denial, co-location union tests, manifest completeness and portability security comparison.