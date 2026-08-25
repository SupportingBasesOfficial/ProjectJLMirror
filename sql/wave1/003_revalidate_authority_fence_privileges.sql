-- Wave 1 IR-D-003 privilege-boundary revalidation.
--
-- Reusing an existing schema/table/function name is not privilege conformance.
-- This migration runs before any separately reviewed C2 runtime/database grants.
-- It proves that the migration authority owns the fence objects, that no other
-- role retains direct object or column authority, that no transitive role-membership
-- path can assume/inherit the migration-owner authority, that no non-owner role
-- can reach PostgreSQL predefined all-data authority, and that no migration-owner
-- SECURITY DEFINER routine survives anywhere in the database before C2 role mapping.
-- It does not choose role names or grant serving/runtime authority.

DO $$
DECLARE
    v_schema oid := to_regnamespace('platform');
    v_table regclass := to_regclass('platform.authority_fences');
    v_initialize regprocedure := to_regprocedure(
        'platform.initialize_authority_fence(text,text,text)'
    );
    v_advance regprocedure := to_regprocedure(
        'platform.advance_authority_fence(text,bigint,text,text,text)'
    );
BEGIN
    IF v_schema IS NULL OR v_table IS NULL OR v_initialize IS NULL OR v_advance IS NULL THEN
        RAISE EXCEPTION 'Wave 1 fence privilege objects are incomplete; apply 001/002 first';
    END IF;

    IF (
        SELECT n.nspowner
          FROM pg_namespace n
         WHERE n.oid = v_schema
    ) IS DISTINCT FROM current_user::regrole::oid THEN
        RAISE EXCEPTION 'platform schema is not owned by the current migration authority';
    END IF;

    IF (
        SELECT c.relowner
          FROM pg_class c
         WHERE c.oid = v_table
    ) IS DISTINCT FROM current_user::regrole::oid THEN
        RAISE EXCEPTION 'authority_fences is not owned by the current migration authority';
    END IF;

    IF EXISTS (
        WITH RECURSIVE owner_role_members(member_oid) AS (
            SELECT m.member
              FROM pg_auth_members m
             WHERE m.roleid = current_user::regrole::oid
            UNION
            SELECT m.member
              FROM pg_auth_members m
              JOIN owner_role_members r
                ON m.roleid = r.member_oid
        )
        SELECT 1
          FROM owner_role_members
    ) THEN
        RAISE EXCEPTION 'current migration authority owner role is reachable through role membership';
    END IF;

    IF EXISTS (
        WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (
            SELECT m.roleid, m.member
              FROM pg_auth_members m
             WHERE m.roleid IN (
                to_regrole('pg_read_all_data')::oid,
                to_regrole('pg_write_all_data')::oid
             )
            UNION
            SELECT r.role_oid, m.member
              FROM pg_auth_members m
              JOIN all_data_role_members r
                ON m.roleid = r.member_oid
        )
        SELECT 1
          FROM all_data_role_members
         WHERE member_oid <> current_user::regrole::oid
    ) THEN
        RAISE EXCEPTION 'non-owner role can reach PostgreSQL predefined all-data authority';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          CROSS JOIN LATERAL aclexplode(
              COALESCE(c.relacl, acldefault('r', c.relowner))
          ) AS acl
         WHERE c.oid = v_table
           AND acl.grantee <> c.relowner
    ) THEN
        RAISE EXCEPTION 'authority_fences has inherited non-owner table privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_attribute a
          CROSS JOIN LATERAL aclexplode(a.attacl) AS acl
         WHERE a.attrelid = v_table
           AND a.attnum > 0
           AND NOT a.attisdropped
           AND a.attacl IS NOT NULL
           AND acl.grantee <> current_user::regrole::oid
    ) THEN
        RAISE EXCEPTION 'authority_fences has inherited non-owner column privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_namespace n
          CROSS JOIN LATERAL aclexplode(
              COALESCE(n.nspacl, acldefault('n', n.nspowner))
          ) AS acl
         WHERE n.oid = v_schema
           AND acl.grantee <> n.nspowner
    ) THEN
        RAISE EXCEPTION 'platform schema has inherited non-owner privileges';
    END IF;

    -- Schema placement, current EXECUTE ACLs and static routine-body inspection are
    -- not sufficient authority boundaries. A migration-owner SECURITY DEFINER can
    -- be reached indirectly (for example through a trigger) or become reachable
    -- after a later grant while still carrying owner-level authority. The pre-C2
    -- boundary therefore rejects every SECURITY DEFINER routine owned by the current
    -- migration authority anywhere in this database. Any future definer is an
    -- explicit reviewed C2/privileged-authority decision, never historical residue.
    IF EXISTS (
        SELECT 1
          FROM pg_proc p
         WHERE p.proowner = current_user::regrole::oid
           AND p.prosecdef
    ) THEN
        RAISE EXCEPTION 'database contains migration-owner SECURITY DEFINER routine';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.proowner <> current_user::regrole::oid
    ) THEN
        RAISE EXCEPTION 'fence authority function is not owned by the current migration authority';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
          CROSS JOIN LATERAL aclexplode(
              COALESCE(p.proacl, acldefault('f', p.proowner))
          ) AS acl
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND acl.grantee <> p.proowner
    ) THEN
        RAISE EXCEPTION 'fence authority function has inherited non-owner privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.prosecdef
    ) THEN
        RAISE EXCEPTION 'fence authority function must remain SECURITY INVOKER';
    END IF;
END
$$;

-- No GRANT follows this validation. A later reviewed C2 role mapping must grant
-- only the exact least-privilege capability required by the selected runtime and
-- must not grant direct serving-role mutation of platform.authority_fences.