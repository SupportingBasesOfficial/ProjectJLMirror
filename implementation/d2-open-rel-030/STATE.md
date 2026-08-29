# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR EXACT-HEAD DECISION REVIEW  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted  
**Production versions/numerics:** not selected; capacity envelopes remain `OPEN-REL-020` C3

## Current recommendation

Recommend C2 acceptance only if the complete invariant set below remains preserved together.

### Tier 1 — transactional and history authority

- canonical observation identity/content is immutable;
- active source generation, poll epoch and durable `live` poll claim come from owner-controlled state inside the acceptance transaction;
- current-state CAS is based on platform authority, never provider event time;
- late-history coverage is contiguous from `supported_history_floor` and bound to exact owner `authority_generation`, `provider_dataset_revision` and required snapshot currentness;
- owner-visible provider mutation invalidates prior coverage atomically; stable identity rewrite, DELETE and TRUNCATE fail closed;
- accepted stable identities are compared with owner-current canonical content before coverage publication whenever either side intersects the requested window, independently of current `became_visible_at`;
- every current `00[4-9]_history_*.sql` hardening module is executed by the extended runner and structurally guarded against orphaning.

### Physical PITR recovery authority

Recovery admission is not a bearer-grant check and not a local-receipt check. It is a surviving, authenticated, effect-bound, boundary-single-winner authority:

1. the source reaches committed `R`;
2. a real `(R,F]` business effect occurs and committed `F` is established;
3. surviving authority, outside the restored database, stores canonical authenticated effect evidence derived from the actual post-R source state;
4. each recovery grant is cryptographically bound to that exact effect digest;
5. all grant IDs representing the same governed recovery boundary map to one canonical `boundary_fingerprint` and one atomic `recovery_boundary_claim`;
6. the winner is bound to authenticated `session_user + restored-instance id + instance-proof fingerprint`;
7. same-instance retry converges, while another physical restore/clone cannot become a second winner by reusing credentials or switching grant IDs;
8. claim alone leaves the restored database at `R`; only verified recovery material can atomically apply the authenticated post-R effect and successor authority;
9. claim, verify and recovery-material fetch use caller-local bounded asynchronous transport; `connect_timeout` covers setup only, and an authenticated stalled peer fails closed under the local response deadline;
10. a locally recreated continuity receipt remains non-authoritative.

Post-enrollment clone hardening remains separately required:

- effective restored-instance proof is outside the `PGDATA` clone domain in the C2 evidence mechanism;
- a physical PGDATA copy after enrollment retains the same database-visible identity but does not inherit effective authority;
- the clone-rejection negative is valid only after a same-path positive control proves the clone capability/helper/credential/transport path operational and binds the surviving-authority fingerprint to the clone-local capability fingerprint.

The evidence-only file/mount capability, LOGIN roles and `dblink` transport are **not** production identity/RPC/secret-store selections. Production must preserve the stronger non-shareable per-instance and surviving-effect authority properties through separately governed mechanisms.

### Tier 2 / relocation

- Timescale shared history remains acceptable only under the mediated profile: no direct tenant access to shared raw history/CAGG/internal materialization; fixed-search-path mediation; privileged automation owner explicitly isolated from tenant/application principals;
- typed canonicalization is total/injective across evaluated `timestamptz` and `numeric` domains;
- target checkpoint measurement/signing authority originates inside Tier 2; Tier 1 verifies but cannot mint;
- cross-authority verifier credentials remain restricted and absent from function source;
- verifier calls are bounded/fail-closed before local authority locks;
- source placement is locked before `F`; target completeness is canonical-set completeness, never max-only;
- Tier 1 placement transition + exact activation grant commit atomically;
- target remains `sealed` until it verifies that committed Tier 1 grant; after activation existing history remains immutable and only new append `>F` is eligible.

## Exact empirical anchor before this governance mutation

```text
HEAD
6f46c6700855207ad85fc206e258da00ce896c8b

JLMIRROR Deterministic Assurance
run #2207
run id 33274303103
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #171
run id 33274303155
SUCCESS
```

This anchor closes the recovery-boundary/effect/deadline findings while preserving all prior Tier1/history, post-enrollment clone, Timescale, canonicalization and relocation vectors. It is provenance only after this governance mutation; the exact final documentation HEAD must independently rerun both gates.

Representative #171 recovery markers:

```text
physical_pitr_surviving_effect_source_state=PASS
physical_pitr_surviving_effect_evidence_published=PASS
physical_pitr_duplicate_grants_same_boundary=PASS
physical_pitr_recovery_helpers_use_bounded_transport=PASS
physical_pitr_recovery_stalled_peer_fails_closed=PASS
physical_pitr_recovery_local_deadline=PASS
physical_pitr_recovery_cross_grant_boundary_single_winner_race=PASS
physical_pitr_recovery_single_winner_per_boundary_across_grant_ids=PASS
physical_pitr_recovery_effect_digest_binding=PASS
physical_pitr_claim_without_effect_application_stays_at_R=PASS
physical_pitr_authenticated_effect_application=PASS
physical_pitr_reconciled_from_authenticated_surviving_effect=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_effect_bound_boundary_single_winner_instance_capability
physical_pitr_rf_reconciliation=PASS
```

The exact same run also preserves the post-enrollment positive-control/clone negatives, all five history hardening modules (`004–008`), fresh-cluster Timescale restore/jobs, canonical typed-value vectors and Tier1↔Tier2 relocation continuity.

## Material classes #38–#42

- **#38 — post-enrollment PGDATA clone authority:** a database-resident instance secret was copyable with PGDATA. Closed by moving the effective C2 proof outside the physical database clone domain and proving the copied database identity cannot duplicate authority.
- **#39 — false-negative clone evidence:** fail-closed helper/transport failure could masquerade as capability rejection. Closed by a same-path clone positive control before the governed negative.
- **#40 — grant-id scoped single winner:** different grant IDs for one recovery event could create multiple winners. Closed by a canonical recovery-boundary fingerprint and atomic one-row boundary claim across grant IDs, including a real cross-grant race.
- **#41 — unauthenticated post-R reconciliation:** a restored database could recreate a receipt and mark reconciliation without applying the committed post-R effect. Closed by authenticated surviving effect evidence, grant→effect-digest binding, and local state mutation only from verified recovery material.
- **#42 — unbounded physical-recovery verifier response:** synchronous `dblink` could hang after connection establishment. Closed by asynchronous polling, caller-local deadline, cancellation/disconnect and fail-closed semantics for claim/verify/material-fetch.

## Acceptance boundary

```text
Evidence package             COMPLETE
Executable empirical anchor  6f46c6700855207ad85fc206e258da00ce896c8b / #2207 / #171
Material finding classes     42
Inline review threads        0 unresolved at anchor review
Exact-final-HEAD CI          REQUIRED AGAIN AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Production authority         NONE
Merge                        NOT AUTHORIZED
```

Evidence completion, CI success, mergeability or reviewer cleanliness do not themselves accept `OPEN-REL-030`, authorize Wave 4, select production topology/numerics, or authorize merge. `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
