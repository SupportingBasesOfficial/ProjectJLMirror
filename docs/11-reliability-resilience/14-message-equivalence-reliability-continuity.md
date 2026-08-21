# Phase 11 — Message-Equivalence Reliability Continuity

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience  
**Authority anchor:** accepted `main@0872fa5cd672f79cc83cec81df2d580186fcdae2`  
**Applies to:** `rel.consumer-inbox-effect@1`, `rel.replay-consume-state@1`, and `rel.secret-key-authority@1` only where keyed/authenticated message-equivalence evidence is selected

## Purpose

This companion materializes, at the Reliability & Resilience layer, the accepted Phase 10 message-equivalence hardening now present in `main@0872fa5cd672f79cc83cec81df2d580186fcdae2`.

Phase 10 already fixes the semantic/security contract: a repeated trusted scoped `message_id` is a benign duplicate only when durable evidence proves the same immutable logical message under the accepted canonical comparison profile; retained evidence that cannot be interpreted because its required historical profile/verifier authority is missing is **unknown equivalence**, not duplicate success.

Phase 11 therefore defines how those accepted properties behave under dependency outage, recovery, profile/key rotation, overload, malicious equality probing and mixed-version execution. It does not select a hash/MAC algorithm, canonicalization implementation, KMS/secret product, storage product, key type, rotation interval or numeric retention horizon.

## Normalized-catalog relationship

`07-capability-resilience-profiles.md` remains the canonical base catalog for Phase 11 reliability profiles. This document is a mandatory normalized extension for the exact profile keys listed above and supplies only the following Phase-10-derived conditional dimensions:

```text
message_equivalence_comparison_authority
message_equivalence_failure_binding
message_equivalence_security_capacity_policy
message_equivalence_recovery_continuity
message_equivalence_compatibility_policy
```

It does not redefine ownership, scope, retry policy, circuit policy, general failure taxonomy or any other field already materialized by `07`.

For an applicable profile key, the complete semantic manifest is the exact-key join of `07` plus this companion as required by `08-reliability-semantic-manifest.md`. Omitting this companion for an applicable duplicate-sensitive profile is a Phase 11 acceptance blocker.

## Accepted comparison authority

For duplicate-sensitive admission, comparison begins only after the trusted identity has been derived:

```text
(consumer_contract, message_identity_scope, message_id)
```

The comparison authority consists of, as applicable:

- protected retained canonical immutable content; or
- a confidentiality-safe canonical fingerprint/digest; or
- an authenticated/keyed comparison value such as a MAC; or
- another accepted deterministic durable comparison authority;
- the stable canonical comparison-profile/version required to reproduce the original equality result;
- the non-secret historical verifier/key-generation reference required by the selected evidence form;
- the narrowly authorized historical verification authority required to interpret that evidence.

Identity alone is never equivalence proof.

## Reliability failure bindings

The same root dependency failure can have different canonical meaning at different profile boundaries. The secret/key authority classifies its own reachability; the consumer/replay profiles classify whether protected message-effect eligibility can still be proven. These bindings SHALL be joined without overwriting the base `07` bindings.

### `rel.consumer-inbox-effect@1`

| Condition | Canonical failure class | Required mode |
|---|---|---|
| same trusted scoped ID and proven equivalent immutable content | `duplicate` | `fail_fast` through the accepted dedup/result-return path; no protected effect re-execution |
| same trusted scoped ID and non-equivalent immutable content | `identity_conflict` | `reconciliation_blocked` / governed integrity quarantine |
| required historical comparison/verifier dependency is temporarily unreachable/unavailable while the retained evidence/profile mapping itself remains intact and trusted | `unavailable` | `reconciliation_blocked` |
| comparison evidence/profile/verifier-generation continuity is missing, rolled back, retired without valid migration, mismatched or otherwise cannot be reconstructed for the supported historical identity | `recovery_continuity_blocked` | `reconciliation_blocked` |
| comparison implementation/profile/evidence authority is compromised or cannot be trusted | `compromised_or_untrusted` | `fail_closed` |

`07` does not otherwise materialize `unavailable`, `recovery_continuity_blocked` or `compromised_or_untrusted` for this consumer profile; this companion therefore supplies those exact conditional bindings rather than conflicting with an existing mode.

