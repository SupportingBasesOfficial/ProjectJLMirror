# OPEN-API-002 Decision Record — HMAC Double-Submit CSRF Mechanism

**Status:** proposed — mechanism selected; one binding closure condition (key rotation) below is required before this record satisfies the anti-CSRF-mechanism half of `OPEN-API-002`
**Decision class:** C2 (`docs/16-implementation-readiness/03-consolidated-open-decision-register.md:30` — "cookie/CSRF/origin implementation profile under fixed Phase 09 browser security semantics")
**Drivers:** `docs/09-api-contracts/phase-09-open-decisions.md:25-34` (`OPEN-API-002`), `adr/ADR-005-identity-and-authorization.md`, `adr/ADR-015-secrets-and-keys.md`, `docs/09-api-contracts/browser-bff-and-realtime-admission.md`, `docs/09-api-contracts/http-message-framing-and-canonicalization.md`, `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md` (IR-D-001)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: it fixes the "exact anti-CSRF token/header mechanism" `OPEN-API-002` explicitly leaves open, inside the already-accepted requirement that state-changing cookie-authenticated browser requests have "explicit CSRF protection" and that SameSite alone is insufficient (`docs/09-api-contracts/browser-bff-and-realtime-admission.md:83-91`). It was produced from an adversarial multi-round red/blue-team review; the review found the HMAC double-submit direction sound but left exactly the parameters `OPEN-API-002` calls out as unresolved unspecified. One finding is confirmed as a binding gap; three others are real but narrower than first claimed once already-accepted text is checked, and are recorded as hygiene/clarity additions rather than structural holes.

## Context and problem

`OPEN-API-002` (`docs/09-api-contracts/phase-09-open-decisions.md:25-34`) already fixes that CSRF protection is explicit and that SameSite alone is insufficient; it leaves the concrete mechanism open. This record selects an HMAC-based double-submit cookie pattern: a server-issued HMAC-signed token echoed by the client in a request header, validated against the session.

## Requirements and invariants this selection must satisfy

- `docs/09-api-contracts/browser-bff-and-realtime-admission.md:57`: security-relevant session/CSRF cookie parsing must have one canonical meaning across every hop (edge, gateway, BFF).
- `docs/09-api-contracts/browser-bff-and-realtime-admission.md:91`: a duplicate/conflicting anti-CSRF header/cookie presentation cannot be first-value-selected by one hop and last-value-selected by another.
- `docs/09-api-contracts/http-message-framing-and-canonicalization.md:8-14`: one canonical wire interpretation at every protected consumer; ambiguity fails closed.
- `adr/ADR-005-identity-and-authorization.md:47`: credential revocation behavior survives multiple API replicas.
- `docs/16-implementation-readiness/04-must-close-identity-and-fencing-profiles.md:31`: session identifiers rotate at privilege/authentication boundary changes where fixation resistance requires it — not on routine background renewal.

## Decision

An HMAC double-submit cookie pattern is selected: `token = key_version || HMAC(key[key_version], session_lineage_id)`, cookie non-`HttpOnly` (required for JS to echo it into a request header), header validated against the session on every state-changing request. Selection is conditioned on the closure requirement below; three further items are recorded as required hygiene additions.

### Closure condition — versioned-key rotation (binding, high severity)

Every BFF replica across every cell/region validating a session's CSRF token must share the same signing key material. Neither ADR-005, `browser-bff-and-realtime-admission.md`, nor `phase-09-open-decisions.md` commits to a key-versioning/rotation/distribution mechanism for this specific token, and ADR-015 (secrets/key management) governs envelope-encrypting persisted secrets at rest, not sizing a cross-replica validation-key overlap window against session TTL. Rotating without an overlap window mass-invalidates every open session's CSRF token simultaneously (a synchronized self-DoS); never rotating leaves a leaked historical key valid indefinitely.

**Requirement:** keys are versioned (`key_version || HMAC(key[key_version], ...)`), sourced from the same secret-management/KMS capability ADR-015 already mandates for other secret material — this is an application of ADR-015's existing versioned-key/rotation idiom, not a new mechanism. Exactly 2 active versions (current + previous) at all times; rotation cadence bounded so overlap ≥ max session/token lifetime; validation tries only currently-active versions (no brute-forcing across key history); alarm if previous-key usage is still nonzero once the overlap window closes.

The HMAC input is a renewal-stable **session-lineage identifier**, not the literal (rotating) session ID — per IR-D-001, session-ID rotation is tied to rare, per-user privilege/authentication boundary events (login, step-up/MFA), not routine background renewal, so this does not produce the platform-wide synchronized-failure pattern an earlier draft of this finding claimed. It remains correct practice: the CSRF cookie SHALL be reissued synchronously in the same response whenever IR-D-001's fixation-resistance rotation actually fires, scoped to that narrow, infrequent event.

### Required hygiene additions (not structural gaps; already covered by existing fail-closed doctrine or accepted exceptions)

1. **Cardinality/parsing fail-closed rule, made concrete.** `browser-bff-and-realtime-admission.md:57` already mandates fail-closed as the default for duplicate/conflicting cookie or header presentation — this forecloses a silent-forgery reading. What remains is availability hygiene: the BFF SHALL reject (not first/last-select) any request presenting more than one CSRF cookie value or more than one CSRF header value for the canonical name, at the same ingress-canonicalization layer that already performs `http-message-framing-and-canonicalization.md`'s work (before session/tenant logic runs), not independently re-implemented per hop. Edge/gateway and BFF SHALL run the identical header/cookie-parsing library or an explicitly certified equivalent, verified by a contract test feeding identical wire bytes through both. Add the duplicate-cookie and duplicate-header cases to the required ingress test list at `browser-bff-and-realtime-admission.md:272-284`.
2. **Non-`HttpOnly` cookie is a documented, bounded exception, not an ADR-005 lapse.** ADR-005's browser-exposed-secret concern targets bearer/refresh credentials that alone grant API authority; a CSRF nonce grants none in isolation and is a standard, accepted double-submit exception (matching OWASP guidance). This is documented as an intentional, bounded exception rather than reopening ADR-005, with a compensating control: Content-Security-Policy restricting which script origins may execute on tenant-scoped BFF pages, as general hygiene against third-party/supply-chain script risk.

## Consequences

### Positive
- correctly beats naive double-submit and SameSite-only reliance;
- versioned-key rotation closes the one gap that would otherwise cause either a platform-wide self-DoS or an unbounded forgery window;
- session-lineage binding means routine session renewal never desynchronizes the client's cached CSRF value from the server's expected value.

### Negative / cost
- key versioning/rotation is new operational surface requiring its own conformance tests;
- edge/gateway and BFF parser-parity certification is an added cross-team contract test.

## Validation

Before production eligibility, conformance evidence SHALL prove:
- a key rotation with the required overlap window does not invalidate any in-flight session's CSRF token;
- previous-key usage reaching zero before overlap-window close, and an alarm firing if it does not;
- duplicate CSRF cookie/header presentation is rejected identically at edge and BFF;
- session renewal (non-fixation-resistance-triggered) does not change the CSRF cookie's validity;
- IR-D-001's fixation-resistance rotation synchronously reissues the CSRF cookie in the same response.

## Exit / revisit conditions

Revisit if a future client architecture change alters the BFF/browser session-transport model this mechanism depends on.
