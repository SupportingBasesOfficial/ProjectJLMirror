# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR DECISION REVIEW  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted  
**Track B acceptance authorization:** not granted  
**Production versions/numerics:** not selected; capacity envelopes remain `OPEN-REL-020` C3

## Current recommendation

### Tier 1 — PostgreSQL transactional authority

Recommend C2 acceptance only with all of the following preserved together:

- immutable canonical observation identity/content;
- active source generation and poll epoch resolved from owner-controlled state inside the acceptance transaction;
- exact durable `live` poll claim for current candidacy;
- current-state CAS by platform source/poll authority, never provider event time;
- contiguous late-history reconciliation anchored at `supported_history_floor`;
- provider snapshot/finality/currentness derived from durable owner authority, not worker-supplied timestamps;
- reconciliation coverage bound to the exact current `authority_generation`, even when snapshot timestamps are unchanged;
- every authority-generation transition invalidates prior materialized coverage until a fresh sweep under the new generation re-establishes it;
- conflicting canonical content under an existing reconciled observation identity rejects the sweep before a new coverage run can be recorded;
- stale reconciliation worker generations rejected;
- physical PITR to committed `R` remaining fail-closed until a surviving external authenticated `(R,F]` recovery grant is verified;
- recovery grant facts stored structurally and authenticated over a deterministic self-delimiting canonical representation;
- a locally recreated receipt after restore is insufficient for re-admission;
- source relocation authority locked before deriving `F`;
- source↔target payload comparison and checkpoint attestation using deterministic self-delimiting canonical serialization;
- target checkpoint authenticity verified through a target-owned verification boundary while Tier 1 has no target signing key and no mint capability;
- verifier transport credentials held in authority-owned restricted capability stores rather than embedded in function source;
- the exact relocation activation grant and the Tier 1 placement transition committed atomically, so neither can survive without the other.

### Tier 2 — Timescale mediated shared history

Recommend C2 acceptance only under the conformed mediated profile:

- no direct tenant-facing privilege on shared raw history, CAGG or internal materialization;
- fixed-search-path `SECURITY DEFINER` mediation with tenant binding outside caller-writable SQL state;
- `ts_owner` NOLOGIN mediation/checkpoint authority;
- `ts_automation_owner` LOGIN only as explicit cross-tenant privileged infrastructure, never as an application/tenant principal;
- `PASSWORD NULL` is not treated as `NOLOGIN` or production admission proof;
- fresh-cluster role reconstruction + attack matrix after restore/jobs;
- target-owned authenticated sealed relocation checkpoint over the actual target canonical payload;
- the effective checkpoint signing key is generated inside Tier 2 target authority and is not provisioned or retained by the test controller;
- verifier and projection-writer principals cannot read that signing key;
- target/Tier1 verifier connection capabilities are restricted authority-owned state and are not readable by verifier/automation principals;
- verifier secrets are not embedded in `pg_proc` function source;
- no target row `>F` may survive or enter before activation;
- `sealed` rejects all target-history DML;
- `sealed → activated` requires successful verification of the exact durable Tier 1 activation grant bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version;
- after `activated`, existing history is immutable and only append `>F` is eligible.

## Exact empirical anchor before this reviewer-document mutation

```text
HEAD
387a68af2eb896f0ece8c916b241a84fde0876f3

JLMIRROR Deterministic Assurance
run #2068
run id 33226943467
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #102
run id 33226943414
SUCCESS
```

That SHA is provenance only after this documentation update. The exact final documentation HEAD must rerun both gates.

## Owner-currentness history gate

The history worker does not provide authority, finality or currentness facts. Durable `provider_authority` owns `authority_generation`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. `sweep(...)` accepts only the requested window plus `expected_authority_generation`; `try_finalize(...)` accepts no caller authority/finality/currentness timestamp.

Coverage is now a function of **both** the exact owner generation and the required owner snapshot. `contiguous_covered_through(...)` filters `reconciliation_run` by `authority_generation = current authority_generation`; `advance_provider_authority(...)` clears materialized coverage and moves non-gap streams to `reconciliation_required` even if all timestamps remain identical. This prevents an authority correction/revision from reusing stale coverage simply because its timestamp did not move.

