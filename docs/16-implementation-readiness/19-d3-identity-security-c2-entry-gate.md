# D3 — Identity, Security & Authority C2 Entry Gate

**Status:** scoped evidence gate — no canonical Product implementation authority is granted by this record  
**Canonical base:** `main@b70d0c20873f92ca0a6040a3cbcd1dfcdace6828`  
**Predecessor:** D2 / `OPEN-REL-030` Track B accepted and post-D2 readiness propagation merged  
**Next gate after D3 acceptance:** D4 Eventing & Asynchronous Transport C2; D3 SHALL NOT select or authorize D4 transport products

## Purpose

D3 closes the remaining **Identity/Security mechanism decisions needed to make the already-accepted authority model executable without turning current products into permanent architecture**.

The fixed semantic authority remains in ADRs, Phase 09/11/13 contracts, IR-D-001/002/003 and accepted Wave 1 substrate. D3 may select replaceable mechanisms only when bounded evidence proves those mechanisms preserve the existing semantics.

D3 is not Wave 4 authorization, not production authority and not a license to add Product/domain behavior.

```text
EVIDENCE_ELIGIBLE != CANONICAL_PRODUCT_IMPLEMENTATION_AUTHORIZED
D3_ACCEPTED != WAVE4_AUTHORIZED
D3_ACCEPTED != PRODUCTION_AUTHORIZED
D3 != D4
```

## Fixed invariants D3 cannot change

- browser authentication uses OIDC Authorization Code + PKCE S256 through the confidential BFF;
- browser JavaScript never receives platform refresh tokens or long-lived platform access credentials;
- an opaque server-side BFF session handle is the browser session capability;
- token validity never substitutes for current membership, permission, tenant, placement or authentication-strength authority;
- IdP-native user/group/organization identity never becomes JLMirror membership/authorization truth;
- security-authority uncertainty fails closed;
- forced logout, permission revocation, tenant suspension and credential retirement cannot be masked by stale positive cache state;
- broad revocation is O(1) or bounded-constant relative to active-session count;
- security cache is derived acceleration state and never business truth;
- external machine authentication retains attributable asymmetric `private_key_jwt` identity and shared atomic replay protection;
- internal workload identity remains SPIFFE-compatible URI identity + short-lived X.509-SVID-compatible credential + mTLS peer authentication;
- workload identity authenticates a workload only; it never grants tenant/business authority;
- CSRF protection remains explicit; SameSite alone is insufficient;
- machine/security replay continuity survives partition/restore or fails closed;
- cryptographic comparison/replay evidence remains tenant/scope domain-separated, generation-bound and recovery-aware;
- D3 cannot select broker/event transport, event serialization, partition topology, ack/lease, quarantine, outbox transport or other D4 mechanisms.

## D3 bounded tracks

### D3-A — Human IdP mechanism

**Source authority:** `IR-D-001-keycloak-idp-decision-record.md`, IR-D-001, ADR-005, ADR-017.  
**Current candidate:** Keycloak.  
**Current state:** mechanism candidate selected; C2 closure incomplete.

D3-A evidence SHALL prove at minimum:

- Authorization Code + PKCE S256 + BFF confidential-client flow with exact state/nonce/session transaction binding;
- issuer/audience/client/time/JWKS/algorithm validation and explicit rejection of untrusted algorithm/key indirection;
- trusted `acr`/`amr` propagation for MFA/step-up policy;
- OIDC Back-Channel Logout authenticity, event profile validation and durable replay identity `(issuer, client, jti)`;
- provider `sid`/`sub` mapping to platform session/principal authority without making provider identity platform identity;
- principal-wide/forced logout via generation/fence semantics rather than active-session enumeration;
- IdP outage behavior: existing sessions only continue when current local JLMirror authorities can still be established; new login and step-up fail closed;
- Keycloak groups/roles/Organizations cannot become JLMirror authorization truth.

Keycloak acceptance would select an **adapter-backed IdP mechanism**, not make Keycloak semantics part of the domain model.

### D3-B — BFF session authority + security acceleration cache

