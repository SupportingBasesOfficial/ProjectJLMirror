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
- stale reconciliation worker generations rejected;
- physical PITR to committed `R` remaining fail-closed until a **surviving external authenticated `(R,F]` recovery grant** is verified;
- recovery grant facts stored structurally and authenticated over a deterministic self-delimiting canonical representation, never reinterpreted through delimiter splitting;
- a locally recreated receipt after restore is insufficient for re-admission;
- source relocation authority locked before deriving `F`;
- relocation/source↔target payload comparison and checkpoint attestation using deterministic self-delimiting canonical serialization.

### Tier 2 — Timescale mediated shared history

Recommend C2 acceptance only under the conformed mediated profile:

- no direct tenant-facing privilege on shared raw history, CAGG or internal materialization;
- fixed-search-path `SECURITY DEFINER` mediation with tenant binding outside caller-writable SQL state;
- `ts_owner` NOLOGIN mediation/checkpoint authority;
- `ts_automation_owner` LOGIN only as explicit **cross-tenant privileged infrastructure**, never as an application/tenant principal;
- `PASSWORD NULL` is not treated as `NOLOGIN` or production admission proof;
- fresh-cluster role reconstruction + attack matrix after restore/jobs;
- target-owned authenticated sealed relocation checkpoint over the actual target canonical payload;
- the HMAC checkpoint payload itself uses the same deterministic self-delimiting canonical field representation on issuer and verifier;
- no target row `>F` may survive or enter before activation;
- `sealed` rejects all target-history DML; after `activated`, existing history is immutable and only append `>F` is eligible.

## Exact empirical anchor before this reviewer-document mutation

```text
HEAD
3ffc96073b54fe7a8b5d002523733947ee59ba57

JLMIRROR Deterministic Assurance
run #2012
run id 33208029855
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #74
run id 33208029866
SUCCESS
```

That SHA is **provenance only** after this documentation update. The exact final documentation HEAD must rerun both gates.

## Owner-currentness history gate

The history worker does not provide finality/currentness timestamps.

Durable `provider_authority` owns:

- `authority_generation`;
- `current_snapshot_at`;
- `finality_floor`;
- `required_reconciliation_snapshot_at`.

`sweep(...)` accepts only the requested window plus `expected_authority_generation`; it locks and derives the actual snapshot from owner authority. `try_finalize(...)` accepts only stream + finalization boundary and locks finality/currentness from owner authority.

The evidence proves worker mutation of authority is unavailable, stale generation rejects, owner-required snapshot currentness is enforced, continuous coverage is anchored at the supported floor, and unrecoverable retention loss remains durable `gap`.

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt.

A separate surviving control database, excluded from the source backup/restore, holds a random HMAC key and issues a recovery grant **after `F`**. Neither source nor restored database contains that signing key.

The grant is stored as structured fields:

```text
domain
R
F
successor epoch
placement version
required receipt
nonce
canonical payload
attestation
```

Each signed field is canonicalized as:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

The fields are concatenated only after each field is self-delimiting. HMAC-SHA-256 covers this canonical payload. The shell reads the authoritative columns independently; it does **not** recover structured authority by splitting an authenticated text blob.

A dedicated negative proves that ordinary pipe framing can map different logical field boundaries to the same raw string while the canonical representation remains distinct. The positive path deliberately uses:

```text
required_receipt = effect|after-r
```

and still verifies correctly, proving that literal delimiter characters do not alter grant structure.

Negative evidence also proves:

- restoring exactly to `R` has no post-`R` receipt/grant metadata;
- locally reinserting the receipt still leaves admission false;
- tampering with one structured grant field while replaying the original attestation is rejected.

Positive evidence proves the surviving authority verifies the exact structured grant, authenticated successor facts are applied without replaying rollback-subject business state, and final admission requires both reconciled local state and fresh verification by the surviving external authority.

## Canonical structured-message gate

The D2 rule is broader than the observation digest:

> A hash/HMAC can authenticate only the bytes it receives. It cannot repair an ambiguous mapping from structured facts to those bytes.

Therefore **every structured cryptographic evidence message** must use deterministic, versioned, injective or equivalently unambiguous serialization before hashing/signing.

The bounded evidence representation is:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

It is used for:

1. immutable observation fields before the relocation SHA-256 digest;
2. all structured target-checkpoint facts before HMAC-SHA-256;
3. all structured PITR recovery-grant facts before HMAC-SHA-256.

The target checkpoint issuer in Timescale and verifier in PostgreSQL independently compute the same `canonical_checkpoint_payload`. Exact-head evidence includes:

```text
relocation_checkpoint_hmac_payload_cross_store=PASS
```

The PITR evidence includes:

```text
physical_pitr_grant_delimiter_collision_closed=PASS
physical_pitr_grant_receipt_contains_pipe=PASS
physical_pitr_tampered_external_grant_rejected=PASS
physical_pitr_external_grant_verified=PASS
```

The exact textual encoding is a bounded evidence choice, not an immutable production wire format. An accepted implementation may use CBOR/Protobuf/another canonical representation only if the same versioned unambiguous-structure property and all authority/integrity semantics are independently proven.

## Relocation target gate

Before seal, staging is allowed but any row `>F` blocks sealing. During `sealed`, all target-history DML is rejected. After `activated`, existing history remains immutable and only new append above `F` is eligible.

The checkpoint remains bound to:

- target-owned measurement of actual current state;
- count + max + SHA-256 over deterministic self-delimiting canonical immutable payload;
- domain-separated HMAC-SHA-256 over a deterministic self-delimiting `canonical_checkpoint_payload`;
- projection writer unable to read attestation key or disable freeze;
- Tier 1 verification of the authenticated sealed checkpoint before target activation.

## Tier 2 trust boundary

`ts_automation_owner` is explicitly a **LOGIN cross-tenant privileged infrastructure principal** because the evaluated Timescale background-job profile requires ownership by a login-capable role. Its evidence profile has no password credential, SUPERUSER, CREATEROLE or BYPASSRLS, and tenant/runtime roles have no membership in it.

However, `PASSWORD NULL` is not an authentication barrier. A production deployment must prevent tenant/application principals from authenticating as or assuming this owner through `pg_hba`, local socket/peer/trust behavior, network exposure, role membership or credential provisioning. Widening that boundary invalidates the conformed profile until fresh review/evidence.

## Acceptance boundary

Evidence completion does not accept `OPEN-REL-030`.

```text
Evidence package             COMPLETE
Exact-final-HEAD CI          REQUIRED AGAIN AFTER DOC MUTATION
Codex exact-final-HEAD       REQUIRED
Native Assurance             REQUIRED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Merge                         NOT AUTHORIZED
```

Only after exact-final-HEAD CI + adversarial review + Native Assurance are clean may Track B be presented for explicit acceptance. Acceptance still does not authorize Wave 4 implementation or production deployment.
