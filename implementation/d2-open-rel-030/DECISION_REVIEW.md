# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** **TRACK B ACCEPTED**  
**Track B acceptance authorization:** granted by explicit authorization  
**Closure claim:** false — separately unauthorized  
**Wave 4 implementation authorization:** not granted  
**Production authority:** none  
**Merge authorization:** `not_granted`

## Authorization basis

Explicit Track B acceptance was granted only after the exact stationary decision-review HEAD satisfied all required gates:

```text
HEAD                        622c094c9274a778d1c21c5976dd3b2ca7b4cedf
Deterministic Assurance    #2273 / run 33283807517 / SUCCESS
OPEN-REL-030 Conformance   #204 / run 33283807551 / SUCCESS
Native Assurance           review 5059581679 / P0=0 P1=0 P2=0
Fresh Codex exact-head     comment 5465822591 / CLEAN — no major issues
Inline threads             0 unresolved
PR mergeable               true
```

The acceptance-state governance mutation and every accepted-state successor create a new HEAD and therefore must independently pass exact-head CI, Native Assurance and fresh Codex before merge-readiness can be asserted. That assurance requirement does not revoke the explicit decision authorization; it validates the exact recorded accepted state.

## Accepted mechanism/profile

Track B accepts the bounded C2 mechanism/profile only as the following coupled invariant set:

1. immutable canonical Tier 1 observation identity/content;
2. owner-controlled source generation, poll epoch and durable live poll claim inside transactional acceptance;
3. platform ordering authority for current-state CAS, never provider event time;
4. owner-derived reconciliation finality/currentness;
5. coverage bound to exact authority generation, provider dataset revision and required snapshot currentness;
6. provider mutation invalidates coverage; stable identity rewrite, DELETE and TRUNCATE fail closed;
7. accepted stable identities are validated independently of current `became_visible_at`;
8. retained historical `finalized_through` requires current-revision revalidation through that watermark before `complete` returns;
9. NULL requested finalization cutoff fails with SQLSTATE `22004` before completeness logic;
10. provider mutation, sweep and finalization share `provider_authority → stream_state` lock order;
11. worker-facing paths cannot bypass the canonical lock-order wrappers;
12. real mutation×finalize and mutation×sweep races complete without deadlock/lock abort;
13. all history hardening modules `004–010` execute under an anti-orphan guard;
14. physical PITR admission derives from authenticated surviving authority external to restored state;
15. post-R effect evidence is authenticated, grant-bound and applied only after verified material fetch;
16. one canonical recovery-boundary winner exists across equivalent grant IDs;
17. the active recovery authority tuple is locked before winner derivation and revalidated by claim/verify/fetch;
18. winner authority is bound to authenticated principal plus non-PGDATA effective restored-instance proof;
19. clone rejection requires a same-path positive control;
20. recovery material fetch uses a consistent locked active-authority→grant→claim→effect/signing snapshot;
21. hardened positive recovery is replayed after hardening installation through claim→verify→fetch/apply→verify;
22. recovery/clone established-response deadlines are caller-local, async and fail closed without synchronous timeout cleanup;
23. real established TCP blackholes are directly falsified;
24. deterministic self-delimiting serialization and total/injective typed canonicalization precede cryptographic digests;
25. Timescale Tier 2 is accepted only under the mediated shared-history profile proven by C2 evidence;
26. `ts_automation_owner` remains privileged cross-tenant infrastructure, excluded from tenant/application authority;
27. fresh-cluster role reconstruction and post-restore/job attack matrices remain mandatory;
28. fresh-restored policy-job inventory must match source evidence cardinality and cover both `shared_history` and `shared_hourly`;
29. every restored Timescale policy job must execute successfully before the post-job tenant/escalation matrix is evaluated;
30. source relocation authority is locked before F and target completeness is canonical-set completeness;
31. target checkpoint measurement/signing authority originates target-side; Tier 1 verifies but cannot mint;
32. verifier credentials remain restricted capability state and absent from function source;
33. effective cross-authority verifier transport has caller-local response deadlines and no synchronous timeout cleanup;
34. real response blackholes are exercised in both relocation directions;
35. Tier 1 successor placement and exact activation grant commit atomically;
36. target `sealed → activated` requires that exact committed Tier 1 grant;
37. pre-activation future rows are rejected; activated existing history is immutable and only new append `>F` is eligible;
38. `OPEN-REL-020` remains owner of production capacity/SLO/retention/cardinality/cost numerics;
39. evaluation database versions, image digests, evidence HMACs, LOGIN roles, external-to-PGDATA mounts, `dblink`, one-shot session retirement and laboratory deadline values remain reproducibility dependencies rather than frozen production selections;
40. current merge authorization is explicit governed state; conformance derives/asserts it from the manifest and may not hard-code a current merge status.

