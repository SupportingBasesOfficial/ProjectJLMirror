# Wave 1 — Fence Privilege and Reuse Boundary

This record owns the implementation-level privilege, reuse, expression-binding and hidden-writer completeness rules for the IR-D-003 PostgreSQL fence substrate. It grants no database privilege and does not select the residual C2 serving/runtime role mapping.

## Reuse is a separate authority path

A fresh bootstrap and an existing authority relation are not the same operation.

Migration `001_platform_authority_fence.sql` is **fresh-bootstrap-only** for authority objects. It starts one explicit transaction, disables event-trigger execution transaction-locally, pins `search_path` to `pg_catalog`, proves the event-trigger guard, then checks `pg_catalog.to_regclass('platform.authority_fences')`.

If the fence table already exists, migration 001 returns from its bootstrap block before any persistent schema/table/function/default-privilege mutation. It does not attempt to make the existing object look canonical and then rely on a later migration to discover whether reuse was safe.

Migration `002_revalidate_authority_fence_contract.sql` owns reused-object admission. It starts one transaction, disables/preflights event-trigger execution, pins `search_path` to `pg_catalog`, acquires `ACCESS EXCLUSIVE`, proves the complete persisted contract and hidden-writer surface, and only after that proof may canonicalize CHECK definitions/functions/privilege narrowing. Any failure aborts the complete transaction.

Therefore:

```text
REUSED AUTHORITY OBJECT != BOOTSTRAP MUTATION ELIGIBILITY
OBJECT NAME EXISTS != REUSE AUTHORITY
PREVALIDATION MUTATION != FAIL-CLOSED REUSE
REUSE VALIDATION PASS != RUNTIME DATABASE AUTHORITY
```

## Trusted expression binding

Migration-role `search_path` is not itself proof of what an already-stored PostgreSQL expression means. A CHECK constraint stores dependencies on functions/operators/collations selected when the expression was created.

Fresh and canonical replacement SQL therefore:

- uses `SET LOCAL search_path = pg_catalog` for migration execution;
- schema-qualifies catalog functions such as `pg_catalog.btrim` and `pg_catalog.statement_timestamp`;
- uses `OPERATOR(pg_catalog.<op>)` for authority-sensitive operators, including regex/equality/order/arithmetic predicates;
- uses exact `COLLATE "C"` semantics for canonical authority identifiers;
- creates both canonical fence routines with exact `SET search_path = pg_catalog` function configuration.

Reuse validation additionally joins `pg_constraint -> pg_depend` and inspects referenced `pg_proc`, `pg_operator` and `pg_collation` objects. Canonical CHECKs fail reuse when they depend on a non-`pg_catalog` function/operator or on a collation other than exact catalog `C`, even when the displayed SQL text resembles the expected expression.

```text
MIGRATION SEARCH_PATH != TRUSTED EXPRESSION BINDING
TEXTUAL CONSTRAINT SHAPE != STORED DEPENDENCY AUTHORITY
FUNCTION NAME MATCH != FUNCTION OID/OWNER AUTHORITY
OPERATOR SPELLING MATCH != OPERATOR NAMESPACE AUTHORITY
```

## Complete pre-C2 authority proof

A reused `platform.authority_fences` boundary is admissible for Wave 1 only when all of these properties hold together:

