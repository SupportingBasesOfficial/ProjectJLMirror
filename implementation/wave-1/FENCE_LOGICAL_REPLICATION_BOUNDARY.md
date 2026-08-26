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
```

## Fresh bootstrap

Before the first persistent authority-object `CREATE`, migration `001_platform_authority_fence.sql` must fail closed when an existing `pg_catalog.pg_publication` has `puballtables = true`.

A `FOR ALL TABLES` publication is relevant even before `platform.authority_fences` exists because it includes future persistent tables. A later object ACL revocation does not remove publication disclosure authority.

## Reused authority admission

Inside the same transaction and while the reused fence table is held `ACCESS EXCLUSIVE`, migration `002_revalidate_authority_fence_contract.sql` must reject current catalog state when any of these applies before canonical mutation:

- inbound `pg_catalog.pg_subscription_rel` maps the fence table as a logical-replication target/writer;
- `pg_catalog.pg_publication_rel` explicitly publishes the fence table;
- any `pg_catalog.pg_publication` has `puballtables = true`;
- where the catalog exists, `pg_catalog.pg_publication_namespace` publishes the canonical `platform` namespace.

The schema-publication lookup is version-tolerant: the migration checks for the catalog with `pg_catalog.to_regclass` before executing the catalog query.

## Administrative concurrency boundary

These catalog checks prove the state observed by the migration. They do **not** claim that an `ACCESS EXCLUSIVE` table lock or an application migration can revoke PostgreSQL superuser authority.

`FOR ALL TABLES` and schema publications are administrative capabilities. Preventing a concurrent privileged administrator from creating/changing publication authority is owned by the separately reviewed C2 database/admin role and operational mapping. Wave 1 does not silently select that product, role topology, or operational mechanism.

Therefore:

```text
STATIC PREFLIGHT PASS != FUTURE ADMINISTRATIVE AUTHORITY ABSENCE
```

A production implementation must bind the accepted database/admin principal segregation so that authority-changing administration cannot race or bypass the governed migration/release boundary.

## Falsification requirements

Assurance must reject at least:

- fresh bootstrap with the `pg_publication` catalog guard removed, moved after first persistent create, or with `puballtables` inverted;
- reused explicit publication membership with wrong catalog or wrong `prrelid` predicate;
- reused all-tables publication with the predicate removed/inverted;
- reused schema publication with wrong catalog, wrong namespace target, missing `USING v_schema`, or unconditional catalog access;
- removal of the inbound subscription-writer guard;
- publication tokens moved only into SQL comments;
- missing transaction/commit or reused-table `ACCESS EXCLUSIVE` boundary.

These checks are conformance evidence only. They do not grant runtime/database authority and do not authorize Wave 2.