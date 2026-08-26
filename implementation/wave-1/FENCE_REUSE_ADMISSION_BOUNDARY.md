# Wave 1 — Fence Reuse Admission Boundary

This record extends `FENCE_PRIVILEGE_BOUNDARY.md` for the exact reuse-admission class exposed by the posterior review of the Wave 1 PostgreSQL fence substrate. It grants no runtime/database privilege and selects no residual C2 product or role mapping.

## Fresh bootstrap means complete object-set absence

Migration 001 is not allowed to infer a fresh authority namespace merely because `platform.authority_fences` is absent.

Before any persistent bootstrap mutation, it resolves all canonical pre-existing authority objects that the bootstrap could otherwise mutate or replace:

```text
pg_catalog.to_regnamespace('platform')
pg_catalog.to_regclass('platform.authority_fences')
pg_catalog.to_regprocedure('platform.initialize_authority_fence(text,text,text)')
pg_catalog.to_regprocedure('platform.advance_authority_fence(text,bigint,text,text,text)')
```

Rules:

- existing `authority_fences` routes to migration 002 reuse admission and migration 001 returns before persistent mutation;
- absent table + pre-existing `platform` schema or either canonical routine is **not** fresh bootstrap and fails closed;
- bootstrap uses `CREATE SCHEMA platform`, not `IF NOT EXISTS`, so namespace reuse cannot be silently laundered;
- no schema/default-privilege/function rewrite is performed before the complete freshness decision.

```text
TABLE ABSENT != AUTHORITY NAMESPACE FRESH
PARTIAL AUTHORITY OBJECT SET != BOOTSTRAP MUTATION ELIGIBILITY
IF NOT EXISTS != REUSE VALIDATION
```

## Reuse admission and canonical mutation are one transaction

Migration 002 owns reuse. `ACCESS EXCLUSIVE`, privilege/reachability preflight, structural/hidden-writer preflight, canonical constraint/function mutation and final `COMMIT` are one transaction.

The privilege preflight occurs before the first persistent canonical mutation and proves, at minimum:

- schema/table owner is the current migration authority;
- migration-owner role cannot be assumed through direct/transitive `pg_auth_members` reachability;
- no non-owner role can reach `pg_read_all_data` or `pg_write_all_data`;
- no non-owner/PUBLIC schema/table/column/canonical-function ACL survives;
- no migration-owner `SECURITY DEFINER` routine survives anywhere in the database;
- pre-existing canonical routines, when present, are owner-bound, SECURITY INVOKER, ACL-clean and pinned to exact `search_path=pg_catalog`.

Only after that privilege proof does structural validation run. Only after **both** proofs may migration 002 replace constraints, narrow privileges/comments or `CREATE OR REPLACE` the canonical routines.

Migration 003 remains an independent post-canonicalization/pre-C2 assertion. It is defense in depth, not the first privilege admission for reuse.

```text
STRUCTURAL REUSE PASS != PRIVILEGE REUSE ADMISSION
POST-COMMIT PRIVILEGE CHECK != FAIL-CLOSED REUSE
REUSE ADMISSION != SAFE MUTATION UNLESS PRIVILEGE+STRUCTURE SHARE THE MUTATION TRANSACTION
MIGRATION 003 PASS != LICENSE FOR MIGRATION 002 TO MUTATE BEFORE PRIVILEGE PREFLIGHT
```

## Primary-key equality authority is explicit

Column-level `text COLLATE "C"` does not prove that a reused primary-key index uses the same equality semantics.

Migration 002 therefore proves the exact conflict-arbiter semantics for `wave1_authority_fences_pkey`:

```text
access method          = pg_catalog btree
index key count        = 1
key column             = fence_scope_id
indcollation[0]        = pg_catalog."C"
indclass[0]            = canonical pg_catalog default text_ops for text/btree
indisprimary           = true
indisunique            = true
indimmediate           = true
indisvalid             = true
indisready             = true
indislive              = true
indexprs               = NULL
indpred                = NULL
```

This is required because the PK backs both uniqueness and `ON CONFLICT (fence_scope_id)`. Noncanonical index collation/opclass can alias distinct canonical scope IDs or redefine equality despite canonical column declarations and function predicates.

```text
COLUMN C COLLATION != PRIMARY-KEY C COLLATION
PRIMARY KEY SHAPE != PRIMARY-KEY OPERATOR-CLASS AUTHORITY
ON CONFLICT TARGET MATCH != CANONICAL CONFLICT EQUALITY
```

## Mandatory falsification

The observer-only Wave 1 suite SHALL fail when any of the following is introduced:

- bootstrap checks only table absence and ignores a pre-existing schema/canonical routine;
- `CREATE SCHEMA IF NOT EXISTS platform` replaces the complete freshness proof;
- privilege preflight is removed from migration 002;
- privilege preflight is moved after structural canonical mutation or after commit;
- migration 002 commits between privilege admission and structural/canonical mutation;
- owner-role, predefined all-data, schema/table/column ACL or database-wide owner-definer checks are removed from reuse preflight;
- PK access method is not the canonical catalog btree AM;
- PK `indcollation[0]` is not exact catalog `C`;
- PK `indclass[0]` is not the canonical catalog default `text_ops` opclass for text/btree;
- any of the pre-existing immediate/valid/ready/live/non-expression/non-partial conflict-arbiter predicates is weakened.

Comment text is not evidence; validators inspect comment-stripped executable SQL.

## Scope boundary

These rules harden only the accepted Wave 1 IR-D-003 authority skeleton. They do not select the concrete production database topology, pooler, runtime database role mapping, backup mechanism, orchestrator, cloud, or other C2/C3 decisions.

```text
REUSE ADMISSION CLEAN != RUNTIME DATABASE AUTHORITY
WAVE 1 HARDENING != WAVE 2 AUTHORIZATION
CI GREEN != MERGE AUTHORIZATION
```