1. the current migration/admin authority owns the `platform` schema, fence table and fence functions;
2. no direct or transitive `pg_auth_members` path can assume/inherit that owner role;
3. no non-owner role has a direct or transitive membership path into PostgreSQL predefined `pg_read_all_data` or `pg_write_all_data` before C2 role mapping;
4. no non-owner/PUBLIC schema ACL survives;
5. no non-owner/PUBLIC table ACL survives in `pg_class.relacl`;
6. no non-owner/PUBLIC column ACL survives in `pg_attribute.attacl` for any live user column of `platform.authority_fences`;
7. no non-owner/PUBLIC function ACL survives on the canonical fence functions;
8. no `SECURITY DEFINER` routine owned by the current migration authority survives anywhere in the database, regardless of schema or current EXECUTE ACL;
9. no external `pg_rewrite` object/view/rule has a `pg_depend` relation dependency on `platform.authority_fences`;
10. no `pg_subscription_rel` mapping targets `platform.authority_fences`;
11. the relation is an ordinary permanent logged non-partition relation with the exact five canonical columns, types, nullability and authority-text `C` collations;
12. no inheritance, RLS policy, generated/identity authority column, unreviewed authority-column default or noncanonical `updated_at` default survives;
13. the exact named PK and four named CHECK constraints are present and validated;
14. the PK is the exact immediate, unique, valid, ready, live, single-key conflict arbiter over `fence_scope_id`, with no expression/predicate and no extra index metadata;
15. the relation has no foreign-key referential-action surface, unexpected non-internal trigger, local rewrite rule, external rewrite dependency or logical-replication subscriber mapping;
16. canonical stored CHECK expressions depend only on accepted `pg_catalog` function/operator authority and exact catalog `C` collation;
17. migrations 001 and 002 each close their event-trigger execution window before event-trigger-capable DDL;
18. the two canonical fence functions remain `SECURITY INVOKER` and have exact `search_path=pg_catalog` function configuration;
19. migration 003 revalidates ownership/role/ACL/definer/function-config boundaries with migration-local `search_path=pg_catalog` before any later C2 role mapping;
20. migrations 001–003 perform no positive `GRANT`, `ALTER OWNER` or `SET ROLE` that could silently select the residual C2 role mapping.

## Privilege surfaces are independent

`pg_class.relacl` and `pg_attribute.attacl` are distinct privilege surfaces. A clean table ACL is not evidence that historical `SELECT(column)` / `UPDATE(column)` grants are absent. Column ACL inspection covers every `attnum > 0`, non-dropped column and rejects every grantee other than the already-proven migration/table owner; PUBLIC (`oid 0`) is rejected as well.

Object ACLs do not enumerate authority inherited through PostgreSQL predefined all-data roles. `pg_read_all_data` can disclose authority state and `pg_write_all_data` can mutate it without a corresponding relation/column/schema ACL. Before C2 role mapping, revalidation therefore walks `pg_auth_members` transitively from both predefined roles and fails closed if any non-owner role can reach either authority surface.

Function ACL cleanliness does not prove absence of definer authority. Schema placement is not a security boundary for `SECURITY DEFINER`, and current EXECUTE ACLs are not sufficient evidence. The pre-C2 proof rejects every `pg_proc` row with migration-owner `proowner` and `prosecdef` anywhere in the database. Any future definer routine is a separate reviewed privileged/C2 decision.

Local fence rewrite cleanliness is incomplete evidence: another view/rule may depend on the table. Revalidation joins `pg_rewrite` to `pg_depend` and rejects any external rewrite relation dependency on the fence table. Logical replication is a separate authority path again, so any `pg_subscription_rel.srrelid` mapping to the fence relation is rejected.

This model intentionally does not claim to eliminate PostgreSQL superuser/cluster-admin authority. That infrastructure authority remains governed by the selected C2/operations implementation.

## Event-trigger and transaction boundary

Database event triggers are database-wide DDL authority. A catalog preflight alone has TOCTOU exposure, so migrations 001 and 002 start explicit transactions, execute exactly one `SET LOCAL event_triggers = off`, prove `current_setting('event_triggers') = 'off'`, and reject any already-present `pg_event_trigger` row with `evtenabled <> 'D'` before fence DDL.

The catalog preflight and session execution guard have different meanings: preflight rejects already-enabled hooks; transaction-local disable closes execution for the current migration even if a concurrent privileged actor changes catalog state later. Neither means event triggers are permanently absent after commit.

Migration 001 performs fresh bootstrap DDL only after the absence check and keeps that fresh-bootstrap mutation in one guarded transaction. If the authority table exists, it does not mutate it.

Migration 002 keeps reused-object validation and any later canonicalization in one guarded transaction while holding `ACCESS EXCLUSIVE`. It never rewrites historical authority rows merely to make validation pass.

## Authority laws

