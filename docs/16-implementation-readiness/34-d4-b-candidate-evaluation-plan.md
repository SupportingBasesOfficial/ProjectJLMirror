# D4-B — Candidate Evaluation Plan

**Status:** candidate-evaluation planning only — no D4-B mechanism selected  
**Canonical base:** `main@9aefb026d8b8a80abc72f1be5c853059718f5ae2`  
**Track:** D4-B — serialization, schema, catalog and contract versioning

## Purpose

D4-B has completed its reviewed evidence ledger at **5/5**, but `OPEN-EVT-002`, `OPEN-EVT-003` and `OPEN-EVT-004` remain intentionally unresolved. This record defines the next governed step: evaluate concrete mechanism families without collapsing three separate choices into one technology bundle.

```text
EVIDENCE COMPLETE != TECHNOLOGY SELECTED
WIRE FORMAT != SCHEMA CATALOG
SCHEMA CATALOG != CONTRACT VERSION SYNTAX
CANDIDATE ELIGIBLE != SELECTED
D4-B SELECTED != D4 ACCEPTED
D4 ACCEPTED != PRODUCT/WAVE4/PRODUCTION AUTHORITY
```

## Three independent decision axes

### Axis A — Wire serialization and schema language (`OPEN-EVT-002`)

Candidate classes admitted to evaluation:

- bounded JSON + JSON Schema profile;
- Protobuf profile;
- Avro profile;
- another reviewed equivalent profile only if it satisfies the same machine-owned proof obligations.

Internal broker messages and external webhook contracts are **not required to share one wire format**. A split is allowed only if both surfaces preserve one explicit canonical semantic model, conversion rules are deterministic, historical interpretation remains available, and no surface-specific parser behavior can override protected envelope/payload authority.

The evaluation must prove bounded canonical interpretation, duplicate/alias rejection, explicit required/optional/null/enum semantics, forward/unknown-field behavior, historical reader continuity, deterministic duplicate-sensitive content equivalence, bounded parsing/decompression, no dynamic untrusted schema/code loading, and stable cross-language semantics.

### Axis B — Schema registry / contract catalog tooling (`OPEN-EVT-003`)

Candidate classes admitted to evaluation:

- reviewed Git catalog;
- registry-backed catalog;
- hybrid reviewed Git + registry catalog;
- another reviewed equivalent catalog.

A registry product is **not** canonical merely because a producer can register a schema. The reviewed contract remains the authority. Any selected catalog must retain provenance/history, compare the semantic manifest as well as syntax, retain or resolve historical reader/upcaster/comparison-profile metadata, enforce authenticated/authorized access, fail safely during tooling outage, detect semantic compatibility breaks in CI, and remain replaceable without changing logical contract identity.

### Axis C — `contract_version` representation (`OPEN-EVT-004`)

Candidate classes admitted to evaluation:

- positive integer family revision;
- semantic-version-like contract revision;
- opaque monotonic contract token;
- another reviewed equivalent representation.

The representation must remain distinct from deployment, API, provider, realtime-protocol and registry versions. Breaking semantic changes require a new incompatible contract version/family or an accepted migration. Historical messages retain their original version semantics. A numeric or semantic-looking representation does **not** automatically grant ordering/range semantics unless the selected profile explicitly defines them.

## Cross-axis anti-coupling rule

The three axes are independently selectable. In particular:

- choosing Protobuf does not automatically choose a particular registry;
- choosing JSON Schema does not automatically choose Git-only storage;
- choosing a registry does not automatically choose Avro/Protobuf/JSON;
- choosing an integer or semantic-version-like `contract_version` does not make a registry version canonical;
- a candidate that only works by coupling logical contract identity to vendor registry IDs, generated-code versions or physical broker metadata is ineligible.

This rule is deliberate. It prevents a convenience tool from becoming architectural authority by implication.

## Evaluation states

A candidate evaluation may conclude only:

- `eligible_for_evidence_execution`;
- `ineligible_by_contract`;
- `insufficient_evidence`.

This planning stage cannot emit `selected`, `production_ready`, `preferred_without_evidence`, or any authority grant.

## Evidence execution expected after this plan

A later source-evidence PR must exercise eligible candidates against the already accepted D4-B semantic invariants. Candidate-dependent claims require real parser/tool/runtime behavior where relevant; documentation-only assertions cannot replace executable evidence.

At minimum the candidate evidence program must test:

1. canonical parse/serialize meaning and ambiguity rejection;
2. cross-language or cross-runtime semantic equivalence;
3. compatibility classification against positive and breaking changes;
4. historical reader/upcaster continuity;
5. deterministic immutable-content equivalence for duplicate-sensitive consumers;
6. catalog history/provenance and authorized access behavior;
7. catalog/tool outage and restore behavior without historical reinterpretation;
8. contract-version parse/comparison rules and separation from unrelated version namespaces;
9. migration/replacement behavior showing that vendor/tool identity is not canonical contract identity.

## Historical truth and current state

This plan must not rewrite the completed D4-B source/promotion evidence. Those records remain historical truth.

The current D4 state remains:

- D4-A: Kafka bounded-C2 selected, exact 7/7 evidence;
- D4-B: exact 5/5 evidence, candidate not selected;
- D4-C: open, unselected, uncredited;
- D4-D: open, unselected, uncredited;
- D4-wide evidence: 12/26;
- D4 gate: `scoped`;
- transport authority: `selected_not_granted`;
- Product/Wave 4 implementation authority: `not_granted`;
- production authority: `none`;
- C3 numeric/topology authority: `not_selected`.

## Machine-owned plan

`implementation/d4-eventing-async/d4-b-candidate-evaluation-plan.json` owns the evaluation inventory. Assurance tooling must pin:

- the exact three decision axes;
- allowed candidate classes;
- all `must_prove` obligations;
- anti-coupling invariants;
- allowed evaluation outputs;
- forbidden selection/authority outputs;
- unchanged D4 state and existing evidence ledgers.

Negative controls must demonstrate that CI rejects removal of an axis, candidate-class collapse, proof-obligation removal, cross-axis coupling, premature D4-B selection, evidence mutation, D4-A regression, sibling D4-C/D credit/selection, full-D4 acceptance and Product/Wave4/production/C3 authority escalation.

## Exit from planning

This planning PR is complete only when exact-HEAD assurance proves the plan is exhaustive and non-selecting. After merge, the next governed step is a **candidate source-evidence execution PR**, not a selection PR.

A later D4-B mechanism selection requires separate reviewed evidence, exact-HEAD review, zero material unresolved threads and separate explicit user authorization. Full D4 acceptance remains a still later transition.
