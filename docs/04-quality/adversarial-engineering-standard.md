# Adversarial Engineering Standard

**Status:** accepted

## Purpose

JLMIRROR SHALL treat external review as an independent red-team signal, never as the primary mechanism for discovering predictable defect classes. A material finding is not closed by a local patch alone; it must improve the repository's own engineering model.

## Required learning loop

Every material defect or review finding SHALL complete this sequence before closure:

1. **Local remediation** — remove the concrete defect without broadening authority.
2. **Root-cause classification** — identify the defect class and the invalid assumption that allowed it.
3. **Generalized invariant** — state the rule that would have prevented the entire class, not only the observed instance.
4. **Horizontal audit** — inspect sibling fields, sibling boundaries, alternate callers, serialization paths, export paths, tenant transitions, and authority transitions for the same class.
5. **Permanent guardrail** — encode the invariant in executable validation, falsification tests, architecture/governance checks, or an explicitly reviewable contract wherever technically possible.
6. **Independent red team** — only after the internal gate is clean may an external reviewer be used to search for residual or novel failures.

A review finding SHALL NOT be considered fully resolved if the same defect class can predictably recur in an adjacent field or boundary that was not audited.

## Boundary invariants

### Untrusted until validated

Type annotations, dataclasses, generated models, SDK types, provider schemas, or caller intent SHALL NOT be treated as runtime proof. Any value that can originate from parsing, deserialization, transport, plugin/provider input, persistence, user input, or another process is untrusted until runtime validation succeeds.

No operation that presupposes type or shape — including regex matching, set/dict membership, indexing, splitting, encoding, hashing, comparison, iteration, arithmetic, or attribute dereference — may occur before the required runtime checks.

When one malformed field exposes a missing runtime guard, the horizontal audit SHALL cover every sibling field of the same boundary object.

### Optional context cannot own business liveness

Observability, tracing, baggage, diagnostic metadata, correlation hints, and other non-business context SHALL NOT suppress, duplicate, reorder, authorize, identify, or otherwise change an otherwise valid business effect unless an explicit canonical contract grants that authority.

Malformed optional context SHALL fail closed for that context and remain isolated from business processing and delivery semantics.

### Representation is not authority

Byte equality, prefixes, formatting, object type, network origin, provider identity, field presence, or successful parsing SHALL NOT by themselves prove authorization, tenant scope, provenance, trust, idempotency, ordering, or canonical identity.

Authority must be explicit, authenticated where required, scoped to the semantic object it governs, and independently revocable or rejectable according to its contract.

### Proof issuance must prove the operation

A proof or attestation SHALL NOT be issuable independently of the operation it claims occurred. The issuing API must either perform the protected transformation itself or consume an unforgeable result/capability produced by that transformation.

Proofs SHALL bind semantic identity rather than incidental serialization. Legitimate representation changes that preserve the governed identity must not invalidate the proof unless the representation itself is the governed object.

### Tenant isolation at observable representation

Tenant isolation SHALL hold on the raw/exported representation visible to telemetry backends, logs, caches, indexes, providers, and operators. A helper that checks tenant IDs is insufficient if globally correlatable bytes remain exposed elsewhere.

Every exported field capable of correlation SHALL be audited for cross-tenant join channels, including vendor metadata, baggage, trace state, identifiers, labels, and high-cardinality attributes.

## Horizontal adversarial questions

Before requesting external review, the internal review SHALL answer at least:

- Which values are assumed typed only because of annotations or constructors?
- Which operations can throw outside the intended fail-closed exception path?
- Which sibling fields share the same validation pattern?
- Which public or indirectly callable API can bypass the intended safe wrapper?
- Where is representation being mistaken for authority or provenance?
- Can optional metadata alter liveness, retry, delivery, ordering, identity, or authorization?
- Can the same raw or derived value correlate two tenants outside application helpers?
- Can a proof be issued for a value that did not actually pass the protected transformation?
- Is the proof bound to semantic identity or to an incidental serialization that legitimate hops must change?
- Does the test suite falsify malformed runtime types, not only semantically invalid well-typed values?
- Does a local fix require auditing the entire boundary object or adjacent trust boundary?

## Review independence

External tools, including automated reviewers, are defense-in-depth. Their absence or failure SHALL NOT turn an internally incomplete change into an acceptable one. Internal exact-head CI, repository-owned falsification, horizontal review, and authority-state validation remain mandatory.

The target condition is not "the external reviewer found nothing because its previous comments were patched." The target condition is "the repository's own invariants and falsification model already anticipated the known defect classes, leaving the external reviewer to search primarily for novel ones."