**Source authority:** `OPEN-REL-031.A`, `OPEN-REL-015`, the mechanism portion of `OPEN-REL-008.A` only where required by this security-session profile, ADR-005/012/017.  
**Current candidates:** PostgreSQL Identity/session system of record + Redis security acceleration cache.  
**Current state:** combined C2 mechanism incomplete.

D3-B evidence SHALL prove at minimum:

- PostgreSQL owns only Identity/BFF-session durable truth; Membership, Authorization Policy and tenant-lifecycle truth remain with their existing owners;
- Redis contains only derived generation-bound acceleration evidence;
- healthy cache-hit admission uses a bounded single Redis network round trip and zero PostgreSQL generation queries while still proving a coherent current read set;
- a stale mixed-generation read cannot be admitted as current;
- positive Redis state cannot self-certify the admission epoch/generation from the same stale dataset;
- revocation/deny commits cannot be masked by stale positive cache data;
- prepare/fence/source-commit/finalize cleanup has a durable single winner and no sleeping-writer resurrection;
- local Redis failure cannot allow a source commit while another BFF may still trust the old positive generation;
- cache exclusion/re-entry has a fleet-wide admission barrier independent of the Redis contents being judged;
- restore/failover/replica promotion cannot resurrect positive cache authority;
- broad revocation is O(1) or bounded-constant relative to active sessions;
- degraded durable-owner reads are bulkheaded and fail closed when current owner evidence cannot safely be established.

`OPEN-REL-031.B`, `OPEN-REL-008.B` and production convergence/RPO/RTO numerics remain C3 and SHALL NOT be closed by D3.

### D3-C — Browser CSRF and key-rotation mechanism

**Source authority:** `OPEN-API-002-csrf-decision-record.md`, ADR-005, ADR-015, Phase 09 canonical HTTP/browser contracts.  
**Current candidate:** HMAC double-submit token bound to renewal-stable session lineage with versioned keys.  
**Current state:** mechanism selected; key-rotation closure evidence incomplete.

D3-C evidence SHALL prove at minimum:

- token construction binds accepted key version to session lineage and cannot be replayed across unrelated session lineages;
- exactly current + previous validation-key generations are admitted by the selected profile;
- rotation overlap is at least the accepted session/token safety lifetime used by the evidence profile;
- no arbitrary historical-key search is performed;
- previous-key usage is observable and stale use beyond the overlap is detectable;
- duplicate/conflicting CSRF cookie/header presentation fails identically at ingress and BFF canonicalization boundaries;
- routine session renewal does not invalidate CSRF state;
- fixation-resistance rotation/step-up synchronously rotates/reissues the CSRF binding as required;
- compromise/uncertain key generation fails closed.

D3 may use bounded non-production timing values to execute evidence. Final production timing/numeric policy remains separately governed.

### D3-D — Workload identity issuer / attestation backend

**Source authority:** `OPEN-PRT-008.B`, IR-D-002, ADR-015/016.  
**Current candidate:** not yet canonically selected; candidate evaluation SHALL use the SPIFFE/X.509-SVID/mTLS contract rather than product-native identity semantics.  
**Current state:** C2 open.

D3-D evidence SHALL prove at minimum:

- runtime evidence, not caller-selected strings, authorizes workload identity issuance;
- exact trust-domain/environment/runtime-profile binding;
- short-lived credential rotation and stale/retired trust-bundle rejection;
- cross-environment identity rejection;
- workload certificate success does not grant tenant/domain permission;
- private-key handling meets the selected runtime's non-exportability/secret-authority profile where supported;
- issuer/attestation outage and restore cannot silently recreate retired authority;
- a narrow adapter can derive short-lived vendor credentials without making vendor identity canonical.

D3-D selects an issuer/attestation backend only after evidence. It SHALL remain replaceable behind the accepted workload-identity port.

### D3-E — Cryptographic key / replay / historical-verifier authority

