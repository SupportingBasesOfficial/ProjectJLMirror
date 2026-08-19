# Canonical Baseline Acceptance — Gate A

**Status:** accepted  
**Acceptance date:** 2026-08-18  
**Acceptance act:** merge of the governance pull request that introduces this record

## Purpose

This record formalizes **Gate A** of JLMIRROR design governance. It accepts the normative layers that must exist before System/Data Design can itself be formally accepted and before API/Event contracts may be authored as implementation constraints.

## Accepted scope

Gate A accepts the current canonical baseline for:

- Product definition, scope, capabilities, actors/personas and exclusions;
- Functional Requirements, Business Rules, System Invariants and System-Level Acceptance Criteria;
- bounded contexts, context/domain maps and the data/capability ownership matrix;
- Quality Attributes, Quality Scenarios and the Capacity Envelope framework;
- Security Requirements, Security/Trust Model and Threat Model;
- Architecture Overview, Dependency Rules and Runtime Topology;
- ADR-001 through ADR-020 as listed in the Architecture Decision Index.

Acceptance means these documents are normative under `docs/00-foundation/document-governance.md` and may constrain lower design/contract layers. It does **not** mean every future implementation choice or numeric target has been selected.

## Ownership reconciliation performed by this gate

Formal acceptance re-audited the post-merge findings from the original foundation/domain review and closes two previously ambiguous ownership areas:

1. **Customer monitoring telemetry/history:** Monitoring owns the canonical semantics and lifecycle of customer monitoring telemetry/history, including accepted historical observations/metric samples. A specialized telemetry store may be a separate physical persistence authority behind the telemetry port; physical separation does not transfer logical domain ownership.
2. **Immutable accountability/audit evidence:** Compliance & Governance owns the immutable/append-only accountability ledger or protected audit-evidence authority and its governance/retention semantics. Domain owners remain responsible for producing required audit evidence atomically with protected mutations or through the accepted protected audit-intent protocol; ledger ownership does not grant Compliance & Governance direct mutation authority over source domain state.

The bounded-context, domain-map, context-map and ownership-matrix documents are aligned to those rules.

## Review evidence

The accepted baseline incorporates the hardened state produced through the repository's earlier staged reviews:

- **PR #1 — Foundation/Product/Requirements/Domain/Quality/Security:** established the original canonical baseline. Two ownership findings arrived after merge; this governance gate explicitly reconciles them before acceptance.
- **PR #2 — Architecture/ADR baseline:** established ADR-001..020 as a proposed architecture baseline. Realtime revocation, inbound-provider authentication/replay and cryptographic recovery concerns identified during review were subsequently strengthened by the System/Data hardening work.
- **PR #3 — System/Data Design hardening:** iteratively reconciled architecture, security, tenant isolation, idempotency/inbox/outbox semantics, realtime replay/current-authorization/placement behavior, recovery continuity, governance/erasure and artifact lifecycle. The final Codex review of head `fbf03a562b` reported no major issues, and PR #3 was squash-merged as `67fbd78b9f3af469e669a67a9bf0f003cffdecd4`.

Gate A is not considered complete merely because statuses were changed. The governance PR itself must receive a clean review focused on hierarchy consistency, ownership, status/prose alignment and accidental closure of intentionally OPEN decisions before it is merged.

## Intentionally OPEN after Gate A

The following are known OPEN decisions and are **not** implied by acceptance of this baseline. This inventory is not permission to treat an explicitly deferred or "to be defined" item elsewhere in the accepted baseline as resolved; such an item remains OPEN until separately accepted through its appropriate later phase/ADR/RFC/governance decision.

- queue technology/vendor;
- cache/replay-authority product or primitive;
- pub/sub or durable event-broker product;
- telemetry physical storage engine beyond the accepted port/semantics;
- object-storage vendor/mechanism beyond the accepted lifecycle/fencing invariants;
- secret-manager/KMS vendor;
- cloud provider and container/orchestrator product;
- exact globally unique ID generation algorithm;
- exact authentication/token protocol details not already constrained by the accepted trust/BFF model;
- numeric SLO, RPO, RTO, percentile latency, queue-lag and propagation/revalidation thresholds;
- exact HTTP status/header/idempotency representations **not already constrained by the accepted baseline**, which belong to Phase 09 API & Contracts. In particular, the accepted protected-WebSocket contract already requires a successful upgrade to return `101 Switching Protocols`, and rejected protected admission MUST NOT receive `101`;
- exact broker acknowledgement/partition/transport mechanics, which belong to Phase 10 Events/Async Contracts;
- artifact provenance/signing policy and related software-supply-chain release-signing details deferred by `TM-014`, which remain OPEN for the supply-chain phase;
- future service extraction decisions, which require the measured drivers and prerequisites of ADR-020.

`OPEN` means evidence or a later contract/ADR is still required. It does not weaken the already accepted security, isolation, consistency, recovery or ownership invariants.

## Gate B follow-on

Gate A intentionally left `docs/07-system-design/*` and `docs/08-data/*` as a proposed lower-level baseline pending a separate governance decision. Their later acceptance is recorded independently by **Gate B** in `docs/06-architecture/system-data-acceptance-2026-08-18.md`; that follow-on does not retroactively expand the scope of Gate A or alter the hierarchy established here.

Once Gate B is accepted and merged, Phase 09 API & Contracts may begin as a normative design phase under the accepted upstream Product/Requirement/Security/Architecture/System/Data authorities. Phase 10 Events/Async Contracts remains a separate later boundary and does not begin merely because Gate A or Gate B is accepted.

## Change discipline

After Gate A acceptance:

- semantic changes to accepted Product/Requirement/Security/Architecture decisions require the repository's ADR/RFC/governance process appropriate to the change;
- lower-level System/Data/API/Event/implementation documents may refine accepted decisions but may not silently redefine them;
- newly discovered contradictions are treated as governance defects and are corrected before downstream implementation relies on them.

## Validation / rollout

This gate changes documentation authority and ownership clarity only. It performs no production deployment, data migration, secret rotation, tenant relocation or runtime cutover. Operational rollout begins only in later implementation phases after the relevant lower design/contracts are also accepted.