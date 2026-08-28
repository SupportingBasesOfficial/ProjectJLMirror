# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD review and explicit Track B acceptance:

1. select the ADR-008 PostgreSQL transactional acceptance pattern as Tier 1 only with immutable canonical observation content, owner-controlled active source generation/poll epoch, exact durable live poll claims and current-state CAS by platform ordering authority;
2. require late-history finality/currentness to come from durable provider-owner authority, never worker/caller timestamps;
3. require physical PITR recovery admission to consume authenticated surviving `(R,F]` evidence external to the restored authority; a locally recreated receipt is never sufficient;
4. require recovery grants to be structured facts authenticated over deterministic self-delimiting canonical bytes; delimiter splitting must not recover authority from an opaque signed string;
5. select TimescaleDB as Tier 2 historical projection only under the mediated shared-history profile proven by this spike;
6. classify `ts_automation_owner` as a LOGIN cross-tenant privileged infrastructure principal and require production connection/admission controls to exclude tenant/application use of that role;
7. reject direct pooled RLS assumptions for Timescale columnstore/CAGG on the evaluated profile;
8. require genuine fresh-cluster reconstruction of database-global role topology;
9. require source relocation placement authority to be locked before deriving `F`;
10. require target-owned authenticated sealed canonical-payload checkpoints before target activation;
11. require source and target to hash the same deterministic, versioned, self-delimiting/unambiguous canonical observation representation;
12. require target checkpoint HMAC issuer and verifier to construct the same self-delimiting canonical checkpoint payload before cryptography;
13. reject any target data above `F` before activation unless excluded by the target lifecycle: seal fails if such data already exists, sealed rejects all DML, and activated permits only new append above `F` while existing history remains immutable;
14. apply the general rule that **cryptographic integrity never substitutes for unambiguous structured serialization**;
15. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
16. treat database versions, image digests, evidence crypto and the concrete evidence encoding as reproducibility dependencies; production may choose equivalent mechanisms only if the accepted authority/integrity/unambiguous-serialization semantics are preserved and revalidated.

## Exact empirical anchor before this review-document mutation

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

This SHA proves the executable mechanism after the structured-crypto serialization panorama. It becomes provenance after this document mutation; the exact final package HEAD must rerun both gates.

## Tier 1 acceptance authority

The PostgreSQL harness establishes:

- independent-session atomic create-or-observe;
- immutable canonical identity/content conflict rejection;
- owner source generation and poll epoch locked in the acceptance transaction;
- exact durable live poll claim for current candidacy;
- current-state CAS independent from provider event time;
- historical obligation/outbox atomicity;
- semantic idempotence and history-first/current-later independence;
- rollback across injected crash stages;
- post-COMMIT ambiguity convergence without duplicate accepted observation/history/signal effects.

## Late-history owner-currentness authority

Durable `provider_authority` owns `authority_generation`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. The worker cannot advance this authority. Sweeps bind to an expected generation and record the owner snapshot; finalization accepts no caller currentness/finality timestamp.

The negative matrix proves stale generation rejection, high-only/disjoint coverage rejection, required snapshot freshness and durable `gap` when retention loss makes recovery impossible.

## Physical PITR and structured surviving `(R,F]` authority

### Authority separation

The PITR harness has a separate surviving control PostgreSQL that is not part of the source backup/restore. It owns the recovery key and issues a grant only after `F`.

The restored database cannot derive the signing key and cannot self-mint admission authority.

### Structured grant model

The recovery grant is not an opaque pipe-delimited message. It stores these facts in distinct typed columns:

```text
grant id
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

Every protected field is encoded as:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

The canonical fields are concatenated only after each field boundary is self-delimiting. HMAC-SHA-256 covers that canonical payload. Verification re-derives the canonical payload from the structured fields and requires exact row/fact/attestation agreement.

The shell obtains the structured columns independently rather than parsing field authority from a delimiter-framed signed payload.

### Class-level falsification

The run proves ordinary `|` framing is ambiguous for unrestricted text while the canonical representation is not:

```text
physical_pitr_grant_delimiter_collision_closed=PASS value=true|true
```

The positive recovery receipt deliberately contains the old delimiter:

```text
effect|after-r
```

and exact evidence proves:

```text
physical_pitr_grant_receipt_contains_pipe=PASS
physical_pitr_local_self_mint_cannot_admit=PASS
physical_pitr_tampered_external_grant_rejected=PASS
physical_pitr_external_grant_verified=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_structured_grant
```

Thus the grant is authenticated as structured authority, not merely as a string that is interpreted later.

## Tier 2 Timescale profile

Against TimescaleDB 2.29.2 / PostgreSQL 17.11:

```text
direct pooled RLS + columnstore          -> SQLSTATE 0A000
direct pooled RLS + continuous aggregate -> SQLSTATE 0A000
```

The surviving mediated profile requires no direct tenant-facing raw/CAGG/internal-materialization privilege, tenant binding outside caller-writable SQL state, fixed-search-path `SECURITY DEFINER`, NOLOGIN `ts_owner`, and separate least-privilege LOGIN `ts_automation_owner` only for evaluated job-bearing objects.

`ts_automation_owner` is a **cross-tenant privileged infrastructure principal**. `PASSWORD NULL` is not `NOLOGIN` and is not proof of production authentication isolation; production `pg_hba`, socket/network exposure, role membership and credential provisioning must prevent application/tenant principals from authenticating as or assuming the role.

Fresh-cluster restore starts with zero JLMirror roles, reconstructs the minimum five-role topology, restores 100,004 history rows and both Timescale jobs, validates ownership and repeats the isolation/escalation matrix after restore and after a restored job executes.

## Tier 1 ↔ Tier 2 relocation

### Source fence and target lifecycle

Source placement is locked before deriving `F`; an in-flight authoritative acceptance completes before the fence and is included. `max(target)=F` is not treated as completeness.

Target lifecycle is:

```text
open
  staging allowed
  seal rejects any row > F

