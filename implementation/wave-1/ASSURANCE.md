# Wave 1 Assurance Boundary

Wave 1 conformance evidence is subordinate to the accepted Product, Security, API, Reliability, Runtime, Operations and Implementation Readiness authorities.

Required exact-HEAD evidence before merge readiness:

- repository deterministic assurance remains green;
- Wave 0 contract tooling remains green;
- Wave 1 unit/adversarial tests remain green;
- Wave 1 authority validator reports no findings;
- the exact Git delta from `main@5b56ad94566b48b72a993ee8f5cf7e983127ab21` remains inside the closed Wave 1 path allowlist;
- PR scope remains only identity/control-plane/minimal-runtime authority skeleton;
- caller/request-adjacent authority identifiers fail before C2 adapter invocation when non-canonical;
- browser session capability input is bounded and canonical before session-authority lookup;
- browser auth transaction currentness is fail-closed for both not-yet-current and expired transactions;
- explicit cross-tenant privileged platform operations cannot be admitted through the ordinary application runtime boundary: a caller-selected `CONTROL_PLANE` binding is insufficient and the actual executing runtime must be proven current/active by trusted authority;
- ordinary tenant/resource protected operations are admitted only through the exact `runtime.api@1` authority boundary; `runtime.web-bff@1` and `runtime.control-plane@1` cannot substitute even when caller-selected runtime/context evidence looks internally consistent;
- privileged/policy-sensitive human admission does not treat an earlier MFA/step-up result as durable authority;
- owning authorization, principal currentness, TenantContext/placement/runtime/fence currentness, authentication-strength currentness and executing-runtime currentness are never made final merely by choosing a serial evaluation order;
- serial currentness checks are narrowing/fail-fast evidence only and **cannot** be returned as final protected-operation authority;
- final protected-operation admission fails closed unless a `FinalAdmissionAuthorityPort` returns a well-formed `FinalAdmissionEvidence` whose implementation re-establishes every applicable current authority as one atomic or revision-bound logical decision;
- the final-admission boundary uses authority-owned currentness/time and receives no caller/request `now` parameter;
- final admission binds exact principal ID, exact principal kind and exact credential/session generation; textual ID/generation equality cannot transfer a grant between human, machine, internal-service or platform-admin principal classes;
- final admission binds the exact declaration `scope` and `tenant_requirement` in addition to action/resource semantics, so evidence cannot cross authorization declaration classes;
- final tenant admission binds exact current tenant/cell placement revision plus placement/runtime/configuration/workload-credential/network-policy generations, environment/isolation, fence scope and fence epoch;
- every protected final admission also binds current executing-runtime authority revision, exact expected runtime profile, executing runtime generation **and the exact executing environment class**; TenantContext destination `runtime_generation`, runtime profile or environment label cannot substitute for current execution authority;
- the final executing environment must be one of the exact environment classes allowed by the expected runtime binding; for cross-tenant privileged work, later trusted runtime evidence and the final snapshot must agree on profile, generation and environment;
- final resource-scoped admission requires a non-null canonical `resource_scope`; a final snapshot for one resource cannot admit another resource merely because the action is identical;
- non-resource declarations reject `resource_scope` rather than carrying dormant/misleading resource authority;
- final privileged-human admission binds both the exact `authentication_strength_policy_id` declared for the operation and the current authentication-strength/Security policy revision; equal revision labels do not make different policy IDs interchangeable;
- final cross-tenant privileged admission binds the exact canonical `cross-tenant target` (explicit tenant set or governed selection criteria) in both final request and evidence; the same action cannot reuse a grant for a different target set;
- final cross-tenant privileged admission binds the current executing Control Plane runtime authority revision, exact `runtime.control-plane@1` profile, exact runtime generation and exact executing environment;
- final admission always binds principal authority revision, principal identity/kind/session-or-credential generation, exact action, exact declaration scope/tenant requirement, resource-scope semantics, authentication-strength policy identity where applicable, final admission revision, owning authorization policy revision and executing-runtime authority;
- any mismatch, omission, malformed evidence, denied/current=false state or final-admission authority failure is a closed denial; there is no fallback to serial checks;
- an admitted final snapshot remains an admission result only and cannot replace effect-boundary fencing/currentness/atomicity;
- fenced effect admission resolves current state from the owning fence authority; a typed/supplied fence record is not currentness proof, and co-resident PostgreSQL effects retain the same-transaction predicate requirement;
- canonical fence scope/generation/state identifiers use deterministic PostgreSQL `COLLATE "C"` storage/comparison semantics so database-default collation cannot alias distinct canonical authority identifiers;
- persisted fence authority state is revalidated against canonical identifier/positive-epoch constraints and exact `pg_catalog."C"` collation for authority-bearing text columns rather than accepted by object presence;
- reused fence storage has an exact finite metadata contract: the named canonical PK, four named canonical CHECK constraints, exactly the PK backing index and no additional constraint/index metadata capable of rejecting or altering canonical writes;
- reused PostgreSQL fence objects fail closed unless the migration authority owns the schema/table/functions, no effective non-owner schema/table/**column**/function ACL survives, and no direct or transitive `pg_auth_members` path can assume/inherit the migration-owner role before separately reviewed C2 role mapping;
- table-level `pg_class.relacl` cleanliness never substitutes for column-level `pg_attribute.attacl` cleanliness: every live user column of `platform.authority_fences` must have no non-owner/PUBLIC column privilege before C2 role mapping;
- expected fence-function ACL cleanliness never substitutes for absence of residual definer authority: pre-C2 revalidation rejects every `pg_proc` row with `p.proowner = current_user::regrole::oid` and `p.prosecdef` across the **entire database**, regardless of schema or current EXECUTE ACL;
- schema placement never narrows migration-owner definer authority: no `p.pronamespace = v_schema` boundary can substitute for database-wide owner-definer absence;
- local trigger/rule cleanliness on `platform.authority_fences` never proves external rewrite/view reachability is absent: pre-C2 revalidation joins `pg_rewrite` to `pg_depend` and rejects every external rewrite object whose relation dependency directly references the fence table;
- local ACL/trigger/rewrite/definer cleanliness never proves logical-replication writer absence: structural revalidation rejects any `pg_catalog.pg_subscription_rel` mapping whose `srrelid` is the fence table;
- row/table trigger, ACL, rewrite, definer and replication cleanliness never proves database-wide DDL event-trigger absence: migration 002 rejects any `pg_catalog.pg_event_trigger` row with `evtenabled <> 'D'` before the first event-trigger-capable fence DDL statement;
- canonical CHECK replacement in migration 002 is one explicit PostgreSQL transaction, with event-trigger preflight before fence DDL and `ACCESS EXCLUSIVE` acquired before structural revalidation and retained through replacement validation and final `COMMIT`; statement-autocommit execution cannot durably expose a dropped/partially replaced constraint set;
- no residual C2 product is silently promoted to architecture authority;
- no Product/domain endpoint family is introduced beyond accepted authority;
- review findings are resolved only after later exact-HEAD evidence;
- Native Assurance passes 1–12 are clean on the exact final HEAD.