```text
TABLE ACL CLEAN != COLUMN ACL CLEAN
OBJECT ACL CLEAN != PREDEFINED ALL-DATA ROLE ABSENT
EXPECTED FUNCTION ACL CLEAN != RESIDUAL DEFINER AUTHORITY ABSENT
SCHEMA LOCATION != DEFINER AUTHORITY BOUNDARY
LOCAL FENCE RULE CLEAN != EXTERNAL REWRITE REACHABILITY ABSENT
LOCAL DATABASE AUTHORITY SURFACES CLEAN != LOGICAL REPLICATION WRITER ABSENT
ROW/TABLE HOOKS CLEAN != DATABASE DDL EVENT-TRIGGER ABSENCE
EVENT-TRIGGER CATALOG PREFLIGHT != CLOSED EVENT-TRIGGER EXECUTION WINDOW
SESSION-LOCAL EVENT-TRIGGER DISABLE != PERMANENT DATABASE EVENT-TRIGGER ABSENCE
TRANSACTIONAL BOOTSTRAP != CLOSED EVENT-TRIGGER EXECUTION WINDOW
REUSED AUTHORITY OBJECT != BOOTSTRAP MUTATION ELIGIBILITY
PREVALIDATION MUTATION != FAIL-CLOSED REUSE
MIGRATION SEARCH_PATH != TRUSTED EXPRESSION BINDING
TEXTUAL CONSTRAINT SHAPE != STORED DEPENDENCY AUTHORITY
VALIDATED CONSTRAINT SHAPE != ATOMIC CONSTRAINT REPLACEMENT
TRANSACTIONAL DDL WITHOUT HELD TABLE LOCK != CLOSED REVALIDATION WINDOW
OBJECT OWNER == CURRENT MIGRATION AUTHORITY != OWNER ROLE UNASSUMABLE
SCHEMA/TABLE/COLUMN/FUNCTION ACL CLEAN != FUTURE C2 ROLE MAPPING
PRIVILEGE REVALIDATION PASS != RUNTIME DATABASE AUTHORITY
```

## Mandatory falsification

Observer-only validators/tests fail when any of these properties is removed, redirected or laundered through comments:

- existing `authority_fences` no longer returns from migration 001 before persistent bootstrap mutation;
- migration 001 fresh branch loses its explicit transaction, event-trigger guard, `pg_catalog` search path or catalog-bound expression primitives;
- migration 002 mutates/deletes authority rows before reuse proof, moves its `ACCESS EXCLUSIVE` lock after validation, or splits validation/canonicalization across commits;
- migration 001 or 002 loses transaction-local `event_triggers=off`, effective-setting proof, `pg_event_trigger` catalog proof or exact enabled-state predicate;
- any migration uses a writable schema in the trusted migration `search_path`;
- either canonical fence function loses exact `search_path=pg_catalog` configuration;
- canonical stored/effect identifier validation loses `pg_catalog.btrim`, exact `C` collation or catalog-bound regex/equality operators;
- CHECK dependency provenance stops validating `pg_proc`, `pg_operator` or `pg_collation` references;
- a reused CHECK may depend on a non-catalog function/operator or noncanonical collation;
- relation kind/persistence/partition/RLS, exact column set/type/collation, generated/identity/default, constraint-set, PK-index, FK, trigger, rewrite, external-dependency or subscription guards are removed/misdirected;
- any PK state predicate (`indisprimary`, `indisunique`, `indimmediate`, `indisvalid`, `indisready`, `indislive`) is negated or omitted;
- schema/table ownership queries stop binding owner expression and the exact owning catalog object together;
- recursive `pg_auth_members` traversal for migration owner or predefined all-data roles is removed/misdirected;
- table, column, schema or canonical-function ACL checks are removed/misdirected;
- the database-wide migration-owner `SECURITY DEFINER` scan is narrowed by schema/ACL/body inference;
- the exact canonical function `proconfig` is not `search_path=pg_catalog`;
- a positive `GRANT`, `ALTER OWNER` or `SET ROLE` appears before a separately reviewed C2 role mapping.

Comment text cannot satisfy executable invariants because structural validators inspect comment-stripped SQL.

Any later C2 role mapping is a separate reviewed decision and may grant only the exact least-privilege capability accepted for the chosen runtime/database mechanism. Historical residual ACLs, role membership, definer routines, rewrite/view reachability, logical-replication mappings, event-trigger execution, search-path shadowing or non-atomic reuse are never valid implementation shortcuts.
