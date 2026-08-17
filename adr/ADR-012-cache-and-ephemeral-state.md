# ADR-012 — Cache and Ephemeral-State Semantics

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible if semantics remain stable

## Context

Caching is required for latency, provider protection, placement lookups and high-read data, but `INV-DATA-004` forbids durable truth from depending solely on ephemeral state. Security-sensitive state has different outage behavior from performance cache.

Drivers: `INV-DATA-004`, `SEC-TEN-003`, `QA-PERF-001`, `TM-004`.

## Decision

Caches SHALL be classified by semantics rather than by one global strategy:

1. **performance cache** — cache-aside/derived data; may fail open by bypassing cache and reading authoritative source;
2. **placement/reference cache** — versioned last-known-good copy of control-plane data; stale use is bounded and cells validate admission/version where needed;
3. **security acceleration cache** — may accelerate permission/session/revocation checks but SHALL have a durable authority or explicit fail-closed policy;
4. **ephemeral fanout/circuit/rate state** — loss may degrade protection/experience but SHALL NOT change durable business truth.

All tenant-protected keys/topics SHALL use canonical collision-resistant tenant namespacing. Cache values SHALL be schema/version aware when shape evolution matters.

A specific cache technology is not selected by this ADR.

## Consequences

### Positive
- dependency outage behavior is explicit per data class;
- security correctness is not traded for performance;
- cache vendor remains replaceable.

### Negative / cost
- multiple cache policies/TTLs/invalidation strategies must be documented;
- permission/placement invalidation requires careful versioning.

## Validation

Test cache loss, stale placement, stale permission, cross-tenant key collision and thundering-herd scenarios. Performance cache outage must not become data corruption; security cache outage must not silently grant access.

## Exit / revisit conditions

Technology selection is a later ADR based on latency, durability, topology and operational requirements.
