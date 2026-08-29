# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD CI, clean Native Assurance, a fresh adversarial Codex review and explicit Track B acceptance, select the bounded C2 mechanism/profile only with the following coupled guarantees:

1. immutable canonical Tier 1 observation identity/content;
2. owner-controlled source generation, poll epoch and durable live poll claim inside transactional acceptance;
3. platform ordering authority for current-state CAS, never provider event time;
4. owner-derived reconciliation finality/currentness;
5. reconciliation coverage bound to exact authority generation, provider dataset revision and required snapshot currentness;
6. provider mutation invalidates current coverage atomically; stable identity rewrite, DELETE and TRUNCATE fail closed;
7. stable accepted identities are validated independently of current `became_visible_at` whenever either side intersects the sweep window;
8. a retained historical `finalized_through` watermark can never be re-advertised as current completeness after invalidation unless current-revision coverage has again reached that watermark;
9. all current history hardening modules `004–009` execute under an anti-orphan workflow guard;
10. physical PITR admission derives from authenticated surviving authority external to restored state;
11. actual post-R effect evidence is authenticated, grant-bound and locally applied only after verified material fetch;
12. one canonical recovery-boundary winner exists across equivalent grant IDs;
13. the surviving active authority tuple is locked before winner derivation and revalidated by claim/verify/fetch;
14. the winner is bound to authenticated principal plus non-PGDATA effective restored-instance proof;
15. clone rejection requires same-path positive control;
16. recovery material fetch uses a consistent locked authority→grant→claim→effect/signing snapshot;
17. the hardened positive recovery path is exercised after hardening installation;
18. established recovery/clone response deadlines are caller-local, asynchronous and fail closed without synchronous timeout cleanup;
19. real established TCP blackholes are directly falsified;
20. deterministic versioned self-delimiting serialization and total/injective typed canonicalization precede hashes/MACs/signatures;
21. Timescale Tier 2 is selected only under the mediated shared-history profile proven by C2 evidence;
22. `ts_automation_owner` remains cross-tenant privileged infrastructure, excluded from tenant/application auth;
23. fresh-cluster role reconstruction and post-restore/job attack matrices are mandatory;
24. source relocation authority is locked before F and target completeness is canonical-set completeness, never max-only;
25. target checkpoint measurement/signing authority originates target-side; Tier 1 verifies but cannot mint;
26. verifier credentials remain restricted capability state, absent from function source;
27. effective final cross-authority verifier transport has caller-local response deadlines and no synchronous timeout cancel/disconnect;
28. real response blackholes are exercised in both relocation directions;
29. Tier 1 successor placement and exact activation grant commit atomically;
30. target `sealed → activated` requires that exact committed Tier 1 grant;
31. pre-activation future rows are rejected; activated existing history is immutable and only new append `>F` is eligible;
32. `OPEN-REL-020` remains owner of production capacity/SLO/retention/cardinality/cost numerics;
33. evaluation database versions, image digests, evidence HMACs, LOGIN roles, external-to-PGDATA mount, `dblink`, one-shot session retirement and laboratory deadlines remain reproducibility dependencies, not frozen production selections.

## Exact empirical mechanism anchor before governance mutation

```text
HEAD
61f8ae668f719f18024a36f06a068937169534a6

JLMIRROR Deterministic Assurance
run #2231
run id 33281621862
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #183
run id 33281621858
SUCCESS
```

Exact #183 verifies the anchor SHA, reports six history hardening modules, preserves the complete #38–#48 recovery/clone/Timescale/relocation package and adds the class #49 regression proof:

```text
history_retained_finalized_watermark_requires_revalidation=PASS
history_retained_finalized_watermark_recovers_after_full_revalidation=PASS
open_rel_030_extended_conformance=PASS
closure_claim=false governed Track B acceptance still required; production/Wave4/merge authorization not granted
```

## Class #49 — retained finalized watermark revalidation

### Finding

A stream could already have durable `finalized_through=T2`. Provider-visible dataset mutation correctly advanced `provider_dataset_revision` and invalidated current reconciliation coverage but intentionally preserved the durable historical T2 watermark. A later worker could sweep only through `T1<T2` and call `try_finalize(...,T1)`. The old function validated current-revision coverage only through T1, then used `GREATEST(finalized_through,p_finalize_through)` and set `state=complete`, thereby falsely advertising the unswept interval `(T1,T2]` as revalidated.

