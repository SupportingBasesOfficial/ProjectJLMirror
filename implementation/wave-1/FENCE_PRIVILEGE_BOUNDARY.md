# Wave 1 — Fence Privilege Boundary

This record owns the implementation-level privilege completeness rule for the IR-D-003 PostgreSQL fence substrate. It does not grant database privileges and it does not select the later C2 serving/runtime role mapping.

## Complete pre-C2 privilege proof

A reused `platform.authority_fences` boundary is admissible for Wave 1 only when all of these properties hold together:

1. the current migration/admin authority owns the `platform` schema, fence table and fence functions;
2. no direct or transitive `pg_auth_members` path can assume/inherit that owner role;
3. no non-owner role has a direct or transitive membership path into PostgreSQL predefined `pg_read_all_data` or `pg_write_all_data` before C2 role mapping;
4. no non-owner/PUBLIC schema ACL survives;
5. no non-owner/PUBLIC table ACL survives in `pg_class.relacl`;
6. no non-owner/PUBLIC **column ACL** survives in `pg_attribute.attacl` for any live user column of `platform.authority_fences`;
7. no non-owner/PUBLIC function ACL survives;
8. fence functions remain `SECURITY INVOKER`;
9. this revalidation performs no `GRANT`, `ALTER OWNER` or `SET ROLE` and therefore cannot silently select the residual C2 role mapping.

`pg_class.relacl` and `pg_attribute.attacl` are distinct privilege surfaces. A clean table ACL is not evidence that historical `SELECT(column)` / `UPDATE(column)` grants are absent. Column ACL inspection covers every `attnum > 0`, non-dropped column and rejects every grantee other than the already-proven table/migration owner; PUBLIC (`oid 0`) is therefore rejected as well.

Object ACLs also do not enumerate authority inherited through PostgreSQL predefined all-data roles. `pg_read_all_data` can disclose authority state and `pg_write_all_data` can mutate it without a corresponding `relacl`, `attacl` or `nspacl` entry. Before any separately reviewed C2 role mapping, the revalidation therefore walks `pg_auth_members` transitively from both predefined roles and fails closed if any non-owner role can reach either authority surface.

This proof intentionally does not claim to remove PostgreSQL superuser or cluster-admin authority. Such infrastructure authority remains outside this modeled application-role boundary and must be governed by the selected C2/operations implementation. It also does not grant the migration owner runtime serving authority merely because that owner is excluded from the non-owner predefined-role check.

## Authority laws

```text
TABLE ACL CLEAN != COLUMN ACL CLEAN
OBJECT ACL CLEAN != PREDEFINED ALL-DATA ROLE ABSENT
OBJECT OWNER == CURRENT MIGRATION AUTHORITY != OWNER ROLE UNASSUMABLE
SCHEMA/TABLE/COLUMN/FUNCTION ACL CLEAN != FUTURE C2 ROLE MAPPING
PRIVILEGE REVALIDATION PASS != RUNTIME DATABASE AUTHORITY
```

## Falsification

The observer-only validator and Wave 1 tests must fail when any of the following is removed or redirected:

- `pg_attribute` as the column privilege catalog;
- `a.attrelid = v_table`;
- live user-column bounds (`attnum > 0` and `NOT attisdropped`);
- `a.attacl` as the ACL source;
- the non-owner grantee predicate;
- the explicit exception for residual non-owner column privileges;
- recursive `pg_auth_members` traversal for the migration-owner role;
- recursive `pg_auth_members` traversal for both `pg_read_all_data` and `pg_write_all_data`;
- either predefined all-data role from the starting role set;
- the non-owner predicate on predefined-role reachability.

Comment text cannot satisfy these executable invariants because privilege validation runs on comment-stripped SQL.

Any later C2 role mapping is a separate reviewed decision and may grant only the exact least-privilege capability accepted for the chosen runtime/database mechanism. It cannot rely on historical residual ACLs or predefined-role membership as an implementation shortcut.