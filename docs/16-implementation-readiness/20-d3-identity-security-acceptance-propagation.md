# D3 Identity/Security Separate Acceptance Propagation

**Status:** proposed D3 separate acceptance  
**Base:** `main@e069f2e86b24c3c0a97af315ea600bd3d90e79f1`  
**Authority source:** merged PR #50, `governance(d3): promote D3-E conformance evidence`  
**Scope:** accept the five fully conformed D3 C2 mechanism candidates; no Wave 4, Product implementation, production, D4 transport, or C3 numeric/topology authority

## Purpose

PR #50 completed the machine-owned D3 evidence ledger at 45/45 approved proofs and moved every D3-A..E track to `per_track_conformed`. The D3 entry gate explicitly requires a later **separate acceptance action** before those mechanism candidates become accepted C2 dispositions.

This record performs only that state transition. It does not reinterpret the evidence, replace source decisions, change candidate versions or artifact pins, grant implementation authority, or close any C3/D4 decision.

```text
PER_TRACK_CONFORMED != D3_ACCEPTED
D3_ACCEPTED != CANONICAL_PRODUCT_IMPLEMENTATION_AUTHORIZED
D3_ACCEPTED != WAVE4_AUTHORIZED
D3_ACCEPTED != PRODUCTION_AUTHORIZED
D3_ACCEPTED != D4_SELECTED
```

## Canonical evidence package

The D3-E evidence promotion was merged into canonical `main` as:

```text
e069f2e86b24c3c0a97af315ea600bd3d90e79f1
```

Its exact reviewed HEAD was:

```text
4654b9d26818c2a9e620dce88c6d2feaba67ddf2
```

Final exact-head assurance before that merge included all twelve pull-request workflows green and a fresh Codex adversarial review reporting no major issues on the same reviewed commit. The six D3-E proof slots retain their original source-evidence provenance from exact reviewed source HEAD `42722507a2eb410f81df2a77b3506432d4b6fb27`, workflow run `33564230738` / run #79, rather than rewriting evidence identity to the later squash commit.

The machine-owned ledger therefore enters this acceptance proposal with:

```text
tracks = 5
required_evidence = 45
evidence_completed = 45
evidence_remaining = 0
all_tracks = per_track_conformed
canonical_product_implementation_authority = not_granted
wave4_implementation_authority = not_granted
production_authority = none
d4_transport_authority = not_selected_not_granted
```

## Separate acceptance transition

The governed transition is:

```text
gate_state: per_track_conformed -> separately_accepted
D3-A: per_track_conformed -> accepted_candidate
D3-B: per_track_conformed -> accepted_candidate
D3-C: per_track_conformed -> accepted_candidate
D3-D: per_track_conformed -> accepted_candidate
D3-E: per_track_conformed -> accepted_candidate
```

No evidence record, source decision, candidate identity, artifact digest, exclusion, or C3-open item changes as part of this transition.

## Accepted D3 C2 mechanism dispositions

| Track | Accepted candidate disposition | Boundary |
|---|---|---|
| D3-A | Keycloak 26.7.2 behind the accepted IdP/BFF boundary | IdP-native identity remains non-authoritative for JLMirror membership/authorization |
| D3-B | PostgreSQL 18.6 session system of record plus Redis-compatible derived security cache, with Valkey portability control | cache remains derived acceleration state; durable owner/currentness semantics remain authoritative |
| D3-C | HMAC-SHA256 double-submit CSRF profile with renewal-stable lineage and versioned current/previous keyring | bounded C2 mechanism only; production timing/numeric policy remains separately governed |
| D3-D | SPIRE 1.15.3 behind the accepted SPIFFE/X.509-SVID workload-identity port | workload identity authenticates workload only and never grants tenant/business authority |
| D3-E | OpenBao 2.6.2 Transit behind a provider-neutral key-authority port plus PostgreSQL shared `private_key_jwt` replay authority | cryptographic/replay authority only; no event transport, serialization, broker topology, ack/lease, or D4 behavior |

Acceptance makes these candidates the accepted C2 mechanism dispositions for D3. It does not make their product-native semantics part of the canonical domain model, and it does not make any candidate irreversible.

## Explicit non-authority boundary

This D3 acceptance does **not** grant or imply:

- canonical Product implementation authority;
- Wave 4 Monitoring implementation authority;
- production deployment authority;
- D4 broker/event transport, serialization, schema-registry, partition, ack/lease, quarantine, or topology selection;
- production C3 capacity, retention, timeout, cache, lease, rotation, SLO, RPO, RTO, or topology numerics;
- realtime, outbound webhook, public SDK, Alerting, ITSM, AIOps, FinOps, or Commercial activation;
- provider-native identity, roles, organizations, topology, or storage semantics as platform authority.

The machine-owned authority fields remain exactly:

```text
canonical_product_implementation_authority = not_granted
wave4_implementation_authority = not_granted
production_authority = none
d4_transport_authority = not_selected_not_granted
```

The following C3 items remain open and unchanged:

```text
OPEN-REL-031.B
OPEN-REL-008.B
OPEN-REL-016.B
OPEN-REL-023
production_capacity_topology_slo_rpo_rto_numeric_profiles
```

## Supersession rule

After this acceptance is reviewed and merged, this record supersedes only stale **operational D3 status statements** that say a D3-A..E candidate is merely pending/conformed-but-unaccepted or that D3 itself is not separately accepted.

It does not supersede historical rationale, evidence requirements, fixed invariants, Product exclusions, C3 ownership, or D4/Wave 4/production boundaries in `19-d3-identity-security-c2-entry-gate.md` or its source decisions.

## Assurance requirements for this acceptance PR

This transition is valid only if the final exact HEAD proves all of the following:

1. the machine manifest remains 45/45 with zero remaining evidence and exact approved provenance;
2. all five tracks are `accepted_candidate` and `gate_state` is `separately_accepted`;
3. candidate identities, pins, source-decision anchors, exclusions, and C3-open items are unchanged;
4. deterministic assurance and every applicable D3 conformance workflow are green on the exact final HEAD;
5. no workflow was weakened merely to tolerate accepted state;
6. all P0/P1/P2 review findings are resolved on that exact final HEAD;
7. a fresh adversarial Codex review is clean on that same HEAD;
8. merge occurs only after a separate explicit user authorization.

## Advancement boundary

After this D3 acceptance is merged, the next architecture gate may advance to D4 Eventing & Asynchronous Transport C2 and/or another explicitly governed readiness step. D3 acceptance by itself does not authorize Wave 4 implementation.

```text
D3_SEPARATELY_ACCEPTED
  -> next governed architecture/readiness gate
  -> explicit implementation authorization where applicable
  -> implementation
```

No CI result, product default, provider capability, framework choice, or AI output may skip those later authority transitions.
