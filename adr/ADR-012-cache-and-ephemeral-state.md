# ADR-012 — Cache and Ephemeral-State Semantics

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** reversible if semantics remain stable

## Context

Caching is required for latency, provider protection, placement lookups and high-read data, but `INV-DATA-004` forbids durable truth from depending solely on ephemeral state. Security-sensitive state has different outage behavior from performance cache. Some coordination-looking records are correctness/security state during a bounded validity window: losing them can reauthorize replay or duplicate protected effects even though they are not long-term business data.

Drivers: `INV-DATA-004`, `SEC-TEN-003`, `QA-PERF-001`, `TM-004`.

## Decision

Caches/state SHALL be classified by semantics rather than by one global strategy:

1. **performance cache** — cache-aside/derived data; may fail open by bypassing cache and reading authoritative source;
2. **placement/reference cache** — versioned last-known-good copy of control-plane data; stale use is bounded and cells validate admission/version where needed;
3. **security acceleration cache** — may accelerate permission/session/revocation checks but SHALL have a durable/current authority or explicit fail-closed policy;
4. **ordinary ephemeral fanout/circuit/rate state** — loss may degrade protection/experience but SHALL NOT change durable business truth or convert a prior denial/consume into new eligibility;
5. **bounded correctness/security coordination state** — records such as single-use capability replay consumption that may be short-lived but whose loss changes authorization/correctness. These require an accepted continuity mechanism rather than best-effort cache semantics.

For single-use/bounded-use realtime capabilities, the shared replay authority SHALL provide atomic single-winner consumption and continuity over the accepted capability validity/retry-safety window. A previously consumed capability cannot become redeemable after authority restart/loss/restore. The design SHALL either retain/reconcile registered capability/consumption state or use a trusted replay epoch/generation advanced after state loss to invalidate outstanding capabilities. Missing replay state is rejection/invalidity, never proof of unused state.

All tenant-protected keys/topics SHALL use canonical collision-resistant tenant namespacing. Cache values SHALL be schema/version aware when shape evolution matters.

A specific cache/replay-state technology is not selected by this ADR.

## Consequences

### Positive
- dependency outage behavior is explicit per data class;
- security correctness is not traded for performance;
- short-lived correctness state is not accidentally treated as disposable merely because its TTL is small;
- cache vendor remains replaceable.

### Negative / cost
- multiple cache policies/TTLs/invalidation strategies must be documented;
- permission/placement invalidation requires careful versioning;
- replay-authority continuity/epoch handling adds coordination and may invalidate outstanding capabilities after loss.

## Validation

Test cache loss, stale placement, stale permission, cross-tenant key collision and thundering-herd scenarios. Performance cache outage must not become data corruption; security cache outage must not silently grant access.

Replay-authority tests consume a still-valid capability, restart/lose/restore the authority, and prove the capability remains rejected. A missing record after state loss MUST NOT be interpreted as unused; either consumed state is recovered/reconciled or a new trusted epoch invalidates the old capability before protected admission resumes.

## Exit / revisit conditions

Technology selection is a later ADR based on latency, durability, topology and operational requirements. The semantic distinction between disposable cache state and bounded correctness/security state remains mandatory.