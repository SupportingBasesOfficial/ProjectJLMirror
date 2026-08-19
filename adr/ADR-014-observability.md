# ADR-014 — Observability Architecture

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** reversible at backend/vendor layer

## Context

JLMIRROR spans BFF, API, database, workers, queues, providers and realtime. Failures must be diagnosable end-to-end without leaking tenant secrets. High-cardinality telemetry can itself become an outage/cost vector.

Drivers: `FR-OPS-001..003`, `INV-OBS-001`, `SEC-AUD-002`, `QA-OBS-001`, `QA-SEC-001`.

## Decision

JLMIRROR SHALL adopt **OpenTelemetry-compatible context/semantic propagation** as the vendor-neutral standard for distributed traces and correlated telemetry.

Every important request/job/event/integration path SHALL propagate stable identifiers as applicable:

- trace/span context;
- request/operation ID;
- correlation ID;
- causation/event/job ID;
- logical tenant ID using controlled cardinality;
- principal/resource identifiers only where privacy/cardinality policy permits.

Structured logs, metrics, traces, errors and health are separate signals. Audit is a separate accountability system and SHALL NOT be treated as ordinary application logging.

Telemetry pipelines SHALL redact secrets/PII at source and sink, cap high-cardinality labels, expose queue/provider/database saturation and define sampling/retention policies by signal class.

The observability backend/vendor is not selected by this ADR.

## Consequences

### Positive
- trace continuity across future service extraction;
- vendor portability;
- better failure diagnosis and SLO measurement.

### Negative / cost
- instrumentation discipline and semantic conventions are required;
- telemetry volume/cost needs budgets.

## Validation

A synthetic end-to-end request -> job -> provider -> event -> notification flow must be reconstructable without secrets. Automated leakage/cardinality tests and broken-trace detection are required.

## Exit / revisit conditions

Backend products and sampling strategy may change. Correlation/semantic requirements remain architectural.