# Wave 1 — Fence Privilege Boundary

This record owns the implementation-level privilege and hidden-writer completeness rule for the IR-D-003 PostgreSQL fence substrate. It does not grant database privileges and it does not select the later C2 serving/runtime role mapping.

## Complete pre-C2 authority proof

A reused `platform.authority_fences` boundary is admissible for Wave 1 only when all of these properties hold together:

1. the current migration/admin authority owns the `platform` schema, fence table and fence functions;
2. no direct or transitive `pg_auth_members` path can assume/inherit that owner role;
3. no non-owner role has a direct or transitive membership path into PostgreSQL predefined `pg_read_all_data` or `pg_write_all_data` before C2 role mapping;
4. no non-owner/PUBLIC schema ACL survives;
5. no non-owner/PUBLIC table ACL survives in `pg_class.relacl`;
6. no non-owner/PUBLIC **column ACL** survives in `pg_attribute.attacl` for any live user column of `platform.authority_fences`;
7. no non-owner/PUBLIC function ACL survives on the canonical fence functions;
8. no `SECURITY DEFINER` routine owned by the current migration authority survives **anywhere in the database**, regardless of schema or current EXECUTE ACL;
9. no external `pg_rewrite` object/view/rule has a `pg_depend` relation dependency on `platform.authority_fences`;
10. no `pg_subscription_rel` mapping targets `platform.authority_fences`; logical-replication apply is an independent writer surface and is not implied absent by clean local ACL/rewrite/trigger state;
11. no PostgreSQL event trigger remains enabled in the database before migration 002 executes event-trigger-capable fence DDL; a database-wide DDL hook is not implied absent by clean row-trigger/rewrite/ACL/definer/replication state;
12. the two canonical Wave 1 fence functions remain `SECURITY INVOKER`;
13. migration `002_revalidate_authority_fence_contract.sql` executes event-trigger preflight, validation and canonical CHECK replacement inside one explicit transaction while holding `ACCESS EXCLUSIVE` on the authority table until the final commit;
14. this revalidation performs no `GRANT`, `ALTER OWNER` or `SET ROLE` and therefore cannot silently select the residual C2 role mapping.

`pg_class.relacl` and `pg_attribute.attacl` are distinct privilege surfaces. A clean table ACL is not evidence that historical `SELECT(column)` / `UPDATE(column)` grants are absent. Column ACL inspection covers every `attnum > 0`, non-dropped column and rejects every grantee other than the already-proven table/migration owner; PUBLIC (`oid 0`) is therefore rejected as well.

Object ACLs also do not enumerate authority inherited through PostgreSQL predefined all-data roles. `pg_read_all_data` can disclose authority state and `pg_write_all_data` can mutate it without a corresponding `relacl`, `attacl` or `nspacl` entry. Before any separately reviewed C2 role mapping, the revalidation therefore walks `pg_auth_members` transitively from both predefined roles and fails closed if any non-owner role can reach either authority surface.

Function ACL cleanliness also does not prove absence of definer authority. Schema placement is not a security boundary for `SECURITY DEFINER`: a migration-owner routine can live outside `platform`, reference the fence with a qualified/dynamic name, or be reached indirectly through a trigger. Current EXECUTE ACLs also are not sufficient proof because a trigger path or a later C2 grant can make residual owner authority reachable. The pre-C2 proof therefore inspects `pg_proc.proowner` + `pg_proc.prosecdef` across the entire database and rejects **every** `SECURITY DEFINER` routine owned by the migration authority. Any future definer routine is a separate reviewed privileged/C2 decision.

Local fence rewrite cleanliness is likewise incomplete evidence. A view or rewrite rule on another relation can depend on `platform.authority_fences`; PostgreSQL can then use the view/rule owner authority against the underlying table. Revalidation therefore joins `pg_rewrite` to `pg_depend` and rejects every external rewrite object whose dependency graph directly references the fence relation, regardless of schema or current view ACL. Historical view/rule reachability cannot be reactivated later by a narrower-looking C2 grant.

Logical replication is a separate authority path again. A subscriber apply worker can write a mapped relation without appearing as an ordinary application ACL, trigger, view or definer routine. The structural revalidation therefore rejects **every** `pg_catalog.pg_subscription_rel` row whose `srrelid` is the fence table, regardless of current subscription state or intended operator use. Replicating fence authority later is a reviewed authority/recovery design, not a reuse-time default.

Database event triggers are a separate DDL authority path. An enabled `ddl_command_start`, `ddl_command_end`, `sql_drop`, `table_rewrite` or other event-trigger hook can execute inside the migration session when the revalidation performs `ALTER TABLE`, including after earlier catalog checks have passed. Row-level `pg_trigger`, object ACL, rewrite, definer and subscription scans do not prove that this database-wide DDL hook is absent. Migration 002 therefore performs an executable `pg_catalog.pg_event_trigger` preflight **before** event-trigger-capable fence DDL and fails closed if any event trigger has `evtenabled <> 'D'`. Wave 1 does not attempt tag inference or allowlist-by-convenience: coexistence with enabled event triggers is a separately reviewed migration/C2 decision.

