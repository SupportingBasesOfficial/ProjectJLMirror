# Wave 1 — Known Deferred Items

Recorded 2026-08-27, found incidentally during the adversarial audit of PR #25 (Wave 3) and
formalized here at the explicit request of the repository owner: these are consciously deferred
scope, not silent omissions. Nothing in this file changes accepted Wave 1 behavior; it is a
record-only addition.

## 1. "Protected realtime" WebSocket capability-admission mechanism

`docs/07-system-design/request-auth-and-authorization-lifecycle.md` (around lines 63-87) describes
a capability-based admission model for realtime/WebSocket connections — "a capability proves that
authority existed when it was minted; it does not freeze that authority until expiry" — but no
corresponding implementation exists in `src/jlmirror_authority` today. A search for
`realtime|websocket|gateway|capability` in that package finds no matching code path; the one hit
is an unrelated docstring in `session.py`.

**Status:** deferred. Wave 1 established the identity/authority skeleton (BFF, control plane,
application-serving principals); realtime/WebSocket admission was never in its authorized scope
(`impl.identity-bff@1`, `impl.control-plane@1`, `impl.platform-runtime@1` — see
`IMPLEMENTATION_MANIFEST.json`).

**Closure requires:** a dedicated implementation wave that authorizes realtime/WebSocket admission
as in-scope, followed by a corrective/additive PR against that scope specifically — not a retrofit
onto Wave 1's accepted files.

## 2. `MachineReplayAuthority.claim_once` has no persisted atomic implementation

`src/jlmirror_authority/machine.py` defines `MachineReplayAuthority` (the machine-assertion replay
authority governing `jti`/IR-D-001 single-winner claims) as a `typing.Protocol` — an interface
only. There is no equivalent in this package to
`platform.advance_authority_fence` (`sql/wave1/001_platform_authority_fence.sql:238-277`), which
*does* implement real compare-and-swap fencing at the database level. The reference-model code and
its test suite exercise `MachineReplayAuthority` only through in-memory fakes.

**Status:** deferred, not a confirmed gap — this was flagged during the audit as an open question,
not verified against a live production call path (none exists yet). It is plausible the intended
persisted implementation lives in a C2 backend choice not yet selected
(`residual_c2_choices_not_selected` in `IMPLEMENTATION_MANIFEST.json` already lists several
undecided backends).

**Closure requires:** either (a) a concrete SQL-backed `MachineReplayAuthority` implementation
mirroring the `advance_authority_fence` pattern once a persistence backend is selected, or (b) an
explicit confirmation that machine-assertion replay authority is intentionally deferred to a later
wave, with the current `Protocol`-only shape formally accepted as an interface contract rather than
a shipped implementation.