sealed
  all target-history DML rejected

activated
  existing history immutable
  INSERT <= F rejected
  new append > F allowed
```

### Canonical observation representation

Each observation field is serialized as UTF-8 byte length + lowercase UTF-8 hex. The current evidence profile covers ordinal, observation ID, metric definition ID, normalized UTC timestamp and normalized numeric value. The old `0x1f/0x1e` delimiter scheme is explicitly falsified as ambiguous.

### Canonical checkpoint attestation

The checkpoint HMAC itself now follows the same structural rule. Both target issuer and Tier 1 verifier encode these fields independently with `canonical_field`:

```text
open-rel-030-target-checkpoint-v1
tenant
F
checkpoint id
checkpoint generation
sealed flag
target count
target digest
target max ordinal
```

The exact run proves both stores produce the same pre-HMAC bytes:

```text
relocation_checkpoint_hmac_payload_cross_store=PASS
```

The target HMAC therefore authenticates a canonical structured checkpoint message, not a delimiter-concatenated string whose safety depends on the present field types.

The wider matrix continues to prove target-owned current-state measurement, fabricated attestation rejection, canonical payload mismatch rejection, seal-vs-DML serialization, pre-seal/post-seal `>F` exclusion, immutable activated history and stale source rejection.

## General structured-crypto invariant

D2 establishes the following reusable rule:

> For every hash, MAC, signature or equivalent cryptographic integrity boundary over structured data, the mapping from logical fields to protected bytes must itself be deterministic, versioned and injective or equivalently unambiguous. Cryptographic strength cannot compensate for ambiguous pre-crypto framing.

The concrete UTF-8 length+hex representation is a bounded evidence mechanism, not a mandatory production format. An equivalent production encoding may replace it only with separately reviewed proof that it preserves the same structural, authority and integrity properties.

## Capacity / crypto / deployment boundaries

Capacity measurements remain bounded mechanism-fitness evidence; `OPEN-REL-020` retains production numeric ownership.

HMAC-SHA-256/SHA-256 do not select production KMS/HSM/TEE, key rotation, secret provisioning or the exact canonical wire format. Database image versions are reproducibility dependencies rather than permanent production pins.

## Material finding classes closed by D2

The program has repaired, among others:

1. conflicting observation content under stable identity;
2. caller-asserted source/poll authority;
3. same-cluster restore falsely implying role reconstruction;
4. relocation `F` derived before authority lock;
5. max-only target completeness;
6. disjoint/max-only history reconciliation completeness;
7. target receipt not bound to actual target state;
8. observation digest omitting immutable payload;
9. target seal not serialized with DML;
10. cross-tenant freeze/owner hardening;
11. Timescale LOGIN automation owner trust-class ambiguity;
12. restored authority self-minting recovery evidence;
13. history worker self-asserting currentness/finality;
14. uncheckpointed target `>F` history surviving cutover;
15. delimiter-framed unrestricted observation text producing ambiguous pre-hash serialization;
16. delimiter-framed structured recovery grants producing ambiguous authenticated-message boundaries;
17. checkpoint HMAC relying on delimiter concatenation rather than the same canonical structured representation used by the verifier.

Each material finding triggered class-level/panoramic repair rather than a line-only patch.

## What acceptance would and would not mean

If the exact-final-HEAD package is reviewed clean and Track B is explicitly accepted:

```text
OPEN-REL-030
  -> selected + conformed for the accepted mechanism/profile

Wave 4 implementation
  -> still NOT automatically authorized
```

Acceptance would not choose immutable production PostgreSQL/Timescale versions, production KMS/HSM topology, production database authentication/network topology, production capacity numerics, or require the exact evidence encoding if another implementation proves equivalent deterministic/versioned/unambiguous structured serialization.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  3ffc96073b54fe7a8b5d002523733947ee59ba57 / #2012 / #74
Final documentation HEAD     REQUIRES FRESH EXACT-HEAD CI
Codex final review           REQUIRED
Native Assurance             REQUIRED
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                         NOT AUTHORIZED BY THIS RECORD
```
