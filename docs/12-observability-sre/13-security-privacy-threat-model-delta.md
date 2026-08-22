# Phase 12 — Security and Privacy Threat-Model Delta

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

Phase 12 introduces a high-propagation diagnostic plane, new correlation surfaces, health/alert semantics and future privileged observability queries. This document captures the resulting threat-model delta without selecting a vendor/runtime.

## Assets

Protected assets include:

- tenant/principal/resource relationship metadata;
- request/operation/message/delivery/replay/recovery identifiers;
- provider/integration diagnostic metadata;
- runtime/topology diagnostic metadata;
- error/stack diagnostic payloads;
- health/recovery/security state;
- SLI/SLO/error-budget and alert state;
- telemetry configuration/sampling/redaction rules;
- observability query/export capability;
- evidence provenance/profile identity.

Secrets remain prohibited ordinary telemetry and are not an observability asset class to retain.

## Threat actors/conditions

- malicious tenant/user controlling request values and high-cardinality inputs;
- compromised provider/integration returning hostile error/metadata;
- compromised application/runtime emitting fabricated telemetry;
- compromised collector/exporter/backend;
- overprivileged operator/support user;
- accidental developer instrumentation leakage;
- noisy tenant/workload causing cost/availability exhaustion;
- stale restored observability state;
- malicious/misconfigured sampling/redaction/dashboard/alert rules.

## Threats and required controls

### TM-OBS-001 — Secret exfiltration through telemetry

**Attack:** errors/headers/bodies/config values copied into logs/traces.  
**Control:** source minimization, explicit allowed fields, sink defense-in-depth, automated leakage tests; secret values prohibited.

### TM-OBS-002 — Cross-tenant correlation oracle

**Attack:** known request/trace/resource ID used to discover another tenant's telemetry.  
**Control:** current query authorization, tenant scope independent of identifier, distinct privileged cross-tenant operation.

### TM-OBS-003 — Correlation confused deputy

**Attack:** attacker supplies trace/correlation value that downstream treats as tenant/routing/dedup authority.  
**Control:** correlation remains diagnostic only; tenant/authority derived independently.

### TM-OBS-004 — Cardinality/cost DoS

**Attack:** attacker varies labels/error text/URLs to create unbounded time series/index fields.  
**Control:** bounded label allowlists, normalized routes/errors, dimension budgets, admission/drop/isolation.

### TM-OBS-005 — Telemetry backpressure outage

**Attack/failure:** collector/backend outage blocks app threads or creates infinite retries/buffers.  
**Control:** bounded asynchronous buffers/degradation, isolation, explicit drop/spill policy; mandatory audit/customer telemetry semantics preserved separately.

### TM-OBS-006 — Sampling evasion

**Attack:** traffic metadata influences sampling to hide malicious/failing operations.  
**Control:** untrusted input cannot choose weaker profile; required evidence classes protected from unsafe sampling.

### TM-OBS-007 — Sampling amplification

**Attack:** attacker selects metadata forcing expensive traces/logs.  
**Control:** bounded diagnostic escalation and tenant/workload budgets.

### TM-OBS-008 — Health spoofing

**Attack/failure:** liveness or reachability reported as readiness/trust/recovery eligibility.  
**Control:** multidimensional health; owning authority still decides admission/resumption.

### TM-OBS-009 — Alert suppression abuse

**Attack:** broad mute hides security/recovery/customer impact.  
**Control:** bounded scope/expiry, underlying evidence preserved, mandatory classes protected, suppression changes auditable where required.

### TM-OBS-010 — Alert flooding

**Attack/failure:** one tenant/provider produces notification storm.  
**Control:** bounded dedup/fanout, tenant/provider/workload isolation, distinct incident grouping.

### TM-OBS-011 — Diagnostic payload injection

**Attack:** provider/user text injects control sequences, fake log fields, HTML/terminal/query syntax.  
**Control:** structured serialization, escaping, bounded text, no dynamic schema/label names from untrusted input.

### TM-OBS-012 — Backend admin becomes product authority

**Attack:** observability administrator uses backend access as unrestricted tenant data access.  
**Control:** least privilege, query authorization, privileged cross-tenant capability explicit and audited.

### TM-OBS-013 — Restore resurrects erased diagnostic data

**Attack/failure:** observability restore re-exposes data after current erasure/governance decision.  
**Control:** accepted governance/recovery reconciliation applies where protected data is retained; telemetry does not become exempt recovery island.

### TM-OBS-014 — Stale telemetry drives unsafe recovery

**Attack/failure:** old “healthy/complete” signal after restore used to resume/retry effect.  
**Control:** telemetry never recovery authority; current generation/fence/continuity evidence required separately.

### TM-OBS-015 — SLI/SLO manipulation

**Attack/misconfiguration:** denominator/exclusions/sampling changed to improve reported reliability.  
**Control:** versioned SLI semantics, evidence-backed exclusions, missing!=success, compatibility/governance review.

### TM-OBS-016 — Profile/config drift

**Attack/failure:** redaction/sampling/semantic config weakens without source change.  
**Control:** profile/config identity in evidence, reviewed config lifecycle, prior clean evidence not reused silently.

### TM-OBS-017 — Health endpoint disclosure

**Attack:** public probe reveals tenant/topology/provider/recovery/security detail.  
**Control:** minimal public profile; privileged diagnostics separated.

### TM-OBS-018 — Trace baggage exfiltration

**Attack:** secret/protected data inserted in tracing baggage and propagated externally.  
**Control:** baggage deny-by-default allowlist, size/classification/hop policy.

### TM-OBS-019 — Telemetry egress confused deputy

**Attack:** future exporter/backend endpoint is attacker-controlled or overly broad.  
**Control:** Phase 13 network/egress/identity policy; observability destination cannot be selected by tenant/provider input.

### TM-OBS-020 — Evidence tampering/absence laundering

**Attack:** compromised pipeline drops/fabricates evidence and consumers treat silence as green.  
**Control:** pipeline-integrity/self-observation, missing=`unknown`, independent authoritative audit/recovery state.

## Trust boundaries

Conceptual boundaries:

```text
untrusted request/provider input
        -> application semantic source
        -> telemetry SDK/emission boundary
        -> collector/transport boundary
        -> processing/redaction/sampling boundary
        -> storage/query/alert boundary
        -> operator/automation consumer
```

No later boundary can safely recover a secret that should never have been emitted.

## Privacy principles

- minimize before emission;
- collect purpose-bound fields;
- use controlled tenant context;
- avoid raw protected payloads;
- bound retention/searchability/export;
- prevent unnecessary cross-tenant correlation;
- apply erasure/governance continuity where retained telemetry contains governed protected data.

## Release blockers

Future implementation/release is blocked by demonstrable secret leakage, cross-tenant query disclosure, uncontrolled cardinality, unsafe baggage/URL capture, telemetry backpressure amplification, missing evidence counted as success, or health semantics that can bypass security/recovery authority.
