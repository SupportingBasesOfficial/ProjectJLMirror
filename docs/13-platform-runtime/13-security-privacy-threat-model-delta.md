# Phase 13 — Security, Privacy and Threat-Model Delta

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document records the Phase 13 threat-model delta introduced by concrete runtime, identity, network, isolation, state-port and cell-lifecycle capabilities. It does not replace the accepted Security Requirements or system threat model.

## Trust boundaries added/refined

Phase 13 makes explicit the following runtime trust boundaries:

- public/edge -> BFF/API/realtime ingress;
- serving runtime -> workload-identity authority;
- serving runtime -> secret/key authority;
- runtime -> transactional/reliability/audit/telemetry/artifact/ephemeral ports;
- runtime -> external provider/destination egress;
- Control Plane -> cell placement/admission distribution;
- source cell -> target cell during replacement/relocation;
- normal serving runtime -> automation/parser/admin/recovery runtime;
- privileged orchestrator -> child execution identity;
- runtime lifecycle state -> Phase 12 health/diagnostic representation.

## Threats and required controls

### PRT-TM-001 — Network-presence confused deputy

A reachable internal workload attempts protected operations without the required machine/application authority.

Controls: authenticated workload principal, capability-scoped service authorization, independent tenant/current-authority evaluation, explicit egress/ingress policies.

### PRT-TM-002 — Service-principal overreach

A valid service principal is reused across tenants/domains/workload classes more broadly than intended.

Controls: least-privilege principal scopes, runtime-profile binding, tenant/domain checks, independent revocation and audit.

### PRT-TM-003 — Physical-placement injection

Caller/message/provider/config attempts to select cell/database/schema/cluster/secret target.

Controls: trusted Control Plane placement resolution, destination-cell admission/version check, caller physical metadata rejected as authority.

### PRT-TM-004 — Stale runtime resurrection

Old/restored runtime/config/network/credential generation regains authority after relocation, revocation, erasure or policy change.

Controls: distinct currentness generations, stale-admission rejection, forward reconciliation, recovery quarantine, no reachability-as-currentness assumption.

### PRT-TM-005 — Secret authority aggregation

One broad runtime principal can read connector, database, signing, admin and recovery secrets.

Controls: secret-reference classes, workload-scoped policy, dedicated privileged principals, rotation/revocation tests, no universal serving secret principal.

### PRT-TM-006 — Secret disclosure through runtime state

Secret values leak into environment/config snapshots, logs, events/jobs, diagnostics, crash dumps or artifacts.

Controls: references not values in ordinary config/state, Phase 12 redaction/classification, bounded diagnostic export, runtime hardening and leakage tests.

### PRT-TM-007 — Egress/SSRF escape

Connector/parser/automation input causes access to unintended protocol/address/destination or redirect target.

Controls: bounded destination policy, resolution/connect/redirect revalidation, protocol/address restrictions, parser deny-by-default egress, response/time/concurrency bounds.

### PRT-TM-008 — Parser/execution sandbox escape

Untrusted content or automation obtains host/platform/state/secret capability beyond its profile.

Controls: smaller execution trust envelope, deny-by-default privileges/network, bounded resources, isolated workspace, no inherited admin credential, conformance/escape testing.

### PRT-TM-009 — Privileged runtime reuse

Migration/admin/recovery credentials are reused for ordinary serving or handed unrestricted to child execution.

Controls: dedicated runtime/principal, no normal ingress, scoped child identity, audited operation, explicit target/environment authority.

### PRT-TM-010 — State-port semantic substitution

A convenient cache/broker/object/storage behavior is treated as stronger business/security/recovery authority than accepted contracts allow.

Controls: typed ports, explicit authority class, compatibility tests for durability/fencing/ambiguity/recovery, vendor adapter boundaries.

### PRT-TM-011 — Cell admission race

Source/target or old/new cell generations both accept tenant protected work during relocation/replacement.

Controls: monotonic placement/admission generation, destination validation, stale source fencing, orchestrator-owned transition, async/realtime re-resolution.