**Source authority:** `OPEN-REL-016.A`, IR-D-001 external-machine replay requirements, ADR-015, Phase 11 keyed message-equivalence security requirements; the comparison-representation portion joined to `OPEN-EVT-011` is included only for cryptographic authority continuity.  
**Explicit exclusion:** D3-E does **not** select event transport, event serialization, broker topology, delivery/ack or D4 async behavior.  
**Current candidate:** HMAC/HKDF profile with provider-neutral KMS/secret-key authority; concrete backend not yet canonically accepted.  
**Current state:** C2 mechanism incomplete.

D3-E evidence SHALL prove at minimum:

- HMAC comparison keys are cryptographically domain-separated per `(tenant, message_identity_scope)`;
- key derivation/granularity is no coarser than the governed erasure unit, or a separately accepted erasure design proves why a coarser key is safe;
- historical verifier generation continuity survives relocation/recovery without becoming current signing authority;
- recovery cannot restore an erased/retired usable key path;
- external-machine `private_key_jwt` assertion replay admission is atomic single-winner across replicas for the accepted bounded evidence window;
- replay authority partition/unavailability fails closed;
- restore/loss cannot convert a previously consumed still-relevant assertion into unused state;
- key/credential generation rotation and retirement are explicit and testable;
- application code consumes a provider-neutral key-authority port so backend replacement does not change domain/session/event semantics.

`OPEN-REL-016.B` rotation/lease numeric horizons remain C3. D4 remains owner of event-transport C2 decisions.

## D3 state machine

```text
scoped
  -> candidate_evidence_running
  -> per_track_conformed
  -> d3_acceptance_eligible
  -> separately_accepted
```

A track cannot enter `per_track_conformed` from documentation alone. It requires executable/falsifiable evidence against the exact candidate mechanism or a faithful cryptographic/runtime boundary where the product is intentionally still replaceable.

D3 acceptance requires all five tracks to have an explicit terminal C2 disposition:

```text
accepted_candidate
or
explicitly_deferred_to_later_gate_with_proof_that_it_does_not_block_D3
```

For this D3 scope, silently deferring D3-A, D3-B, D3-C or the replay-authority portion of D3-E is prohibited because they directly affect protected browser/machine authority. D3-D and the historical-verifier backend portion of D3-E may be accepted only when their exact dependency gate and non-blocking boundary are proven, not assumed.

## Evidence engineering rules

- candidate product/version/configuration is evidence input, never domain authority;
- every evidence harness is pinned/reproducible and executes on the exact reviewed HEAD;
- synthetic happy-path tests are insufficient where the closure record calls for partition, crash, concurrent-winner, restore, relocation, revocation or stale-reader evidence;
- every accepted failure path has a forbidden-outcome assertion, not only an expected success assertion;
- no test may pass merely because a dependency was unavailable or a branch was skipped;
- negative controls SHALL prove that the harness itself detects the failure it claims to exclude;
- evidence must preserve the already-accepted Waves 1–3 substrate and cannot rewrite its semantics to fit a candidate product;
- any candidate-specific concept crossing an adapter into canonical domain/authority identity is a D3 blocker.

## Explicit non-authority

This gate does not authorize:

- canonical Monitoring/Wave 4 Product code;
- production deployment;
- production C3 numeric/topology choices;
- D4 broker/event transport selection;
- realtime, outbound webhook, public SDK, Alerting, ITSM or AIOps activation;
- Keycloak/Redis/PostgreSQL or any D3 candidate as an irreversible architecture dependency merely because an evidence harness exists.

## Exit criteria

D3 can be proposed for acceptance only when:

1. the machine-readable D3 state manifest names every track/source OPEN and has no ambiguous owner;
2. every D3-A..E blocker is either conformed or explicitly classified by a reviewed non-blocking dependency rule;
3. exact-head deterministic assurance and all D3 conformance jobs are green;
4. all P0/P1/P2 review findings are resolved on the exact final HEAD;
5. Native Assurance and a fresh Codex adversarial review are clean on that same HEAD;
6. D4, Wave 4 and production authority remain explicitly ungranted;
7. acceptance and merge remain separate explicit user-authorized actions.
