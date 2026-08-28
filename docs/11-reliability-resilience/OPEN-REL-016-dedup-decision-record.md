# OPEN-REL-016 / OPEN-EVT-011 Decision Record — HMAC-Keyed Message-Equivalence Backend, PostgreSQL-Local

**Status:** proposed — mechanism selected; three binding closure conditions below required before `OPEN-REL-016.A`/`OPEN-EVT-011`'s mechanism portion may be treated as closed
**Decision class:** C2 (`docs/16-implementation-readiness/03-consolidated-open-decision-register.md:85` — `OPEN-REL-016` mechanism; `docs/10-event-contracts/phase-10-open-decisions.md:140` — `OPEN-EVT-011` comparison representation)
**Drivers:** `docs/00-foundation/architecture-principles.md` (AP-01), `docs/05-security/threat-model.md` (TM-004, TM-012), `docs/11-reliability-resilience/07-capability-resilience-profiles.md`, `docs/11-reliability-resilience/14-message-equivalence-reliability-continuity.md`, `docs/08-data/tenant-relocation.md`, `docs/08-data/recovery-retention-and-artifacts.md`, `docs/05-security/security-requirements.md` (SEC-GOV-004), `docs/15-operations-recovery-incident-readiness/08-cryptographic-authority-and-secret-recovery.md`

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: `14-message-equivalence-reliability-continuity.md` already anticipates a keyed-MAC comparison authority as one accepted evidence form; this record selects the concrete mechanism (HMAC, PostgreSQL-local store) inside that already-accepted frame. It was produced from an adversarial multi-round red/blue-team review. Three findings are confirmed as binding closure conditions (one critical); one candidate finding (co-locating the dedup store with the cell's transactional store) was investigated and **refuted** — the co-residency the finding attacked is in fact the platform's own accepted, stated design, and the finding's proposed fix would itself have broken atomic effect+dedup commit.

## Context and problem

`14-message-equivalence-reliability-continuity.md:44` lists "an authenticated/keyed comparison value such as a MAC" as one of several accepted comparison-evidence forms without mandating any particular key-scoping. This record selects HMAC as that keyed form and PostgreSQL, co-resident with the owning cell's transactional store, as the storage location — matching `rel.cell-transactional-store@1`'s own definition (`07-capability-resilience-profiles.md:17`): "authoritative transactional store plus co-resident idempotency/inbox/outbox/effect ledgers."

## Requirements and invariants this selection must satisfy

- AP-01 (`docs/00-foundation/architecture-principles.md:3-5`): tenant isolation is enforced in **multiple layers** — a passing functional correlation test alone does not prove this.
- The confidentiality/anti-oracle invariant (`14-message-equivalence-reliability-continuity.md:106-121`, `FV-ASYNC-003` branch 8): equal content in different scopes must not be correlatable.
- `rel.secret-key-authority`'s declared scope is explicitly cell-namespaced (`07-capability-resilience-profiles.md:22`), with no default cross-cell access.
- SEC-GOV-004: recovery SHALL NOT restore/recreate an older usable cryptographic key path when governed intent is approved erasure of the corresponding ciphertext.
- `docs/08-data/recovery-retention-and-artifacts.md:199-201`: data-rights (DSAR-style) erasure is a named, accepted, inherently sub-tenant scenario.

## Decision

HMAC-keyed message-equivalence evidence, stored PostgreSQL-local and co-resident with the owning cell's transactional store, is selected as the mechanism for `OPEN-REL-016`/`OPEN-EVT-011`. Selection is conditioned on the three closure requirements below.

### Closure condition 1 — cryptographic domain separation per (tenant, scope) (binding, critical severity)

The comparison identity `(consumer_contract, message_identity_scope, message_id)` (`14-message-equivalence-reliability-continuity.md:37`) places tenant separation inside an application-supplied scope value, not a cryptographically distinct key. `OPEN-REL-016` (concrete KMS/verifier mechanism) is explicitly still open, so nothing forecloses a shared cell/platform-wide HMAC key with tenant folded only into the MAC input — the simpler, more likely-as-built path. `FV-ASYNC-003` branch 8 is a mandatory, tested acceptance branch, but a passing functional test cannot distinguish a single-layer (query-predicate-only) implementation from a genuinely multi-layered one — both pass the same test, and AP-01 requires enforcement "in multiple layers," not one. A single missed filter in an internal support tool, analytics export, or incident-response dump — at thousands-of-tenants scale — becomes a live cross-tenant confidential-content equality oracle across the entire shared store.

**Requirement:** the comparison MAC key SHALL be cryptographically domain-separated per `(tenant, message_identity_scope)` — HKDF-derived as a per-scope subkey from a platform master key, never one shared secret with scope folded only into the MAC input — so a query-layer bug, compromised internal tool, or malicious tenant cannot produce a valid cross-scope equality signal even when the scope predicate is wrong or bypassed.

### Closure condition 2 — cross-cell historical-verifier transfer at relocation (binding, high severity)

`docs/08-data/tenant-relocation.md`'s migration manifest previously listed fingerprint data as a migration item but never the historical key/verifier-generation reference needed to interpret it, while `rel.secret-key-authority` is cell-namespaced with no cross-cell default access. A relocation following the prior checklist literally would leave the target cell holding fingerprints it structurally cannot verify, silently degrading every duplicate-sensitive message from the cutover window to `reconciliation_blocked` — a real, recurring, previously unbudgeted operational cost at a platform doing routine rebalancing/residency/DR relocations across thousands of tenants, even though the resulting failure mode itself is safe (fail-closed, not incorrect).

**Requirement:** already applied as a companion edit — `docs/08-data/tenant-relocation.md` now lists "historical HMAC key/verifier-generation reference and cross-cell verification authority" as a first-class migration-manifest item (preconditions, QUIESCING async-ownership, and VERIFYING sections), modeled on the already-accepted "historical verification" concept in `08-cryptographic-authority-and-secret-recovery.md:28-32` (a verifier may be "narrowly available to prove historical equality... That does not make it current authority for unrelated work"). The target cell holds, or has narrowly-scoped read access to, the source cell's historical verifier generation for the in-flight dedup horizon before cutover completes.

### Closure condition 3 — key granularity relative to erasure granularity (binding, medium severity)

SEC-GOV-004 ties approved cryptographic erasure to "the corresponding retained ciphertext"; `recovery-retention-and-artifacts.md:199-201` confirms data-rights erasure is a named, accepted, sub-tenant-granularity scenario — resolving in the direction that strengthens this finding (the original red-team finding flagged this as an open question; independent verification confirms sub-tenant erasure is real). If dedup keys are provisioned coarser than erasure granularity (e.g., one key per tenant), a single data-subject's erasure event destroying that key would collaterally invalidate dedup continuity for every other, unrelated in-flight message under the same tenant.

**Requirement:** dedup-equivalence keys SHALL be derived at a granularity no coarser than the smallest unit of erasure this platform supports (per-record/session HKDF subkeys, consistent with Closure condition 1's domain separation). If a coarser (whole-tenant) key is chosen instead, that choice must be recorded explicitly alongside a cited governing decision that data-rights erasure at this platform is implemented without destroying the tenant-wide dedup key.

### Investigated and refuted — not a closure condition

**"Co-locating the dedup store with the cell's transactional store collapses two declared blast radii."** Refuted: `rel.cell-transactional-store@1`'s own `truth_authority` field (`07-capability-resilience-profiles.md:17`) states co-residency of inbox/dedup/outbox ledgers with the core transactional store as its **stated definition**, corroborated at `07-capability-resilience-profiles.md:458`, `02-capability-dependency-criticality.md:39`, and `09-api-contracts/idempotency-concurrency-and-mutations.md:178`. This is the standard transactional-inbox pattern: the effect and its dedup marker must commit atomically in the same database, or the platform reintroduces the exact duplicate-execution race AP-07 (retry requires idempotency) exists to close. The proposed alternative (a physically separate PostgreSQL instance per cell for dedup) would itself break that atomicity and is explicitly rejected. Hot-tenant contention on the shared cell primary is an already-acknowledged general property of cell-level multi-tenancy, correctly owned by `OPEN-REL-022`'s numeric capacity/bulkhead-sizing work, not a topology change.

## Consequences

### Positive
- reuses the accepted transactional-inbox pattern rather than inventing a second correctness model;
- domain-separated keys close a real cross-tenant confidentiality gap that a passing functional test alone would not have caught;
- relocation continuity for keyed evidence is now a planned, budgeted operational step rather than a production surprise.

### Negative / cost
- per-scope HKDF key derivation adds implementation surface beyond a single shared HMAC secret;
- relocation runbooks gain an additional precondition/gate;
- key-granularity-vs-erasure-granularity must be an explicit, recorded choice rather than an implicit default.

## Validation

Before production eligibility, conformance evidence SHALL prove:
- a query-layer bug or compromised internal tool cannot produce a valid cross-scope equality signal (domain-separated keys, not just correct predicates, are what prevents it);
- a tenant relocation carries historical verifier-generation continuity and does not produce spurious `reconciliation_blocked` waves from missing key material alone;
- a data-subject erasure event does not invalidate dedup continuity for unrelated in-flight messages under the same tenant.

## Exit / revisit conditions

Revisit if a future equality-preserving migration mechanism changes the comparison-profile/verifier model platform-wide, or if `OPEN-REL-022`'s capacity evidence shows co-resident dedup storage cannot meet production load at representative scale.
