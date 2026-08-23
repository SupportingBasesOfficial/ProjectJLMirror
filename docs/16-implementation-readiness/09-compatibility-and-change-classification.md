# Implementation Readiness — Compatibility & Change Classification

**Status:** proposed gate baseline

## Classes

### IR-COMP-A — non-semantic implementation detail
Formatting, internal refactor or replaceable mechanism change that preserves every accepted contract/profile/authority/evidence field.

### IR-COMP-B — C2 mechanism substitution
Cloud/runtime/broker/cache/observability/release/ops product or mechanism replacement that passes the same exact conformance profile and does not alter authority/failure/recovery semantics.

### IR-COMP-C — semantic implementation breaking
Any change that alters API/event meaning, tenant/current authority, identity, idempotency, failure class, health/SLI meaning, generation/fencing, release-target/config semantics, recovery admission, runbook authority or evidence interpretation.

### IR-COMP-D — Security/Recovery critical
Any change that broadens trust, makes stale/unknown state permissive, weakens revocation/erasure/legal hold/audit/crypto/replay continuity, permits cross-tenant authority, changes identity/fence currentness, or turns ambiguity into effect eligibility.

### IR-COMP-E — Product scope change
Any implementation that exposes/activates a Product-gated/deferred endpoint, webhook, public projection, SDK, privileged query, active-inline artifact, diagnostic export or capability without accepted Product/domain authority.

## C1 decision compatibility

Changes to IR-D-001/002/003 are not ordinary implementation details.

Security-sensitive changes include:

- OIDC flow or browser credential boundary;
- MFA/step-up/re-authentication assurance semantics for privileged human operations;
- machine client authentication profile, including unique-`jti` replay identity, atomic cross-replica single-winner replay admission, fail-closed unavailability and replay-state recovery continuity;
- workload identity syntax/trust domain/certificate currentness;
- service authentication/authorization separation;
- fence epoch ordering, allocation or stale-effect rejection.

A replay-store/vendor substitution is IR-COMP-B only when it proves the same IR-D-001 replay authority semantics. A change from shared single-winner/fail-closed/recovery-continuous replay protection to replica-local, check-then-insert, fail-open or missing-state-means-unused behavior is IR-COMP-D even if token schema and client protocol are unchanged.

Such changes require an explicit governance amendment and migration/compatibility evidence.

## Mixed-version rule

Old/new implementations may coexist only when the accepted API/event/runtime/release/recovery compatibility matrices admit the combination. For machine authentication, mixed token-boundary versions SHALL NOT create two replay domains or disagree on replay-generation/current-key interpretation. A deployment tool's ability to run both versions is not compatibility evidence.

## OPEN transitions

- C1 closure is a governance change and must update the consolidated register and owning closure record.
- C2 selection records chosen/rejected materially different mechanism options and conformance evidence.
- C3 numeric closure requires production-eligibility evidence and does not retroactively redefine normative semantics.
- C4/C5 activation requires Product/architecture authority before implementation.

## Rollback

Code/config rollback cannot restore retired identity, machine-assertion replay eligibility, fence, release policy, authorization, Product applicability or recovery authority. Where current state is not safely interpretable by the old implementation, forward recovery is required.
