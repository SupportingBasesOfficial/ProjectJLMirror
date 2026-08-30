# D2 / OPEN-REL-030 Evidence State

**State:** TRACK B ACCEPTED — post-acceptance exact-head assurance mandatory  
**Evidence:** complete  
**Decision disposition:** `accepted_track_b`  
**Track B acceptance authorization:** granted by explicit user authorization  
**Closure claim:** false — closure remains a separate authorization  
**Wave 4 implementation authorization:** not granted  
**Production authority:** none  
**Production versions/numerics:** not selected; capacity envelopes remain `OPEN-REL-020` C3  
**Merge authorization:** not granted

## Acceptance authorization basis

Track B was explicitly authorized only after the prior exact stationary HEAD passed every required decision gate:

```text
Authorized-from HEAD          622c094c9274a778d1c21c5976dd3b2ca7b4cedf
Deterministic Assurance      #2273 / 33283807517 / SUCCESS
OPEN-REL-030 Conformance     #204 / 33283807551 / SUCCESS
Native Assurance             review 5059581679 / P0=0 P1=0 P2=0
Fresh Codex exact-head       comment 5465822591 / CLEAN — no major issues
Inline review threads        0 unresolved
PR mergeable                 true
```

The acceptance mutation itself changes HEAD. Therefore the accepted-state commit must independently pass deterministic assurance, OPEN-REL-030 conformance, Native Assurance and a fresh adversarial Codex review before it is considered exact-head assured for merge-readiness purposes.

## Accepted Track B profile

The accepted C2 mechanism/profile is the coupled invariant set already proven by the evidence package. Acceptance does not weaken or split those guarantees.

### Tier 1 / owner-current history

- immutable canonical observation identity/content;
- owner-controlled source generation, poll epoch and durable live poll claim inside transactional acceptance;
- platform ordering authority for current-state CAS;
- reconciliation coverage contiguous from `supported_history_floor`, bound to exact authority generation, provider dataset revision and owner-required snapshot currentness;
- provider mutation invalidates current coverage; stable identity rewrite, DELETE and TRUNCATE fail closed;
- accepted stable identities are validated independently of current `became_visible_at`;
- retained `finalized_through` cannot be re-advertised as current completeness until current-revision coverage again reaches it;
- `try_finalize(..., NULL)` fails closed with SQLSTATE `22004`;
- provider mutation, sweep and finalization use the canonical lock order `provider_authority → stream_state`;
- worker paths cannot bypass the lock-order wrappers;
- all seven history hardening modules `004–010` are ordered, executed and anti-orphan guarded.

### Physical PITR / recovery authority

- surviving recovery authority is external to restored PostgreSQL state;
- PGDATA copying alone cannot duplicate effective restored-instance authority;
- clone negatives require same-path positive control;
- one winner exists per canonical recovery boundary across equivalent grant IDs;
- grants bind authenticated surviving post-R effect evidence;
- claim alone leaves local truth at R; verified material is required for atomic effect/successor application;
- material fetch uses locked, revalidated active-authority/grant/claim/effect/signing state;
- validly signed successor epoch/placement drift fails closed;
- hardened positive claim→verify→fetch/apply→verify is exercised after hardening installation;
- recovery and clone calls use caller-local async response deadlines, real established TCP blackhole tests and one-shot session retirement without synchronous timeout cleanup.

### Tier 2 / relocation

- only the mediated shared-history Timescale profile is accepted by Track B;
- tenant/application principals have no direct shared raw/CAGG/internal-materialization authority;
- `ts_automation_owner` remains privileged cross-tenant infrastructure;
- fresh-cluster role reconstruction and post-restore/job attack matrices remain mandatory;
- timestamp/numeric canonicalization is total and injective over the evaluated domains;
- target checkpoint mint authority is target-side; Tier 1 verifies but cannot mint;
- verifier capability state remains restricted;
- effective verifier transport uses caller-local async deadlines, no synchronous timeout cleanup and real blackholes in both directions;
- source is locked before F; target completeness is canonical-set completeness;
- Tier 1 placement + activation grant commit atomically;
- target activation requires the exact committed Tier 1 grant.

## Evidence provenance

Empirical mechanism anchor before the #51 governance promotion:

```text
51cddbca4258a78ed8f4a3254ff54a01a332e933
Deterministic Assurance #2261 — run 33283602526 — SUCCESS
OPEN-REL-030 Conformance #198 — run 33283602532 — SUCCESS
```

The prior final decision-review HEAD `622c094c9274a778d1c21c5976dd3b2ca7b4cedf` then passed #2273/#204, Native P0/P1/P2=0 and fresh Codex CLEAN, establishing the basis for the explicit Track B authorization.

## Material findings

All **51 material finding classes** remain closed/documented by the accepted mechanism. The latest classes are:

- **#49:** retained finalized watermark stale resurrection — current-revision coverage must revalidate through the retained watermark before `complete` can return.
- **#50:** NULL finalization cutoff — SQLSTATE `22004` rejection prevents three-valued logic from minting completeness.
- **#51:** inconsistent history authority lock order — mutation, sweep and finalization now acquire `provider_authority → stream_state`; concurrent deadlock vectors are required.

Classes #1–#48 remain enumerated in `DECISION_REVIEW.md` and are not superseded by acceptance.

## Authorization boundary

```text
Evidence package             COMPLETE
Track B decision             ACCEPTED
Track B authorization        GRANTED
Closure claim                FALSE / NOT AUTHORIZED
Wave 4 implementation        NOT AUTHORIZED
Production authority         NONE
Production selections        NOT MADE
Merge                        NOT AUTHORIZED
Post-acceptance exact-head   CI + Native + fresh Codex REQUIRED
```

Track B acceptance selects the bounded C2 mechanism/profile as the accepted decision outcome. It does **not** authorize Wave 4 implementation, production deployment, production topology/numerics, closure of the OPEN, or merge.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