### Closure

The effective final `try_finalize(...)` now derives `required_through` as the greatest of the caller request and the retained historical watermark. Current authority-generation + current provider-dataset-revision + owner-required snapshot coverage must be contiguous through that entire bound before `complete` can be restored. If coverage is shorter, the function leaves the historical watermark durable, publishes only the current coverage actually established, sets `reconciliation_required` and returns false.

The dedicated vector proves both directions:

- baseline finalization through T2 succeeds;
- dataset mutation advances revision and clears current coverage while retaining T2;
- current-revision sweep only through T1 cannot restore complete;
- T2 remains durable but non-advertised as current completeness;
- after current-revision coverage is extended back through T2, even a T1 request may succeed because the retained T2 obligation has actually been revalidated.

This closes the Codex P1 thread `PRRT_kwDOT7x07M6ddV1O` at the mechanism/evidence layer. Governance promotion and fresh exact-final-head review are separate gates.

## Material finding classes closed by D2

The evidence program has repaired **49 material classes**, with panoramic review after each repair:

1. conflicting observation content under stable Tier 1 acceptance identity;
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
20. placement/grant lacking explicit all-or-nothing failure evidence;
21. signing key generated/provisioned by cross-database controller instead of target authority;
22. verifier connection secrets embedded in SQL function source;
23. reconciliation coverage reusable across authority-generation changes with same timestamps;
24. owner-current provider conflict silently treated as duplicate;
25. surviving recovery grant reusable across multiple restored authorities;
26. established relocation `dblink` verification lacking caller-local response deadline;
27. recovery single-winner binding relying on caller-copyable target identifier;
28. recovery principals needing direct grant read/caller-supplied signed facts;
29. stable identity correction escaping validation when `observed_at` crosses sweep boundary;
30. timestamp canonicalization non-injective across BC/AD;
31. provider dataset mutation leaving coverage reusable without dataset-revision change;
32. reviewer-critical history module present but not executed by runner;
33. non-finite `timestamptz` disappearing under finite-only formatting;
34. statement-level TRUNCATE bypassing row mutation fencing;
35. numeric `NaN`/`Infinity`/`-Infinity` lacking total cross-store canonicalization;
36. accepted stable-identity conflict hidden by owner correction moving `became_visible_at` beyond current snapshot;
37. duplicate independent physical restore accepted as same-principal retry when recovery credential is reused;
38. post-enrollment physical PGDATA clone inheriting database-resident instance capability;
39. post-enrollment clone rejection able to false-pass because helper/transport failure looked like capability rejection;
40. recovery single-winner scoped to arbitrary `grant_id`;
41. restored authority able to claim reconciliation without authenticating/applying actual surviving `(R,F]` effect;
42. physical-recovery claim/verify/material-fetch using unbounded synchronous established-session response semantics;
43. recovery-material fetch verify-then-unlocked-reread allowing in-flight grant/effect substitution;
44. cooperative delay failing to prove real network blackhole while synchronous cleanup could exceed deadline;
45. validly signed grant drifting successor epoch or placement version without active singleton check;
46. active-authority hardening installed after the successful base recovery, leaving hardened positive path unproven;
47. post-enrollment clone claim/verify retaining synchronous established-session response behavior;
48. effective relocation verifier timeout cleanup synchronously disconnecting under a real blackhole;
49. retained historical `finalized_through` being re-advertised as complete after dataset invalidation using only shorter current-revision coverage.

## What acceptance would and would not mean

If the exact-final package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would **not** freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, workload/instance identity mechanism, verifier secret-store mechanism, production timeout/cancellation numerics, capacity numerics, or the evidence `dblink`/one-shot-session mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  61f8ae668f719f18024a36f06a068937169534a6 / #2231 / #183
Material finding classes     49
History hardening modules    6 (004–009)
Inline review threads        0 unresolved after #49 evidence closure
Exact-final documentation CI REQUIRED AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           NOT GRANTED
Wave 4 implementation        NOT AUTHORIZED
Production authority         NONE
Merge                        NOT AUTHORIZED
```