A temporary dependency outage and a continuity defect are deliberately distinct. Reachability restoration may clear `unavailable` only after the same historical comparison authority becomes usable and proves equivalence; it does not repair a `recovery_continuity_blocked` condition by itself.

### `rel.replay-consume-state@1`

The base `07` profile already owns a generic `unavailable:fail_closed` binding for replay/consume-state unavailability. This companion SHALL NOT redefine that failure class.

At the replay profile boundary, inability to establish historical message equivalence because its required historical verifier is unavailable is represented as a **comparison-continuity inability**, not as a second generic `unavailable` mapping:

| Condition | Canonical failure class | Required mode |
|---|---|---|
| historical message identity/evidence exists but its required comparison profile/verifier cannot currently establish the supported historical equality result, including temporary verifier unavailability for that historical proof | `recovery_continuity_blocked` | `reconciliation_blocked` |
| historical comparison profile/evidence authority is compromised or untrusted | `compromised_or_untrusted` | `fail_closed` |
| conflicting immutable content appears under the same trusted scoped identity | `identity_conflict` | `reconciliation_blocked` (same base mode, with the stronger Phase 10 comparison semantics) |

Thus `rel.replay-consume-state@1` keeps one deterministic generic `unavailable` mode from `07`, while historical equivalence-proof failure uses the distinct existing `recovery_continuity_blocked` class added by this normalized companion. Operator replay authorization does not override either binding.

### `rel.secret-key-authority@1`

When keyed/authenticated message-equivalence evidence is selected, the secret/key profile retains its existing base binding:

```text
unavailable -> capability_unavailable
```

That describes the secret/key dependency itself. It does not imply that a consumer or replay operation may reinterpret missing verification as duplicate success.

The profile additionally preserves this authority distinction:

```text
historical verifier generation
!=
current unrestricted cryptographic authority
```

A restored or retained old verifier may be used only by the narrowly authorized historical comparison path for evidence bound to that generation. It does not authorize unrelated messages, tenants, consumers, encryption, signing or current key issuance merely because the key material is reachable.

Temporary key/verifier backend outage remains an availability failure of the key dependency. Missing/rolled-back historical verifier continuity is a recovery-continuity defect. Compromised verifier trust is a trust failure. These classes SHALL NOT be collapsed into one generic retry state.

## Confidentiality and anti-oracle invariant

Derived equivalence evidence inherits source-data confidentiality risk.

A plain unsalted/unkeyed digest of low-entropy confidential immutable values is not automatically safe because it may create an offline dictionary oracle. The accepted implementation profile uses a protected form when disclosure/guessing risk requires it.

Equivalence evidence SHALL NOT become:

- a global reverse lookup;
- a cross-tenant/cross-consumer correlation namespace;
- an externally queryable equality oracle;
- authorization, routing, ordering or placement authority;
- a public identifier or bearer capability;
- ordinary log/metric/quarantine data when its classification makes disclosure unsafe.

Equal semantic content in two different trusted scopes cannot cause cross-scope deduplication or reveal that the scopes contain the same confidential values.

## Bounded comparison and KMS work

Duplicate/equivalence verification is a reliability amplification surface.

Implementations SHALL bound, attribute and isolate as applicable:

- comparison attempts per admitted scoped identity;
- historical-profile lookup work;
- KMS/secret-store requests;
- key/profile migration work;
- equality-failure diagnostics;
- quarantine and recovery scans;
- tenant/consumer/source skew.

Crafted duplicate IDs or conflicting payloads cannot force unbounded KMS/secret-store work, bypass admission budgets or monopolize shared comparison capacity.

Exact numeric bounds remain governed by `OPEN-REL-022`; the mechanism/backend remains governed by `OPEN-REL-016`; semantic-horizon retention remains governed by `OPEN-REL-025`.

## Recovery and `(R,F]` continuity

For duplicate-sensitive identities, recovery continuity includes not only receipt/effect and comparison-evidence bytes but also the authority required to interpret those bytes:

```text
message identity/scope
+ inbox/effect/result state
+ comparison evidence
+ comparison-profile/version
+ non-secret historical verifier generation reference (when applicable)
+ required narrowly authorized historical verification authority
```

A restore that has the fingerprint/MAC but not the accepted historical interpretation authority remains uncertain. For the consumer profile, temporary dependency outage can be `unavailable`; for replay/historical proof and for continuity defects, the protected replay path is `recovery_continuity_blocked`. Neither permits duplicate success.

