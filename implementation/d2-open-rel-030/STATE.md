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
- a locally recreated receipt after restore is insufficient for re-admission;
- source relocation authority locked before deriving `F`;
- relocation/source↔target payload comparison using deterministic **self-delimiting canonical serialization**, never delimiter-framed unrestricted text.

### Tier 2 — Timescale mediated shared history

Recommend C2 acceptance only under the conformed mediated profile:

- no direct tenant-facing privilege on shared raw history, CAGG or internal materialization;
- fixed-search-path `SECURITY DEFINER` mediation with tenant binding outside caller-writable SQL state;
- `ts_owner` NOLOGIN mediation/checkpoint authority;
- `ts_automation_owner` LOGIN only as explicit **cross-tenant privileged infrastructure**, never as an application/tenant principal;
- `PASSWORD NULL` is not treated as `NOLOGIN` or production admission proof;
- fresh-cluster role reconstruction + attack matrix after restore/jobs;
- target-owned authenticated sealed relocation checkpoint over the actual target canonical payload;
- the same deterministic self-delimiting canonical representation on both sides of the projection seam;
- no target row `>F` may survive or enter before activation;
- `sealed` rejects all target-history DML; after `activated`, existing history is immutable and only append `>F` is eligible.

## Exact empirical anchor before this reviewer-document mutation

```text
HEAD
cbd433f09a7568048a45b75cd9abb6760b5687d8

JLMIRROR Deterministic Assurance
run #2000
run id 33206933772
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #68
run id 33206933620
SUCCESS
```

That SHA is **provenance only** after this documentation update. The exact final documentation HEAD must rerun both gates.

## Owner-currentness history gate

The history worker no longer provides finality/currentness timestamps.

Durable `provider_authority` owns:

- `authority_generation`;
- `current_snapshot_at`;
- `finality_floor`;
- `required_reconciliation_snapshot_at`.

`sweep(...)` accepts only the requested window plus `expected_authority_generation`; it locks and derives the actual snapshot from owner authority. `try_finalize(...)` accepts only stream + finalization boundary and locks finality/currentness from owner authority.

The evidence proves:

- worker cannot execute the owner authority transition;
- stale expected generation is rejected;
- generation-2 coverage at snapshot `12:15` cannot satisfy generation-3 owner currentness `12:16`;
- a fresh generation-3 covering sweep is required before finalization;
- unrecoverable provider retention loss remains durable `gap`.

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt.

A separate surviving control database, excluded from the source backup/restore, holds a random HMAC key and issues a domain-separated recovery grant **after `F`**. Neither source nor restored database contains that signing key.

Negative evidence:

- restoring exactly to `R` has no post-`R` receipt/grant metadata;
- locally reinserting `effect-after-r` still leaves admission false;
- tampering with the external recovery-grant payload while replaying its attestation is rejected.

Positive evidence:

- the surviving authority verifies the exact grant;
- successor epoch/placement/receipt facts are taken from the authenticated external grant;
- rollback-subject post-`R` business state is not replayed;
- final admission requires both reconciled local state and fresh verification by the surviving external authority.

## Canonical serialization gate

Relocation equivalence is defined over an **unambiguous canonical byte representation**, not merely over a cryptographic hash function.

The evidence profile serializes every immutable field as:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

Rows are deterministically ordered and their self-delimiting fields are concatenated without using an in-band text delimiter as an authority boundary. The fields covered by the current evidence profile are:

- accepted ordinal;
- observation ID;
- metric definition ID;
- normalized UTC `observed_at` at microsecond precision;
- normalized numeric value.

The negative vector proves why the old `US/RS` (`0x1f`/`0x1e`) delimiter framing is invalid for unrestricted text: different logical field boundaries can yield the same pre-hash bytes when an ID contains those control characters. The new representation remains distinct, and PostgreSQL and Timescale produce the same canonical field bytes for text containing both control characters.

Future/production payload kinds must use a deterministic, versioned, injective or equivalently unambiguous canonical serialization covering **every immutable accepted payload field**. SHA-256 cannot repair an ambiguous pre-hash representation.

## Relocation target gate

Relocation fences the complete pre-activation target state, not only rows `<=F`.

Before seal:

- ordinary staging/projection is allowed;
- if **any** row for the relocating tenant has `accepted_ordinal > F`, the seal fails and control remains `open`.

During `sealed`:

- all target-history INSERT/UPDATE/DELETE is rejected;
- therefore no post-fence row can enter during the seal→activation window;
- the checkpoint remains bound to an unchanged target set.

After `activated`:

- existing historical rows are immutable;
- INSERT at/below `F` is rejected;
- new append above `F` is eligible.

The same target checkpoint still requires:

- target-owned measurement of actual current state;
- count + max + SHA-256 of deterministic self-delimiting canonical immutable payload;
- domain-separated HMAC-SHA-256 attestation;
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
