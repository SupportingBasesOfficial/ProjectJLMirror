# ADR-021 — Monitoring Source-Instance Replacement: Staged Candidate and Atomic Cutover

**Status:** proposed
**Date:** 2026-08-27
**Reversibility:** costly (identity-domain-boundary semantics; downstream Monitoring consumers depend on generation stability once accepted)

## Context

`docs/03-domains/monitoring-domain-contract.md` and `docs/09-api-contracts/monitoring-domain-api-contract.md` (Wave 4 Monitoring governance package) define a mechanism for replacing the physical external-provider instance behind a `monitoring_source` (for example, swapping which Zabbix server a tenant's monitoring source points at) without losing or corrupting the source's stable logical identity. The mechanism was drafted directly inside those Phase 03/09 contract documents, framed as a "provider-specific instantiation" of already-accepted architecture. An adversarial multi-round review (documented in this project's session history) found that framing inaccurate: no existing ADR authorizes a "provider-instance generation with staged-candidate validation and atomic cutover" mechanism. ADR-013 (External Provider Adapter Architecture) governs outbound-connector/inbound-callback trust boundaries only and does not mention instance replacement, generations, or cutover. ADR-019 (Scaling, Cell Expansion and Tenant Relocation) establishes a structurally similar *tenant placement* relocation idiom but does not extend it to *external-provider-instance* identity.

This ADR exists to close that governance gap: it does not redesign the mechanism (the review found the design itself sound and consistent with this platform's established idioms), it gives that already-drafted mechanism the ADR-level authorization it was missing before Wave 4 implementation may treat it as binding.

The underlying problem is real and recurring, not specific to Zabbix: any external-provider adapter whose native object IDs are only unique within one provider instance (Zabbix `hostid`/`itemid`/`triggerid`/`eventid` are small sequential integers scoped to a single running Zabbix server) needs a way to let a tenant point the same logical `monitoring_source` at a *different* physical instance — a server migration, a disaster-recovery failover of the tenant's own monitoring infrastructure, a vendor/version upgrade requiring a fresh install — without silently merging the old instance's native IDs with the new instance's numerically-identical-but-semantically-different IDs.

Drivers: `FR-MON-001..006`, `FR-OPS-001..003`, `AC-001` (tenant isolation), `AC-003` (provider failure containment), `INV-ASYNC-001`, `docs/03-domains/monitoring-domain-contract.md`, `docs/09-api-contracts/monitoring-domain-api-contract.md`.

## Requirements and invariants

- **Identity-domain boundary.** A provider-native ID is only comparable within `(tenant_id, monitoring_source_id, provider_profile, source_instance_generation)`. The same native ID appearing under two different generations MUST project as two independent platform entities and MUST NOT merge on numeric similarity (`monitoring-domain-contract.md:85`, mirroring the Zabbix contract's `zabbix_instance_generation` rule).
- **No split-brain across cutover.** There is never more than one active generation for a source at a time (`monitoring-domain-contract.md:585`). Cutover has exactly one serialized winner, matching this platform's already-accepted stale-writer-fencing idiom (ADR-004's relocation state machine; ADR-019's placement-generation-bound stale-writer rejection).
- **Non-disruptive staging.** A replacement candidate can be created, validated, and re-validated without affecting the currently active generation's correctness — a healthy active generation is never retired before its successor proves admissibility (`monitoring-domain-contract.md`, "Replace instance" section).
- **Bounded, not O(N), cutover.** Cutover MUST NOT require rewriting every resource/metric/problem/health row from the prior generation; historical-generation classification is derived at read time, not migrated at write time (`monitoring-domain-contract.md:193,439`).
- **Recovery continuity.** Cutover ambiguity across crash/PITR/relocation follows the same `(R,F]` reconciliation discipline already established platform-wide by ADR-018, and the same placement-generation-bound stale-writer-rejection discipline already established by ADR-019 — this ADR does not invent a new recovery model, it applies the existing one to a new identity axis (provider-instance generation, alongside the already-covered tenant-placement generation).
- **No fabricated negative evidence.** Retiring a generation never by itself fabricates `removed`, `retired`, or `resolved` state for the objects that generation owned (`monitoring-domain-contract.md:87,197`) — this is the platform-wide `uncertainty != absence` rule (already established for recovery generally) applied to instance replacement specifically.
- **Generation values are opaque.** Per the companion clarification added to the domain/API contracts during this review, `source_instance_generation`/`active_source_instance_generation`/`candidate_generation` are high-entropy opaque tokens compared only for equality, never magnitude — consistent with this platform's existing `session_generation` convention (`src/jlmirror_authority/session.py`).

## Options considered

### Option A — No dedicated replacement mechanism; require a new `monitoring_source` for every instance change

A tenant replacing their monitoring server would create an entirely new `monitoring_source` and manually retire the old one.

- Strengths: zero new mechanism, zero new ADR needed.
- Weaknesses: breaks `FR-MON-006`'s intent that provider identifiers stay external references under a *stable* logical source — every instance swap would force the tenant to lose their source's history/dashboards/configuration continuity, or require ad hoc, ungoverned data-migration tooling per swap. Does not scale to a mega-tech multi-tenant platform where instance replacement (DR failover, vendor migration, version upgrade) is a routine operational event across hundreds/thousands of tenants, not a rare edge case.

### Option B — In-place instance swap with no staged validation or generation fencing

Allow editing the source's provider endpoint directly (as an ordinary field edit), trusting the operator to have already validated the new instance works.

- Strengths: simplest possible mechanism.
- Weaknesses: directly violates the identity-domain-boundary requirement above — reused numeric IDs from the new instance would silently merge with the old instance's data the moment the URL changes, with no way to detect or prevent it. This is precisely the failure mode the adversarial review confirmed as a real, exploitable gap when a URL-change path lacks explicit generation advancement.

### Option C (chosen) — Staged replacement candidate with independent validation, followed by an explicit, fenced, atomic cutover

A replacement request creates a durable, versioned `monitoring_source_replacement_candidate` that is validated independently of the active generation (via the accepted outbound/SSRF connector boundary, never inside the ordinary configuration transaction) and can only be activated through a separate, explicit, privileged action once validation proves current. Activation is a single atomic transaction that fences the prior generation's poll authority, advances `active_source_instance_generation`, and emits exactly one `monitoring.source-generation.changed` outbox obligation — mirroring the exact shape ADR-004/019 already use for tenant placement relocation, applied here to provider-instance identity instead of tenant/cell identity.

- Strengths: closes the identity-domain-boundary gap Option B leaves open; keeps the active generation fully operational and correct while a replacement is validated (non-disruptive staging); reuses an already-accepted, already-reviewed fencing/generation idiom rather than inventing a new correctness model from scratch; bounded/derived (not O(N)) cutover keeps the mechanism viable at real multi-tenant scale.
- Weaknesses: more mechanism than Option A/B — a candidate lifecycle, a freshness-binding contract for validation evidence, and an atomic multi-step cutover transaction are genuine new surface area requiring their own conformance tests (already specified as falsification vectors in `monitoring-domain-contract.md` and `monitoring-domain-api-contract.md`); the residual risk that an operator bypasses the explicit replacement action via an in-place URL edit is mitigated (the ordinary edit path rejects base-URL changes outright) but not structurally eliminated by any single technical control — it depends on the ordinary-edit rejection being correctly implemented and enforced.

## Decision

Option C is accepted. The exact mechanism — canonical identities, the `monitoring_source_replacement_candidate` state machine, the validation-currentness freshness contract, and the atomic cutover transaction steps — is specified in `docs/03-domains/monitoring-domain-contract.md` ("Replace instance — staged candidate, then atomic cutover" and "Replacement-validation currentness" sections) and exposed via `docs/09-api-contracts/monitoring-domain-api-contract.md`'s `monitoring.replaceSourceInstance` and `monitoring.activateReplacementCandidate` operations. This ADR does not restate those field-level details; it authorizes the mechanism at the architecture-decision level and binds it to the invariants above. Any future change to the mechanism's fixed semantics (identity-domain-boundary rule, single-active-generation invariant, non-O(N)-cutover guarantee, or recovery-continuity treatment) is an ADR-level change, not a Phase 03/09 contract-level one, per `docs/00-foundation/document-governance.md`'s hierarchy rule.

This mechanism generalizes beyond Zabbix: any future Monitoring Source provider profile whose native IDs are only unique within one instance inherits this same identity-domain-boundary/candidate/cutover treatment without a new ADR, provided it does not change the fixed invariants above.

## Consequences

### Positive

- closes a real identity-corruption gap (reused provider-native IDs silently merging across instance swaps) that the prior in-place-edit design left open;
- reuses this platform's already-accepted, already-reviewed generation-fencing/stale-writer-rejection idiom (ADR-004, ADR-019) rather than inventing a new correctness model;
- keeps the currently active generation fully correct and undisturbed while a replacement is validated — no forced downtime or degraded monitoring during a provider migration;
- bounded/derived cutover scales to real multi-tenant volume (no per-tenant O(N) rewrite as monitoring fleets grow);
- generalizes to future provider profiles without requiring a new ADR per provider, as long as the fixed invariants hold.

### Negative / cost

- meaningful new surface area (candidate lifecycle, validation-freshness contract, atomic cutover transaction) requiring its own conformance/falsification test suite before implementation, beyond what a simpler mechanism would have needed;
- the residual risk noted in the companion Zabbix contract (an operator bypassing the explicit replacement action, e.g. via infrastructure outside JLMIRROR's control) is mitigated, not eliminated, by rejecting in-place base-URL edits;
- validation-evidence freshness horizon and candidate-generation retention are still open numeric/mechanism questions (tracked as C2/C3 items in the Monitoring domain contract's "Remaining OPENs" section), not settled by this ADR.

### Risks

- if a future provider profile's native IDs are NOT instance-scoped (e.g., a provider with globally unique IDs), applying this mechanism unmodified would be unnecessary overhead for that profile — the mechanism's applicability, not its correctness, would need re-evaluation per provider, which the domain contract already anticipates by scoping the identity-domain-boundary rule to providers whose native IDs are instance-scoped.

## Validation

Before Wave 4 implementation treats this mechanism as binding, conformance evidence SHALL prove (per the falsification vectors already specified in `monitoring-domain-contract.md` and `monitoring-domain-api-contract.md`, cross-referenced here rather than restated):

- reused native IDs across two generations project as independent platform entities, never merged;
- a replacement candidate cannot mutate canonical current state before atomic cutover;
- concurrent cutover attempts against the same source produce at most one active-generation winner;
- cutover does not synchronously rewrite prior-generation resource/metric/problem/health rows;
- an ordinary configuration edit that changes the provider base URL is rejected, not silently accepted as same-generation;
- cutover ambiguity across crash/PITR/relocation is resolved through `(R,F]` reconciliation before further protected replacement admission, per ADR-018's existing continuity model;
- generation retirement alone never fabricates `removed`/`retired`/`resolved` state for the retired generation's objects.

## Exit / revisit conditions

Revisit this ADR if: a future provider profile's native identity model makes instance-scoped generation fencing unnecessary (see Risks above); production evidence shows the staged-candidate/cutover mechanism's operational cost (validation infrastructure, candidate retention) is disproportionate to actual replacement frequency across the tenant fleet; or a platform-wide generalization of ADR-004/019's placement-generation idiom is later adopted that this mechanism should be re-expressed in terms of, rather than maintaining a parallel Monitoring-specific instantiation.

## Migration / rollout

No existing implementation depends on this mechanism (Wave 4 has not yet begun implementation). Once accepted, `docs/16-implementation-readiness/16-wave-4-monitoring-entry-gate.md`'s readiness matrix row for "replacement candidate/cutover" is promoted from "PROPOSED mechanism — pending ADR-021" to its prior `contract-ready` classification, and Wave 4 implementation may treat the mechanism as binding.