## Empirical provenance

History/mechanism anchor through class #51:

```text
51cddbca4258a78ed8f4a3254ff54a01a332e933
Deterministic Assurance #2261 / 33283602526 / SUCCESS
OPEN-REL-030 Conformance #198 / 33283602532 / SUCCESS
History hardening modules 7 (004–010)
```

Class #52 governance repair anchor:

```text
0f0d72ca443ff2c87f44409e65f893c99b530aed
Deterministic Assurance #2295 / 33285211010 / SUCCESS
OPEN-REL-030 Conformance #215 / 33285210993 / SUCCESS
merge_authorization_guard=true
```

Class #53 Timescale fresh-restore repair anchor:

```text
d20e83780d1c370e96a5a960f27a6a959f7a320c
Deterministic Assurance #2309 / 33286313003 / SUCCESS
OPEN-REL-030 Conformance #222 / 33286312997 / SUCCESS
restored_policy_jobs_executed=2
restored_job_targets=shared_history,shared_hourly
```

The pre-acceptance authorization-basis HEAD remains:

```text
622c094c9274a778d1c21c5976dd3b2ca7b4cedf
#2273 SUCCESS / #204 SUCCESS / Native CLEAN / Codex CLEAN
```

## Material finding classes closed by D2

The accepted evidence program repaired **53 material classes**, each followed by panoramic review:

1. conflicting observation content under stable Tier 1 identity;
2. caller-asserted source/poll authority;
3. same-cluster restore falsely implying role reconstruction;
4. relocation F derived before authority lock;
5. max-only target completeness;
6. disjoint/max-only history reconciliation completeness;
7. target receipt not bound to actual target state;
8. observation digest omitting immutable payload;
9. target seal not serialized with DML;
10. cross-tenant freeze/owner hardening;
11. Timescale LOGIN automation-owner trust ambiguity;
12. restored authority self-minting recovery evidence;
13. history worker self-asserting currentness/finality;
14. uncheckpointed target `>F` surviving cutover;
15. delimiter-framed unrestricted observation text;
16. delimiter-framed structured recovery grants;
17. checkpoint HMAC relying on ambiguous concatenation;
18. Tier 1 holding target checkpoint HMAC key/mint capability;
19. target automation leaving `sealed` before Tier 1 grant;
20. placement/grant lacking all-or-nothing failure evidence;
21. signing key provisioned by cross-database controller rather than target authority;
22. verifier connection secrets embedded in SQL function source;
23. reconciliation coverage reusable across authority-generation changes;
24. owner-current provider conflict silently treated as duplicate;
25. surviving recovery grant reusable across multiple restored authorities;
26. established relocation verification lacking caller-local response deadline;
27. recovery single-winner binding relying on caller-copyable target identifier;
28. recovery principals needing direct grant read/caller-supplied signed facts;
29. stable identity correction escaping validation across sweep boundary;
30. timestamp canonicalization non-injective across BC/AD;
31. provider mutation leaving coverage reusable without dataset revision;
32. history hardening module present but not executed by runner;
33. non-finite `timestamptz` disappearing under finite-only formatting;
34. statement-level TRUNCATE bypassing mutation fencing;
35. numeric non-finite values lacking total cross-store canonicalization;
36. accepted stable-identity conflict hidden by visibility-time correction;
37. duplicate independent physical restore accepted as same-principal retry;
38. post-enrollment PGDATA clone inheriting database-resident instance capability;
39. clone rejection able to false-pass because broken helper/transport looked like rejection;
40. recovery single-winner scoped to arbitrary `grant_id`;
41. restored authority claiming reconciliation without authenticating/applying surviving `(R,F]` effect;
42. physical-recovery helpers using unbounded established-session response semantics;
43. recovery-material fetch TOCTOU via verify-then-unlocked reread;
44. cooperative delay failing to prove real network blackhole while sync cleanup could exceed deadline;
45. validly signed grant drifting successor epoch or placement without active singleton check;
46. active-authority hardening installed after successful base recovery, leaving hardened positive path unproven;
47. post-enrollment clone claim/verify retaining synchronous established-response behavior;
48. effective relocation verifier timeout cleanup synchronously disconnecting under blackhole;
49. retained finalized watermark re-advertised after dataset invalidation using only shorter current coverage;
50. NULL finalization cutoff exploiting SQL three-valued logic to mint completeness;
51. inconsistent provider/history authority lock order allowing mutation-versus-finalization deadlock;
52. conformance hard-coding merge authorization instead of deriving current merge state from governed authority;
53. fresh restore executing only one restored Timescale policy job while allowing the other restored job to remain unexercised.

