# Wave 2 — Known Deferred Items

Recorded 2026-08-27, found incidentally during the adversarial audit of PR #25 (Wave 3) and
formalized here at the explicit request of the repository owner: these are consciously deferred
scope, not silent omissions. Nothing in this file changes accepted Wave 2 behavior; it is a
record-only addition.

## 1. `system.async_consumer_inbox` atomicity is proven only in-process

`sql/wave2/001_async_correctness.sql:308` defines a real `PRIMARY KEY` on the canonical inbox
identity `(consumer_contract, message_identity_scope, message_id)`, which is the correct schema-level
mechanism for atomic create-or-observe against a real database. However,
`src/jlmirror_async/inbox.py` (lines 87-137, especially line 96) proves atomic create-or-observe
only via an in-process `threading.RLock`, explicitly labeled as a reference model
(`inbox.py:69-81`). Atomicity against a real multi-connection PostgreSQL deployment — concurrent
processes/workers racing on the same primary key — is not demonstrated in this codebase.

**Status:** deferred, intentionally scoped. `tools/async_core/validate_wave2.py:74-103` records
`"product_feature_activation": "none"` for this exact reason — this is reference/conformance code,
not a production consumer runtime.

**Closure requires:** a real database-backed implementation (once a persistence/pooling backend is
selected — see `residual_c2_choices_not_selected` in `IMPLEMENTATION_MANIFEST.json`) that proves
the primary-key-based atomic insert behaves correctly under real concurrent connections, with a
test that actually exercises concurrent DB sessions rather than in-process threads sharing one lock.

## 2. Outbox + domain-mutation atomicity is documentation-only

The rule that outbox publication evidence must be written in the *same transaction* as the
authoritative domain mutation is stated in three places
(`docs/10-event-contracts/publication-outbox-and-producer-authority.md:10`;
`sql/wave2/001_async_correctness.sql:6-8`; `src/jlmirror_async/outbox.py:106-109`), but no
domain/use-case layer exists yet in this repository that actually performs a domain mutation
alongside an outbox write — so there is currently no call site where this rule could be violated
*or* fulfilled in practice.

**Status:** deferred by construction. This is not a gap in Wave 2 so much as a property that has no
concrete instance to test yet; it becomes testable only once a domain/use-case layer exists (e.g.
the Wave 4+ Monitoring vertical slice referenced in the platform roadmap).

**Closure requires:** when the first real domain mutation + outbox call site is implemented (Wave
4 or later), add an integration test proving the transaction boundary is actually shared — not
merely documented.
