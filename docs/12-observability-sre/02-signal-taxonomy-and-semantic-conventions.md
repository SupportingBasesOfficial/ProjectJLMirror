# Phase 12 — Signal Taxonomy and Semantic Conventions

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This document defines stable vendor-neutral meanings for JLMIRROR operational signals. Backend field names and wire encodings may vary only through an implementation mapping that preserves these semantics.

## Signal families

### Structured log

A discrete diagnostic record describing an observed condition or transition. Logs are not append-only business history by default and SHALL NOT substitute for required audit evidence.

### Metric

A numeric time series with a stable name, unit, aggregation meaning and bounded dimension set. Metric labels are not a general metadata bag.

### Trace

A causally connected set of spans describing execution across accepted boundaries. Trace continuity is diagnostic evidence; a trace gap does not prove an operation or external effect did not occur.

### Operational event

A structured platform-operational state transition intended for diagnosis/automation of observability, not a domain event merely renamed for logging. Operational events cannot become a second business event bus.

### Health state

A bounded state/profile describing current eligibility/progress characteristics of a runtime/capability. Health is derived evidence, not authorization or recovery authority.

### Audit evidence

A separately governed accountability record correlated with observability where safe. Audit identity, durability, immutability and retention remain owned by accepted audit authority.

## Common semantic envelope

Where applicable, a signal profile declares:

```text
signal_name
signal_profile_version
signal_family
observed_at
emitted_at
severity_or_state
capability_id
operation_class
runtime_role
logical_environment_class
trace_id / span_id
request_id
correlation_id
operation_id
causation_id
message_id / delivery_id / replay_id
recovery_operation_id / recovery_generation_or_fence_reference
tenant_context_representation
classification
cardinality_profile
schema/profile version
```

A field is emitted only when semantically applicable and permitted by classification/cardinality policy. Empty or fabricated identifiers SHALL NOT be inserted merely to satisfy a common shape.

## Naming

Stable signal names SHALL:

- identify a logical capability/operation rather than a host/pod/node name;
- describe the measured state/outcome, not a backend query implementation;
- avoid provider-native names as the canonical platform contract where an adapter semantic exists;
- have one accepted meaning per profile version;
- avoid encoding tenant, resource, principal or other unbounded identifiers into the signal name.

Physical runtime identity may exist as a bounded diagnostic attribute where Phase 13 later defines it; it is not canonical resource identity.

## Units and aggregation

Every numeric metric declares:

- unit;
- monotonic/counter, gauge, histogram/distribution or other semantic class;
- reset/generation behavior where relevant;
- valid aggregation across instances/tenants/cells;
- whether zero means observed zero, no work, or another explicit condition;
- how missing samples differ from zero.

A latency metric SHALL define the measured boundary. A queue metric SHALL distinguish queued item count from age/lag. A success ratio SHALL define numerator and denominator rather than infer success from absence of errors.

## Time semantics

`observed_at` is when the source says the condition occurred. `emitted_at` is when the signal was created. Collector/storage receipt time MAY be retained separately.

Clock skew, buffering and late arrival SHALL NOT silently reorder authoritative business/recovery state. Observability may record skew/late arrival but cannot use wall-clock order to override accepted sequence/generation/fence authority.

## Outcome taxonomy

Signals describing operation outcome use stable classes rather than arbitrary exception text. At minimum, mappings distinguish where applicable:

```text
success
denied
invalid
not_found_or_concealed
throttled
unavailable
timed_out
cancelled
ambiguous_external_outcome
reconciliation_required
quarantined
recovery_blocked
compromised_or_untrusted
internal_failure
```

These are observability outcome dimensions and do not replace Phase 11 failure-class authority.

## Error representation

Errors SHALL use bounded stable error codes/classes. Stack traces, provider messages and exception text are diagnostic payloads subject to classification/redaction and SHALL NOT become metric labels.

A provider-native error code MAY be recorded in a bounded/redacted adapter diagnostic field when useful, but canonical alert/SLI logic consumes normalized platform classes.

## Tenant context

Tenant context in telemetry is derived only from trusted platform context after the relevant boundary establishes it. Caller/provider text SHALL NOT select another tenant's observability scope.

Tenant IDs MAY be used only according to the accepted cardinality/privacy profile. Cross-tenant aggregate metrics SHOULD prefer bounded aggregation that does not expose individual tenant identity when the use case does not require it.

## Semantic convention versioning

Every stable signal contract belongs to a semantic profile/version. A material meaning change requires compatibility review even when the field name and type remain unchanged.

Producers and consumers SHALL support an accepted mixed-version window where rolling deployment requires it. A dashboard/query/alert relying on one meaning cannot silently consume another meaning under the same identity.

## Prohibited semantics

The following are prohibited:

- `error_count == 0` being interpreted as proof of success when telemetry may be missing;
- trace absence being interpreted as effect absence;
- log presence being treated as authoritative audit completion;
- a `healthy=true` bit masking readiness/degradation/recovery-quarantine dimensions;
- raw exception/provider text as an unbounded metric label;
- raw URL/query/cursor/capability material in ordinary telemetry;
- secrets/credentials in any ordinary signal;
- arbitrary user/provider labels being promoted to canonical dimensions without validation/bounds.

## Validation obligations

Tests SHALL prove stable units, missing-vs-zero behavior, late/skewed time handling, semantic-version compatibility and rejection/redaction of prohibited high-cardinality or protected fields.
