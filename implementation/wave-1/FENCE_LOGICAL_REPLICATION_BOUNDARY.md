# Wave 1 — Fence Logical Replication Authority Boundary

**Scope:** `impl.control-plane@1` / minimal `impl.platform-runtime@1` IR-D-003 persistence boundary only.

This record separates ordinary PostgreSQL object privileges from logical-replication writer/disclosure authority for `platform.authority_fences`.

## Canonical laws

```text
ACL CLEAN != LOGICAL REPLICATION DISCLOSURE ABSENT
INBOUND REPLICATION WRITER ABSENT != OUTBOUND PUBLICATION ABSENT
PUBLICATION CATALOG SNAPSHOT CLEAN != CONCURRENT SUPERUSER AUTHORITY ABSENT
TABLE LOCK HELD != DATABASE ADMIN AUTHORITY REVOKED
WAVE 1 REPLICATION PREFLIGHT != C2 DATABASE ROLE MAPPING
PREDICATE TOKEN PRESENCE != REACHABLE PREDICATE
DOLLAR-QUOTED TEXT != EXECUTABLE PREFLIGHT
NESTED DEAD GUARD != TOP-LEVEL PREFLIGHT
```

## Fresh bootstrap

Before the first persistent authority-object `CREATE`, migration `001_platform_authority_fence.sql` must fail closed when an existing `pg_catalog.pg_publication` has `puballtables = true`.

A `FOR ALL TABLES` publication is relevant even before `platform.authority_fences` exists because it includes future persistent tables. A later object ACL revocation does not remove publication disclosure authority.

The required `IF EXISTS ... pg_publication ... puballtables` guard is a top-level executable statement in the `wave1_bootstrap` PL/pgSQL body. Merely preserving its tokens in a comment, ordinary string, inner dollar-quoted payload, zero-iteration loop or false conditional does not satisfy the boundary.

## Reused authority admission

Inside the same transaction and while the reused fence table is held `ACCESS EXCLUSIVE`, migration `002_revalidate_authority_fence_contract.sql` must reject current catalog state when any of these applies before canonical mutation:

- inbound `pg_catalog.pg_subscription_rel` maps the fence table as a logical-replication target/writer;
- `pg_catalog.pg_publication_rel` explicitly publishes the fence table;
- any `pg_catalog.pg_publication` has `puballtables = true`;
- where the catalog exists, `pg_catalog.pg_publication_namespace` publishes the canonical `platform` namespace.

The three static reuse guards are top-level executable statements in the `wave1_revalidate` body. They cannot be nested behind an extra `IF`, `CASE`, `LOOP` or equivalent dead wrapper merely to preserve expected text.

The schema-publication lookup is version-tolerant: the migration checks for the catalog with `pg_catalog.to_regclass` before executing the catalog query. The catalog guard itself is top-level; the dynamic namespace query and its fail-closed result guard execute directly inside that one accepted version-tolerant guard. The assurance parser reconstructs the dynamic query and treats any unrelated inner dollar-quoted SQL payload as opaque data.

A top-level `RETURN` in the reused structural preflight is prohibited because it could skip publication checks while canonical `ALTER TABLE` statements after the `DO` block still execute.

## Administrative concurrency boundary

These catalog checks prove the state observed by the migration. They do **not** claim that an `ACCESS EXCLUSIVE` table lock or an application migration can revoke PostgreSQL superuser authority.

`FOR ALL TABLES` and schema publications are administrative capabilities. Preventing a concurrent privileged administrator from creating/changing publication authority is owned by the separately reviewed C2 database/admin role and operational mapping, machine-readable as `database_admin_role_and_operational_mapping`. Wave 1 does not silently select that product, role topology, or operational mechanism.

Therefore:

```text
STATIC PREFLIGHT PASS != FUTURE ADMINISTRATIVE AUTHORITY ABSENCE
```

A production implementation must bind the accepted database/admin principal segregation so that authority-changing administration cannot race or bypass the governed migration/release boundary.

## Falsification requirements

Assurance must reject at least:

- fresh bootstrap with the `pg_publication` catalog guard removed, moved after first persistent create, or with `puballtables` inverted;
- expected publication syntax retained only in comments, ordinary strings or inner dollar-quoted payloads while the real predicate is weakened;
- any required static publication guard wrapped in a false conditional, zero-iteration loop or other additional control-flow layer instead of executing top-level;
- reused explicit publication membership with wrong catalog or wrong `prrelid` predicate;
- reused all-tables publication with the predicate removed/inverted;
- reused schema publication with wrong catalog, wrong namespace target, missing `USING v_schema`, unconditional catalog access, or dynamic/result logic moved outside/directly deeper than the one accepted version-tolerant guard;
- removal of the inbound subscription-writer guard;
- a top-level reused-preflight `RETURN` bypass;
- missing transaction/commit or reused-table `ACCESS EXCLUSIVE` boundary.

These checks are conformance evidence only. They do not grant runtime/database authority and do not authorize Wave 2.
