-- Wave 1 IR-D-003 privilege-boundary revalidation.
--
-- Reusing an existing schema/table/function name is not privilege conformance.
-- This migration runs before any separately reviewed C2 runtime/database grants.
-- It proves that the migration authority owns the fence objects, that no other
-- role retains direct object or column authority, that no transitive role-membership
-- path can assume/inherit the migration-owner authority, that no non-owner role
-- can reach PostgreSQL predefined all-data authority, and that no SECURITY DEFINER
-- routine owned by the migration authority or either predefined all-data root role
-- survives anywhere in the database before C2 role mapping.
-- The migration search_path is fixed to pg_catalog and both canonical fence routines
-- must themselves carry the exact pg_catalog-only function search_path.

BEGIN;
SET LOCAL search_path = pg_catalog;

DO $wave1_privilege_revalidation$
DECLARE
    v_schema oid := pg_catalog.to_regnamespace('platform');
    v_table pg_catalog.regclass := pg_catalog.to_regclass('platform.authority_fences');
    v_initialize pg_catalog.regprocedure := pg_catalog.to_regprocedure(
        'platform.initialize_authority_fence(text,text,text)'
    );
    v_advance pg_catalog.regprocedure := pg_catalog.to_regprocedure(
        'platform.advance_authority_fence(text,bigint,text,text,text)'
    );
BEGIN
    IF v_schema IS NULL OR v_table IS NULL OR v_initialize IS NULL OR v_advance IS NULL THEN
        RAISE EXCEPTION 'Wave 1 fence privilege objects are incomplete; apply 001/002 first';
    END IF;

    IF (
        SELECT n.nspowner
          FROM pg_catalog.pg_namespace n
         WHERE n.oid OPERATOR(pg_catalog.=) v_schema
    ) IS DISTINCT FROM current_user::pg_catalog.regrole::oid THEN
        RAISE EXCEPTION 'platform schema is not owned by the current migration authority';
    END IF;

    IF (
        SELECT c.relowner
          FROM pg_catalog.pg_class c
         WHERE c.oid OPERATOR(pg_catalog.=) v_table
    ) IS DISTINCT FROM current_user::pg_catalog.regrole::oid THEN
        RAISE EXCEPTION 'authority_fences is not owned by the current migration authority';
    END IF;

    IF EXISTS (
        WITH RECURSIVE owner_role_members(member_oid) AS (
            SELECT m.member
              FROM pg_catalog.pg_auth_members m
             WHERE m.roleid OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid
            UNION
            SELECT m.member
              FROM pg_catalog.pg_auth_members m
              JOIN owner_role_members r
                ON m.roleid OPERATOR(pg_catalog.=) r.member_oid
        )
        SELECT 1
          FROM owner_role_members
    ) THEN
        RAISE EXCEPTION 'current migration authority owner role is reachable through role membership';
    END IF;

    IF EXISTS (
        WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (
            SELECT m.roleid, m.member
              FROM pg_catalog.pg_auth_members m
             WHERE m.roleid IN (
                pg_catalog.to_regrole('pg_read_all_data')::oid,
                pg_catalog.to_regrole('pg_write_all_data')::oid
             )
            UNION
            SELECT r.role_oid, m.member
              FROM pg_catalog.pg_auth_members m
              JOIN all_data_role_members r
                ON m.roleid OPERATOR(pg_catalog.=) r.member_oid
        )
        SELECT 1
          FROM all_data_role_members
         WHERE member_oid OPERATOR(pg_catalog.<>) current_user::pg_catalog.regrole::oid
    ) THEN
        RAISE EXCEPTION 'non-owner role can reach PostgreSQL predefined all-data authority';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_class c
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              pg_catalog.COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
          ) AS acl
         WHERE c.oid OPERATOR(pg_catalog.=) v_table
           AND acl.grantee OPERATOR(pg_catalog.<>) c.relowner
    ) THEN
        RAISE EXCEPTION 'authority_fences has inherited non-owner table privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attribute a
          CROSS JOIN LATERAL pg_catalog.aclexplode(a.attacl) AS acl
         WHERE a.attrelid OPERATOR(pg_catalog.=) v_table
           AND a.attnum OPERATOR(pg_catalog.>) 0
           AND NOT a.attisdropped
           AND a.attacl IS NOT NULL
           AND acl.grantee OPERATOR(pg_catalog.<>) current_user::pg_catalog.regrole::oid
    ) THEN
        RAISE EXCEPTION 'authority_fences has inherited non-owner column privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_namespace n
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              pg_catalog.COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))
          ) AS acl
         WHERE n.oid OPERATOR(pg_catalog.=) v_schema
           AND acl.grantee OPERATOR(pg_catalog.<>) n.nspowner
    ) THEN
        RAISE EXCEPTION 'platform schema has inherited non-owner privileges';
    END IF;

    -- Schema placement, current EXECUTE ACLs and static routine-body inspection are
    -- not sufficient authority boundaries. Reject SECURITY DEFINER routines whose
    -- owner itself carries fence-wide authority: the migration owner or either
    -- predefined all-data root role. The root roles are included explicitly because
    -- pg_auth_members closure does not emit a role as its own member.
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.proowner IN (
                   current_user::pg_catalog.regrole::oid,
                   pg_catalog.to_regrole('pg_read_all_data')::oid,
                   pg_catalog.to_regrole('pg_write_all_data')::oid
               )
           AND p.prosecdef
    ) THEN
        RAISE EXCEPTION 'database contains fence-authoritative SECURITY DEFINER routine owned by migration or predefined all-data authority';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.proowner OPERATOR(pg_catalog.<>) current_user::pg_catalog.regrole::oid
    ) THEN
        RAISE EXCEPTION 'fence authority function is not owned by the current migration authority';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              pg_catalog.COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
          ) AS acl
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND acl.grantee OPERATOR(pg_catalog.<>) p.proowner
    ) THEN
        RAISE EXCEPTION 'fence authority function has inherited non-owner privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.prosecdef
    ) THEN
        RAISE EXCEPTION 'fence authority function must remain SECURITY INVOKER';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[]
    ) THEN
        RAISE EXCEPTION 'fence authority functions must retain exact pg_catalog-only search_path';
    END IF;
END
$wave1_privilege_revalidation$;

-- No GRANT follows this validation. A later reviewed C2 role mapping must grant
-- only the exact least-privilege capability required by the selected runtime and
-- must not grant direct serving-role mutation of platform.authority_fences.

COMMIT;