A restore that revives an obsolete verifier does not make that verifier current authority for unrelated work.

If an equality-preserving migration replaces an old profile/verifier, the migration must prove the same historical equality result before the old authority is retired. Otherwise affected identities remain `recovery_continuity_blocked`.

## Mandatory adversarial extension of `FV-ASYNC-003`

`FV-ASYNC-003` remains the canonical async identity/equivalence vector in `09-reliability-validation-and-fault-matrix.md`. For `rel.consumer-inbox-effect@1` and duplicate-sensitive replay, its aggregate design/conformance definition SHALL include every applicable branch below:

1. same trusted scoped ID + conflicting immutable semantic content -> `identity_conflict:reconciliation_blocked`;
2. original full payload minimized but surviving protected evidence still distinguishes equivalent from conflicting reuse;
3. consumer path: required historical verifier backend temporarily unavailable while evidence/profile continuity remains intact -> `unavailable:reconciliation_blocked`, with no blind retry/effect eligibility;
4. replay path: historical equality cannot currently be established by the required verifier, including verifier unavailability for that historical proof -> `recovery_continuity_blocked:reconciliation_blocked`, without redefining replay's generic base `unavailable` binding;
5. evidence/profile/verifier-generation continuity missing, rolled back, retired without valid migration, mismatched or restored older -> `recovery_continuity_blocked:reconciliation_blocked`;
6. comparison authority/profile is compromised/untrusted -> `compromised_or_untrusted:fail_closed`;
7. low-entropy confidential content cannot be recovered or tested through ordinary plain-digest logs, exports or operator surfaces;
8. equal semantic content under different trusted tenant/consumer/message scopes cannot be correlated or deduplicated through a global equality lookup;
9. comparison-profile/canonicalization or verifier/key rotation preserves historical equality through accepted retained authority or an equality-preserving migration before retirement;
10. restored obsolete verifier/profile cannot become current authority for unrelated messages/scopes;
11. crafted duplicate identities cannot generate unbounded comparison, KMS, secret-store or migration work.

Aggregate pass requires every applicable branch. Absence of implementation/runtime evidence is not a design failure, but omission of a branch from the Phase 11 evidence plan is a design-acceptance failure.

These branches remain governed by existing blockers `RB-REL-010`, `RB-REL-018` and `RB-REL-022` according to the affected correctness, recovery and evidence-integrity dimension; no new blocker namespace is introduced.

## Compatibility classification

A change is at least `security_breaking` and/or `recovery_breaking`, with `capacity_risk` where applicable, when it:

- changes the canonical comparison surface/profile so historical equality may change;
- weakens evidence confidentiality/domain separation or exposes cross-scope equality;
- retires a historical verifier without retained verification or equality-preserving migration;
- collapses dependency availability, historical continuity and compromised-trust conditions into a retry/default that can widen eligibility;
- changes unknown-equivalence handling into duplicate success or protected-effect eligibility;
- changes recovery interpretation of retained evidence/profile/verifier generations;
- materially changes comparison/KMS amplification or tenant isolation.

Matching API/event payload schemas do not make such mixed versions compatible.

## OPEN discipline

This companion does not close implementation choices.

The following remain OPEN under existing registries:

- `OPEN-REL-016`: concrete KMS/secret mechanism and historical verifier implementation where keyed evidence is selected;
- `OPEN-REL-022`: numeric capacity/cost/amplification envelopes for comparison/KMS/migration work;
- `OPEN-REL-025`: numeric semantic retention horizons and physical evidence lifecycle.

Exact fingerprint/hash/MAC algorithm, domain-separation encoding, comparison-profile serialization, verifier backend and equality-preserving migration mechanism also remain subordinate implementation/profile choices under accepted Phase 10 governance. Phase 11 fixes only failure, isolation, recovery, compatibility and evidence obligations.

## Assurance and authority

This companion inherits the accepted Native Assurance Governance package. External reviewer/model evidence may supplement the gate, but no named reviewer or unavailable external service is a mandatory progression dependency.

A clean review of an older Phase 11 SHA does not validate a HEAD containing or omitting this companion. Final readiness requires the exact-final-HEAD Native Assurance Gate, panoramic propagation review and separate explicit merge authorization.