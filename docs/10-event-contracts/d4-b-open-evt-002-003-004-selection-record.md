# D4-B Selection Record — OPEN-EVT-002 / OPEN-EVT-003 / OPEN-EVT-004

## Current disposition

At bounded C2 scope, the following Phase 10 decisions are **RESOLVED by governed D4-B selection**:

- `OPEN-EVT-002` — wire serialization and schema language;
- `OPEN-EVT-003` — schema registry / contract catalog tooling;
- `OPEN-EVT-004` — `contract_version` representation.

The original `phase-10-open-decisions.md` remains the immutable Phase 10 baseline showing these items as open at the time that baseline was accepted. This record supplies the later governed disposition rather than rewriting historical baseline text.

## Selected bounded C2 profile

### OPEN-EVT-002

- internal broker: `protobuf_profile`;
- outbound webhook representation, if that Product surface is later separately authorized: `bounded_json_plus_json_schema_profile`;
- realtime protocol: unchanged from the independently accepted Phase 10 canonical JSON baseline.

Different wire representations are permitted only at explicit surface/adapter boundaries and must preserve one canonical logical contract meaning.

### OPEN-EVT-003

- selected mechanism: `hybrid_reviewed_git_plus_registry_catalog`;
- reviewed Git contract history remains canonical authority;
- registry remains an authenticated/authorized replaceable distribution, discovery, compatibility and physical-mapping surface;
- no registry vendor/product is selected by this decision.

### OPEN-EVT-004

- selected representation: `positive_integer_family_revision`;
- zero is invalid;
- the integer has equality identity semantics only;
- numeric ordering does not become compatibility, deployment, routing, authorization, API/provider/realtime or registry-version authority.

## Current authority boundary

This decision is a **bounded C2 contract-profile selection only**. It does not:

- accept full D4;
- grant canonical Product implementation authority;
- grant Wave 4 implementation authority;
- create outbound webhooks as a Product feature;
- select a registry product;
- authorize production deployment;
- select C3 numerics/topology;
- complete D4-C or D4-D.

D4 remains `scoped`, D4-wide evidence remains 12/26, D4-C/D remain open and separate full D4 acceptance remains required.

## Authoritative machine-owned records

Current D4-B selection authority is represented jointly by these machine-owned current-state records:

- `implementation/d4-eventing-async/d4-b-selection-record.json` — explicit D4-B bounded-C2 selection record;
- `implementation/d4-eventing-async/d4-b-evidence-plan.json` — current D4-B ledger carrying the selected profile while preserving exact 5/5 evidence accounting;
- `implementation/d4-eventing-async/state-manifest.json` — current global D4 state carrying the same D4-B selection while preserving D4-wide scope and authority boundaries.

Assurance validators, falsification tests and workflows verify and enforce these records but do not themselves carry or grant selection authority.

Full rationale and replacement governance:

- `docs/16-implementation-readiness/38-d4-b-bounded-c2-profile-selection.md`.

Historical Axis A/B/C source manifests remain intentionally `not_selected` because they describe the state at the time evidence was produced.