### PRT-TM-012 — Recovery authority rollback

Restored infrastructure reintroduces revoked credentials, permissions, placement, old verifier/key paths, erased data authority or stale legal-hold state.

Controls: `(R,F]` reconciliation, current Security/Governance authorities, recovery quarantine, generation/fence validation, separate recovery principal.

### PRT-TM-013 — Runtime health authority laundering

Orchestrator/vendor health/readiness green status is treated as proof of tenant authorization, placement, recovery completion or safe release.

Controls: Phase 12 semantic mapping, lifecycle/health separation, application admission checks, telemetry/tool status as evidence only.

### PRT-TM-014 — Resource exhaustion/noisy neighbor

Tenant/provider/destination/parser/query/recovery workload exhausts global compute, connections, state-port or egress capacity.

Controls: multidimensional admission/concurrency budgets, workload bulkheads, tenant/destination isolation, saturation signals, bounded retry/backlog.

### PRT-TM-015 — Leader split brain

Old and new coordinator both act after lease/failover ambiguity.

Controls: fenced epoch/lease semantics, stale-leader rejection, durable outcome/reconciliation, no immortal singleton/process-memory truth.

### PRT-TM-016 — Topology/privacy leakage

Public APIs, logs or diagnostics expose physical cell/cluster/database/node/provider topology or privileged secret references.

Controls: logical canonical IDs, protected/internal diagnostics, Phase 12 classification/cardinality controls, minimum public health disclosure.

### PRT-TM-017 — Product-scope laundering through deployment

Presence/absence of a runtime component or feature flag is interpreted as Product enablement/non-applicability.

Controls: upstream Product authority remains owner; `OPEN-OBS-037` discipline preserved; runtime/config evidence cannot close Product applicability by itself.

### PRT-TM-018 — Portability security regression

Vendor replacement preserves nominal API but weakens identity, isolation, network, durability, fence or recovery guarantees.

Controls: semantic manifest mapping, compatibility classification, portability rehearsal and negative security/fault tests.

## Tenant-isolation implications

- workload/service principals do not replace tenant context;
- state-port credentials enforce least privilege and data-layer tenant controls where applicable;
- cell/dedicated-cell placement changes isolation/capacity, not tenant identity or Product semantics;
- cross-cell direct operational mutation is not enabled by connectivity;
- administrative cross-tenant capability remains explicit privileged authority.

## Privacy/data-minimization implications

Runtime metadata SHALL minimize exposure of:

- physical topology;
- secret/key references beyond operational need;
- tenant/resource IDs in high-cardinality public telemetry;
- parser/automation inputs/outputs;
- provider destination/configuration details;
- recovery/erasure/legal-hold internals.

Diagnostic usefulness does not authorize broad retention/searchability. Phase 12 retention/classification and Security governance remain authoritative.

## Cryptographic and secret continuity

Phase 13 supplies runtime access/rotation/revocation capabilities but does not select cryptographic algorithms or KMS vendor.

Runtime recovery/rollback SHALL NOT recreate a retired key path when current governance requires erasure, nor retire historical verification authority still needed for accepted evidence without an equality/verification-preserving migration.

## Accountability

Privileged runtime lifecycle, migration/admin, secret/key administration, recovery/fence advancement and cross-tenant platform operations require protected audit/accountability evidence under accepted Security rules. Ordinary runtime logs do not substitute for audit.

## Security compatibility blockers

A Phase 13 change is security-sensitive when it broadens effective principal, secret references, egress destinations, state ports, tenant scope, physical placement control, parser/automation capability, recovery authority or weakens stale-generation/fence behavior.

## Evidence requirements

Future conformance/runtime evidence includes privilege-denial tests, credential rotation/revocation, stale-generation rejection, parser/automation isolation, SSRF/egress tests, cross-cell placement races, recovery rollback tests, secret-leak scans, noisy-neighbor tests, split-brain fencing and portability security comparison.