## Class #52 closure

Codex identified #52 on exact accepted-state SHA `b09979d96f9461e024fc717a67a8944c2e34f8b2` in thread `PRRT_kwDOT7x07M6dd3bh`.

The repair on `0f0d72ca443ff2c87f44409e65f893c99b530aed`:

- adds top-level machine-readable `merge_authorization=not_granted`;
- records that merge authorization has not been separately granted;
- makes the extended runner assert that governed value;
- derives the terminal `merge=...` value directly from the manifest;
- makes the workflow guard require the dynamic expression and reject the prior hard-coded terminal value;
- preserves Track B accepted, closure false, Wave 4 not granted and production authority none.

Exact repair gates #2295/#215 are SUCCESS, and the Codex thread was resolved only after that evidence was recorded.

## Class #53 closure

Codex identified #53 on exact accepted-state SHA `01e4ba2c366d5d22a925d320403dce317dc81dd3` in thread `PRRT_kwDOT7x07M6dd_SA`.

The repair on `d20e83780d1c370e96a5a960f27a6a959f7a320c`:

- removes the single restored-job `LIMIT 1` execution path;
- enumerates every restored `ts_evidence` policy job;
- requires enumerated restore cardinality to match both restore inventory and source evidence cardinality;
- requires restored job targets to cover exactly `shared_history` and `shared_hourly` in the bounded profile;
- executes `public.run_job(...)` for every restored job ID;
- emits per-job PASS markers and `timescale_fresh_restore_all_jobs_executed=PASS count=2`;
- runs the full post-job tenant/escalation attack matrix only after all restored jobs have completed successfully;
- preserves Track B accepted, closure false, Wave 4 not granted, production authority none and merge not granted.

Exact repair gates #2309/#222 are SUCCESS. #222 proves both restored jobs execute, target/cardinality checks pass, the complete post-job attack matrix remains green, and the full history/PITR/clone/recovery/relocation regression package still ends `open_rel_030_extended_conformance=PASS`. The Codex thread was resolved only after that exact-head evidence was recorded.

## Meaning of acceptance

Track B acceptance selects/conforms the bounded C2 mechanism/profile described above as the accepted decision outcome for `OPEN-REL-030`.

It **does not**:

- claim closure of `OPEN-REL-030` beyond the explicit Track B decision authorization;
- authorize Wave 4 implementation;
- authorize production deployment or production authority;
- freeze PostgreSQL/Timescale versions;
- select production KMS/HSM, workload identity, database authentication/network/RPC topology, verifier secret-store mechanism, timeout/cancellation numerics or capacity numerics;
- authorize merge.

## Review disposition

```text
Evidence completeness        COMPLETE
Track B decision             ACCEPTED
Track B authorization        GRANTED
Material finding classes     53
History hardening modules    7 (004–010)
Closure claim                FALSE / NOT AUTHORIZED
Wave 4 implementation        NOT AUTHORIZED
Production authority         NONE
Production selections        NOT MADE
Merge authorization          NOT_GRANTED
Post-acceptance exact-head   CI + Native + fresh Codex REQUIRED
```

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
