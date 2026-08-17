# ADR-016 — Deployment and Runtime Architecture Beyond Edge Limits

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly but portable by design

## Context

The platform needs long-lived provider connections, WebSockets, durable workers, database transactions, controlled script execution and background migrations. Some edge/serverless runtimes impose execution time, socket, filesystem, process or network limitations incompatible with these responsibilities. The web layer still benefits from CDN/edge delivery.

Drivers: `FR-AUTO-003`, `FR-OPS-*`, `QA-AVAIL-001`, `SEC-EXEC-*`, `AP-06`, `AP-15`.

## Decision

Separate deployment roles:

- **edge/web delivery:** CDN/WAF/static assets/routing and optional web/BFF functions where runtime capability fits;
- **core API:** general-purpose long-running compute packaged as OCI-compatible containers or equivalent portable process runtime;
- **worker pools:** general-purpose container/process runtime, scaled independently by workload class;
- **realtime gateway:** runtime supporting long-lived WebSocket connections and horizontal fanout;
- **automation executor:** stronger isolated compute boundary with explicit resource/network/credential controls;
- **migration/administrative jobs:** controlled one-shot runtime using distinct privileges.

Core business execution SHALL NOT require an edge runtime. Container/orchestrator/cloud vendor remains unselected until platform ADRs evaluate managed container/serverless-container/Kubernetes trade-offs.

Data-plane cells SHOULD be deployable independently. Runtime services are stateless where possible and use graceful shutdown/readiness for rolling changes.

## Consequences

### Positive
- implementation is not trapped by edge constraints;
- API/workers/WebSocket/executors can have fit-for-purpose resource/security profiles;
- OCI/process portability reduces provider lock-in.

### Negative / cost
- multiple runtime classes require deployment/observability standards;
- general-purpose compute has more operational responsibility than pure edge functions.

## Validation

Graceful shutdown, connection draining, worker lease recovery, WebSocket reconnect, rolling deployment and one-cell replacement tests. Automation executor cannot access platform secrets/network beyond policy.

## Exit / revisit conditions

Specific hosting/orchestration vendor is intentionally open. A fully serverless implementation is acceptable only if it demonstrably satisfies these runtime semantics.
