# Decision Policy

## Decision types

### Requirement
A behavior or quality the system must provide. Requirements avoid prescribing implementation unless the technology itself is a business or regulatory constraint.

### Invariant
A condition that must remain true across implementations and runtime paths.

### Architecture Decision Record (ADR)
A durable decision that shapes structure, dependencies, data, runtime, security, platform, or evolution.

### Request for Comments (RFC)
A proposal requiring broader review before becoming normative. Accepted RFCs normally produce requirement updates, ADRs, or contract changes.

### Implementation choice
A local, replaceable decision that does not redefine accepted architecture or externally observable contracts.

## Decision quality

Significant decisions must state:

- context and problem;
- relevant requirements and quality attributes;
- alternatives considered;
- chosen option;
- positive and negative consequences;
- operational cost;
- security and tenant-isolation implications;
- migration and rollback implications;
- evidence or validation required;
- conditions that would justify revisiting the decision.

## Status lifecycle

`proposed -> accepted -> superseded | deprecated`

Rejected alternatives may be recorded when understanding why they were rejected prevents repeated debate.

## Reversibility

Decisions are classified as:

- **reversible:** low-cost to change;
- **costly:** migration or significant coordination required;
- **one-way/high-risk:** difficult to undo after scale or customer adoption.

Evidence requirements increase with irreversibility.

## Technology discipline

A technology is accepted only after the capability it serves is defined. For example, `durable background execution with retry and backoff` is a requirement; a queue product is an implementation decision until an ADR accepts it.