Mandatory falsification includes:

- all serial checks green but no final-admission authority -> deny;
- malformed, unavailable, denied or non-current final-admission authority -> deny;
- principal/action/session-generation drift in final evidence -> deny;
- same principal ID and credential generation but a different principal kind -> deny;
- same principal/action/context with different `scope` or `tenant_requirement` cannot reuse final evidence;
- `ScopeClass.RESOURCE` without `resource_scope` -> reject before authorization;
- non-resource declaration carrying `resource_scope` -> reject;
- same action with different resource scope cannot reuse final evidence;
- tenant/resource protected admission through `runtime.web-bff@1` or `runtime.control-plane@1` -> deny;
- tenant final evidence missing any executing-runtime binding -> reject;
- tenant final evidence bound to the wrong executing runtime profile or a disallowed executing environment -> deny;
- tenant/cell/placement/runtime/configuration/workload-credential/network-policy/fence drift -> deny;
- final Security/authentication-strength revision drift -> deny;
- same authentication-strength revision under a different policy ID -> deny;
- same cross-tenant action with a different canonical cross-tenant target cannot reuse final evidence -> deny;
- non-cross-tenant operation carrying a cross-tenant target binding -> deny;
- cross-tenant final executing-runtime profile or generation drift -> deny;
- cross-tenant final snapshot with the same runtime profile/generation but a different executing environment than the latest trusted runtime evidence -> deny;
- removal of deterministic `C` collation from fence storage/equality -> validator finding;
- reused fence table with non-`C` authority text collation -> revalidation failure;
- extra `UNIQUE`, `CHECK`, exclusion, expression, partial or other noncanonical constraint/index metadata on `platform.authority_fences` -> revalidation failure;
- removing or misdirecting the exact finite fence constraint-set guard or extra-index guard -> validator finding;
- reused fence table with any non-owner/PUBLIC column-level `attacl` entry -> revalidation failure;
- removing, misdirecting or comment-laundering the `pg_attribute.attacl` guard -> validator finding;
- any migration-owner `SECURITY DEFINER` routine anywhere in the database -> revalidation failure, even outside `platform` or without a current non-owner EXECUTE ACL;
- narrowing the owner-definer scan by schema, ACL or routine-body inference -> validator finding;
- an external view/rule/rewrite object with a `pg_depend` relation edge to `platform.authority_fences` -> revalidation failure;
- removing, misdirecting or comment-laundering the `pg_rewrite -> pg_depend -> v_table` external dependency guard -> validator finding;
- a logical-replication subscriber mapping with `pg_subscription_rel.srrelid = platform.authority_fences` -> revalidation failure;
- removing, redirecting or comment-laundering the `pg_subscription_rel -> v_table` writer guard -> validator finding;
- any PostgreSQL event trigger with `pg_event_trigger.evtenabled <> 'D'` -> migration 002 failure before fence DDL;
- removing or redirecting the `pg_catalog.pg_event_trigger` catalog guard, inverting `evtenabled <> 'D'`, moving the guard after fence DDL or satisfying it only through comments -> validator finding;
- removing the leading `BEGIN`, final `COMMIT`, or `ACCESS EXCLUSIVE` table lock from migration 002 -> validator finding;
- moving the fence lock after structural validation or introducing an early/intermediate `COMMIT` before canonical constraint validation -> validator finding;
- valid final evidence returns the final owning authorization policy revision, not an earlier serial authorization revision;
- no caller-supplied `now` reaches the final-admission port.

`CI GREEN != MERGE AUTHORIZATION` and `WAVE 1 ACCEPTED != WAVE 2 AUTHORIZED`.