Constraint revalidation is also an authority mutation, not merely a lint step. Dropping canonical checks under per-statement autocommit could make a failed migration leave the table durably weaker. Migration 002 therefore starts one explicit transaction, performs the event-trigger preflight, obtains `LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE`, performs structural checks and CHECK replacement/validation while that lock is retained, and commits only after all canonical constraints validate. PostgreSQL transactional DDL then makes any error abort the complete replacement instead of committing a partially weakened fence table.

This proof intentionally does not claim to remove PostgreSQL superuser or cluster-admin authority. Such infrastructure authority remains outside this modeled application-role boundary and must be governed by the selected C2/operations implementation. It also does not grant the migration owner runtime serving authority merely because that owner is excluded from the non-owner predefined-role check.

## Authority laws

```text
TABLE ACL CLEAN != COLUMN ACL CLEAN
OBJECT ACL CLEAN != PREDEFINED ALL-DATA ROLE ABSENT
EXPECTED FUNCTION ACL CLEAN != RESIDUAL DEFINER AUTHORITY ABSENT
SCHEMA LOCATION != DEFINER AUTHORITY BOUNDARY
LOCAL FENCE RULE CLEAN != EXTERNAL REWRITE REACHABILITY ABSENT
LOCAL DATABASE AUTHORITY SURFACES CLEAN != LOGICAL REPLICATION WRITER ABSENT
ROW/TABLE HOOKS CLEAN != DATABASE DDL EVENT-TRIGGER ABSENCE
VALIDATED CONSTRAINT SHAPE != ATOMIC CONSTRAINT REPLACEMENT
TRANSACTIONAL DDL WITHOUT HELD TABLE LOCK != CLOSED REVALIDATION WINDOW
OBJECT OWNER == CURRENT MIGRATION AUTHORITY != OWNER ROLE UNASSUMABLE
SCHEMA/TABLE/COLUMN/FUNCTION ACL CLEAN != FUTURE C2 ROLE MAPPING
PRIVILEGE REVALIDATION PASS != RUNTIME DATABASE AUTHORITY
```

## Falsification

The observer-only validators and Wave 1 tests must fail when any of the following is removed or redirected:

- `pg_attribute` as the column privilege catalog;
- `a.attrelid = v_table`;
- live user-column bounds (`attnum > 0` and `NOT attisdropped`);
- `a.attacl` as the ACL source;
- the non-owner grantee predicate;
- the explicit exception for residual non-owner column privileges;
- recursive `pg_auth_members` traversal for the migration-owner role;
- recursive `pg_auth_members` traversal for both `pg_read_all_data` and `pg_write_all_data`;
- either predefined all-data role from the starting role set;
- the non-owner predicate on predefined-role reachability;
- the database-wide `pg_proc` scan for `p.proowner = current_user::regrole::oid` plus `p.prosecdef`;
- any attempt to narrow that residual-definer scan to `p.pronamespace = v_schema`;
- the explicit exception for migration-owner residual `SECURITY DEFINER` authority;
- `pg_rewrite` as the external rewrite/view rule catalog;
- `pg_depend` as the dependency edge source;
- dependency identity `d.classid = 'pg_rewrite'::regclass`, `d.objid = r.oid`, `d.refclassid = 'pg_class'::regclass`, `d.refobjid = v_table`;
- the external relation predicate `r.ev_class <> v_table`;
- the explicit exception for external rewrite dependency reachability;
- `pg_catalog.pg_subscription_rel` as the logical-replication subscriber mapping catalog;
- exact mapping predicate `sr.srrelid = v_table`;
- the explicit fail-closed exception for logical-replication writer reachability;
- `pg_catalog.pg_event_trigger` as the database-wide DDL-hook catalog;
- exact fail-closed predicate `et.evtenabled <> 'D'`;
- the event-trigger guard occurring before the fence lock/validation and before the first fence `ALTER TABLE`;
- any attempt to satisfy the event-trigger guard only through comments;
- the single leading `BEGIN;` and final `COMMIT;` transaction boundary;
- `LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE` occurring before structural revalidation;
- any early/intermediate commit that can separate constraint drop from replacement validation.

Comment text cannot satisfy these executable invariants because privilege/revalidation validation runs on comment-stripped SQL.

Any later C2 role mapping is a separate reviewed decision and may grant only the exact least-privilege capability accepted for the chosen runtime/database mechanism. It cannot rely on historical residual ACLs, predefined-role membership, residual definer routines, external rewrite/view reachability, logical-replication mappings, enabled database event triggers or non-atomic migration execution as an implementation shortcut.
