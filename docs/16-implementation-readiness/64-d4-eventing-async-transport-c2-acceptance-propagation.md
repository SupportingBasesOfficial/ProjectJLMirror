# D4 Eventing & Asynchronous Transport C2 Separate Acceptance Propagation

**Status:** proposed D4 separate acceptance  
**Base:** `main@9a636d509828e95b05574964f39a27fab59a1a66`  
**Authority source:** merged PR #121, `feat(d4-c): select bounded C2 delivery recovery profile`  
**Scope:** accept the four fully reviewed D4 C2 candidate/profile dispositions; no transport implementation, Product, Wave 4, production, or C3 numeric/topology authority

## Purpose

PR #121 completed the last terminal D4 C2 disposition. D4 now has 26/26 required evidence, zero remaining evidence, and reviewed terminal candidate/profile selections for D4-A through D4-D. The D4 entry gate requires a later **separate acceptance action** after those conditions are met.

This record performs only that acceptance transition. It does not reinterpret source evidence, rewrite historical candidate-evaluation records, change selected candidates/profiles, choose C3 numerics/topology, or grant implementation/production authority.

```text
D4_SELECTED != D4_ACCEPTED
D4_ACCEPTED != D4_TRANSPORT_IMPLEMENTATION_AUTHORIZED
D4_ACCEPTED != CANONICAL_PRODUCT_IMPLEMENTATION_AUTHORIZED
D4_ACCEPTED != WAVE4_AUTHORIZED
D4_ACCEPTED != PRODUCTION_AUTHORIZED
```

## Canonical pre-acceptance package

The final D4-C selection was squash-merged into canonical `main` as:

```text
9a636d509828e95b05574964f39a27fab59a1a66
```

Its exact reviewed PR HEAD was:

```text
33492f9f54d1d98f5c8570803e09444df011292a
```

The exact-head matrix was terminal SUCCESS, including Deterministic Assurance and live Kafka recovery/capacity-ordering probes. Both material PR #121 findings were remediated, internalized into executable learning guardrails, and resolved before merge.

The machine-owned D4 state therefore enters this acceptance proposal with:

```text
tracks = 4
required_evidence = 26
evidence_completed = 26
evidence_remaining = 0
all_tracks = selected_candidate
gate_state = scoped
d4_transport_authority = selected_not_granted
canonical_product_implementation_authority = not_granted
wave4_implementation_authority = not_granted
production_authority = none
c3_numeric_topology_authority = not_selected
```

## Separate acceptance transition

The governed transition is exactly:

```text
gate_state: scoped -> separately_accepted
D4-A: selected_candidate -> accepted_candidate
D4-B: selected_candidate -> accepted_candidate
D4-C: selected_candidate -> accepted_candidate
D4-D: selected_candidate -> accepted_candidate
```

No candidate identity/profile, candidate status, source decision, required evidence, completed evidence, exclusion, historical source record, or later-gate authority changes as part of this transition.

## Accepted D4 C2 dispositions

| Track | Accepted C2 disposition | Boundary |
|---|---|---|
| D4-A | Kafka behind the broker-neutral anti-corruption boundary | acceptance does not authorize transport implementation or production topology/numerics |
| D4-B | explicit surface-bound serialization + hybrid reviewed Git/registry catalog + positive-integer family revision | canonical contracts remain provider-neutral and production schema/catalog topology remains separately governed where applicable |
| D4-C | bounded delivery/recovery profile covering ack, quarantine/redrive, bounds, equivalence, outbox, producer generation, replay/history, readers/upcasters and recovery reconciliation | production retry, retention, replay, quarantine, recovery and capacity numerics remain C3/later authority |
| D4-D | derived short-lived broker credentials, broker ACL projection, KMS-backed protection profile, reference-only secret authority and bounded W3C trace context | provider/vendor/crypto/topology numerics and Product authority remain outside this acceptance |

Acceptance makes these the accepted D4 C2 dispositions. It does not make provider-native semantics canonical domain authority and does not make any implementation irreversible.

## Explicit non-authority boundary

This D4 acceptance does **not** grant or imply:

- D4 transport implementation authority;
- canonical Product implementation authority;
- Wave 4 Monitoring implementation authority;
- production deployment authority;
- C3 numeric/topology authority;
- production partition counts, retry/backoff/jitter, retention, replay/quarantine horizons, recovery/capacity targets, or realtime session/buffer numerics;
- provider-native identity, authorization, schema/catalog, topology, secret, KMS or tracing semantics as platform authority;
- activation of Alerting, ITSM, Automation, AIOps, FinOps or Commercial behavior.

The machine-owned authority fields remain exactly:

```text
d4_transport_authority = selected_not_granted
canonical_product_implementation_authority = not_granted
wave4_implementation_authority = not_granted
production_authority = none
c3_numeric_topology_authority = not_selected
```

## Historical immutability

Historical D4 source-evidence manifests, candidate-evaluation plans and promotion records remain source-time truth. This acceptance supersedes only stale **current operational status statements** that say D4 is scoped/unaccepted or a selected D4 track is not yet accepted.

Historical records that correctly state `not_selected`, `selected_candidate`, source-time credit counts, or source-time non-authority remain unchanged and must be projected as historical state by validators rather than rewritten.

## Assurance requirements for this acceptance PR

This transition is valid only if the final exact HEAD proves all of the following:

1. D4 remains exactly 26/26 required/completed evidence with zero remaining evidence;
2. the four candidate/profile identities and candidate-status values are unchanged;
3. all four track states are `accepted_candidate` and `gate_state` is `separately_accepted`;
4. `d4_transport_authority` remains `selected_not_granted`;
5. Product, Wave 4, production and C3 authorities remain blocked exactly as before;
6. source-evidence and historical candidate/promotion records remain immutable source-time truth;
7. Deterministic Assurance and every applicable D4 workflow are green on the exact final HEAD;
8. all material review findings are resolved and internalized where required;
9. merge occurs only after separate explicit user authorization.

## Advancement boundary

After this D4 acceptance is merged, the repository may proceed only to the next explicitly governed readiness/implementation-authority transition.

```text
D4_SEPARATELY_ACCEPTED
  -> next governed architecture/readiness transition
  -> explicit implementation authority where applicable
  -> implementation
```

D4 acceptance by itself does not authorize transport runtime implementation, Wave 4, Product implementation or production deployment. No CI result, selected technology, provider capability, framework choice or AI output may skip those later authority transitions.