An existing `(stream_id, observation_id)` is also immutable canonical history. Before inserting or recording a reconciliation run, `sweep(...)` compares owner-visible `observed_at` and `numeric_value` against the persisted accepted row; mismatch raises `reconciled observation identity content mismatch`. The failed sweep records no new run and leaves accepted canonical content unchanged.

Exact #102 proves:

```text
history_conflicting_observation_rejected=PASS
history_generation_bound_coverage=PASS
history_owner_currentness_authority=PASS
late_history_reconciliation=PASS
```

The same run preserves continuous coverage from the supported floor and durable `gap` on unrecoverable retention loss.

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt. A separate surviving control database, excluded from the source backup/restore, owns the recovery signing key and issues a grant after `F`. The structured grant facts are individually self-delimiting before HMAC-SHA-256. The matrix proves local self-mint cannot admit, tampering rejects, surviving authority verifies the exact grant, and authenticated successor facts can be applied without replaying rollback-subject business state.

## Canonical structured-message gate

Every structured cryptographic evidence message must use deterministic, versioned, injective or equivalently unambiguous serialization before hash/MAC/signature. The bounded evidence representation is `<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>`, used for observation payloads, target-checkpoint facts and PITR recovery-grant facts. An accepted implementation may use another canonical representation only with equivalent independently reviewed evidence.

## Relocation target and issuer/verifier gate

The target checkpoint is bound to target-owned measurement of actual current state, count/max/SHA-256 over canonical immutable payload, and domain-separated HMAC over the canonical checkpoint message. The effective signing key is generated inside target authority using target-side randomness. The trusted disposable-lab controller can administer both databases for setup/fault injection, but it neither provisions nor retains the protocol signing key.

Exact #102 continues to prove:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_controller_does_not_retain_target_signing_key=PASS
relocation_target_authority_generated_signing_key=PASS
relocation_projection_writer_still_cannot_read_generated_signing_key=PASS
relocation_target_verifier_still_cannot_read_generated_signing_key=PASS
relocation_tier1_verifier_cannot_read_target_connection_capability=PASS
relocation_projection_writer_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_secret_not_in_function_source=PASS
relocation_tier1_verifier_secret_not_in_function_source=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_fabricated_target_attestation_rejected=PASS
```

Thus the evidence separates issuer from verifier at the database-authority and key-provenance levels, not merely by table naming.

## Cross-authority activation gate

The target checkpoint verifier and Tier 1 activation verifier are capability-restricted yes/no interfaces. The evidence uses short-lived random verifier credentials plus PostgreSQL `dblink` only to exercise independent authorities. Those credentials live in restricted authority-owned capability tables and are not embedded in verifier function source. This concrete transport/auth mechanism remains C2 laboratory machinery and does not select production database-authentication, network, secret-distribution or RPC topology.

Remote verification is bounded/fail-closed and happens before local authority locks. Tier 1 then atomically commits successor placement plus a durable activation grant. Target remains `sealed` until it verifies the exact committed grant.

Exact #102 also preserves:

```text
relocation_target_cannot_self_activate_before_tier1_grant=PASS
relocation_premature_mark_keeps_future_insert_blocked=PASS
relocation_activation_commit_conflict_rolls_back=PASS
relocation_activation_conflict_preserves_fenced_placement=PASS
relocation_conflicting_grant_cannot_activate_target=PASS
relocation_activation_conflict_keeps_target_sealed=PASS
relocation_activation_grant_placement_atomicity=PASS
relocation_tier1_activation_grant_committed=PASS
open_rel_030_extended_conformance=PASS
```

## Tier 2 trust boundary

`ts_automation_owner` remains a LOGIN cross-tenant privileged infrastructure principal because the evaluated Timescale background-job profile requires it. Production must prevent tenant/application principals from authenticating as or assuming this owner through `pg_hba`, local socket/peer/trust behavior, network exposure, role membership or credential provisioning. Widening that boundary invalidates the conformed profile until fresh review/evidence.

## Acceptance boundary

Evidence completion does not accept `OPEN-REL-030`.

```text
Evidence package             COMPLETE
Exact-final-HEAD CI          REQUIRED AGAIN AFTER DOC MUTATION
Codex exact-final-HEAD       REQUIRED
Native Assurance             REQUIRED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED
```

Only after exact-final-HEAD CI + adversarial review + Native Assurance are clean may Track B be presented for explicit acceptance. Acceptance still does not authorize Wave 4 implementation or production deployment.
