# Document Governance

## Normative language

Canonical documents use the following meanings:

- **SHALL / MUST:** mandatory behavior or invariant.
- **SHOULD:** expected default; deviation requires rationale.
- **MAY:** optional behavior.
- **PROPOSED:** not yet an accepted decision.
- **OPEN:** intentionally unresolved and tracked.

## Hierarchy

When documents conflict, resolve the conflict explicitly. Do not silently select the implementation as truth. The intended hierarchy is:

1. accepted product requirements and invariants;
2. accepted security and quality requirements;
3. accepted ADRs and contracts;
4. system/data/platform design;
5. implementation.

A lower layer cannot redefine a higher layer without changing the higher-layer document.

## Document states

Documents may be `draft`, `proposed`, `accepted`, or `superseded`. Baselines should identify their status at the top of the document.

## Traceability

Important architecture decisions should reference the requirements, invariants, and quality attributes they satisfy. Tests should reference externally meaningful requirements or invariants where practical.

## Change discipline

Semantic changes are reviewed through pull requests. High-impact architecture, security, data, or contract changes require an ADR or RFC. Historical files are not edited to pretend a superseded decision never existed; they are marked superseded and linked to the replacement.