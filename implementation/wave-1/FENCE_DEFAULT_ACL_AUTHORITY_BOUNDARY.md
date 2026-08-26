# Wave 1 — Fence Default ACL Creation Authority Boundary

This record owns the PostgreSQL creation-time privilege class exposed by posterior review of the Wave 1 IR-D-003 fence substrate. It grants no runtime/database privilege, selects no C2 role mapping, and does not weaken the existing fresh/reuse admission boundaries.

## Default ACL is creation-time authority

PostgreSQL object-level revocation after `CREATE` is not sufficient proof that a freshly materialized authority object never inherited a grant to another principal. Migration-owner `pg_default_acl` state can grant schema, relation or function privileges to PUBLIC or named roles at creation time.

For fresh bootstrap, migration 001 therefore performs both sides of the proof inside the same transaction:

1. **pre-create default-ACL admission** — before the first persistent `CREATE`, the migration authority's applicable global default ACL entries for schema/relation/function object classes are inspected through `pg_catalog.pg_default_acl` + `pg_catalog.aclexplode`; any grantee other than the default-ACL owner fails closed;
2. **post-create materialized-ACL assertion** — after schema/table/functions exist and explicit PUBLIC revocations have executed, the concrete namespace/table/column/function ACLs are re-read from the catalogs; any non-owner/PUBLIC authority fails closed before `COMMIT`.

These are deliberately independent checks. Default configuration intent is not proof of the resulting object ACL, and a clean resulting object does not justify ignoring unsafe creation-time defaults.

```text
PUBLIC REVOKED != NONOWNER DEFAULT ACL ABSENT
DEFAULT ACL PREFLIGHT != MATERIALIZED OBJECT ACL PROOF
MATERIALIZED OBJECT ACL CLEAN != DEFAULT ACL SAFE FOR FUTURE CREATE
CREATE SUCCEEDED != AUTHORITY ADMISSIBLE
```

## Fresh bootstrap privilege reachability

Fresh-object ACL checks also cannot prove that the migration owner is unreachable through role membership or that PostgreSQL's predefined all-data roles cannot immediately reach the newly created table. Likewise, a migration-owner `SECURITY DEFINER` routine anywhere in the database is residual owner authority independent of the new object's direct ACL.

Before the first persistent `CREATE`, migration 001 therefore also rejects:

- any direct or transitive `pg_auth_members` path into the current migration-owner role;
- any non-owner principal that can reach `pg_read_all_data` or `pg_write_all_data` through direct or transitive membership;
- any database-wide routine owned by the migration authority with `prosecdef=true`.

This mirrors the reuse privilege model **before** bootstrap can commit the first authority object, rather than relying on migration 002/003 to detect exposure later.

```text
OBJECT ACL CLEAN != OWNER ROLE UNASSUMABLE
OBJECT ACL CLEAN != PREDEFINED ALL-DATA AUTHORITY ABSENT
SCHEMA LOCATION != DEFINER AUTHORITY BOUNDARY
POST-BOOTSTRAP REJECTION != FAIL-CLOSED BOOTSTRAP
```

## Reuse requires a complete canonical routine set

Migration 002 is reuse admission, not repair/bootstrap. If the reused schema/table exists but either canonical fence routine is absent, the object set is incomplete and reuse fails closed before structural mutation.

This deliberately prevents `CREATE OR REPLACE FUNCTION` from degenerating into a new `CREATE` under unknown/default ACL state. Missing canonical routines require a separately governed repair/bootstrap path rather than silent privilege-bearing object creation during reuse.

After canonical `CREATE OR REPLACE` of the already-existing routines and explicit PUBLIC revocation, migration 002 re-reads both routine ACLs, owner, `SECURITY INVOKER` state and exact `search_path=pg_catalog` before the same transaction may commit.

```text
MISSING REUSE ROUTINE != SAFE CREATE OR REPLACE
PREEXISTING ROUTINE ACL CLEAN != POSTCANONICAL ROUTINE ACL CLEAN
PRE-CREATE DEFAULT ACL CHECK != POST-CREATE ACL ASSERTION
REUSE REPAIR != REUSE ADMISSION
```

## Mandatory catalog anchors

The executable proof is bound to:

```text
pg_catalog.pg_default_acl
pg_catalog.aclexplode
pg_default_acl.defaclrole
pg_default_acl.defaclnamespace
pg_default_acl.defaclobjtype
pg_catalog.pg_auth_members
pg_catalog.to_regrole('pg_read_all_data')
pg_catalog.to_regrole('pg_write_all_data')
pg_namespace.nspacl
pg_class.relacl
pg_attribute.attacl
pg_proc.proacl
pg_proc.proowner
pg_proc.prosecdef
pg_proc.proconfig
```

Replacing these with comments, unqualified lookups, a single PUBLIC-only check, or an object-name heuristic is not evidence.

## Mandatory falsification

Observer-only assurance SHALL fail when any of these conditions is introduced:

- fresh bootstrap stops inspecting the migration owner's applicable global `pg_default_acl` rows before first persistent object creation;
- schema/relation/function object-type coverage is narrowed so one created authority class can inherit an unchecked custom grant;
- the default-ACL owner binding or non-owner grantee predicate is removed/inverted;
- fresh bootstrap permits direct/transitive membership into the migration-owner role before authority object creation;
- fresh bootstrap permits a non-owner principal to reach `pg_read_all_data` or `pg_write_all_data` before authority object creation;
- fresh bootstrap permits any migration-owner `SECURITY DEFINER` routine to survive before the new fence objects are created;
- fresh bootstrap omits its materialized schema/table/column/function ACL assertion before commit;
- PUBLIC revocation is represented as proof that named-role default grants are absent;
- reuse accepts a missing initialize or advance routine and allows canonicalization to create it;
- reuse omits its post-canonical routine ACL/owner/SECURITY INVOKER/search-path assertion before commit;
- any positive runtime GRANT is introduced as part of this boundary.

Comment text is not evidence; validators inspect comment-stripped executable SQL.

## Scope boundary

The selected production role hierarchy, database product/topology, pooler, connection mechanism, migration executor and runtime grant mapping remain C2/C3 decisions under existing governance.

```text
DEFAULT ACL CLEAN != C2 RUNTIME ROLE MAPPING SELECTED
FENCE PRIVILEGE PROOF != SERVING PRINCIPAL AUTHORITY
WAVE 1 HARDENING != WAVE 2 AUTHORIZATION
CI GREEN != MERGE AUTHORIZATION
```
