-- Wave 1 IR-D-003 hardening for migration/replay safety.
--
-- Migration 001 is fresh-bootstrap-only. Reused authority admission is owned here.
-- This migration is one transaction: event-trigger/search-path guards, ACCESS EXCLUSIVE
-- lock, privilege/reachability preflight, structural/hidden-writer preflight, canonical
-- mutation, and commit. A failed reuse admission therefore cannot durably mutate the
-- authority namespace before privilege or structural conformance is proven.

BEGIN;

SET LOCAL event_triggers = off;
SET LOCAL search_path = pg_catalog;

SELECT 1 / CASE
    WHEN pg_catalog.current_setting('event_triggers') IS DISTINCT FROM 'off' THEN 0
    WHEN EXISTS (
        SELECT 1
          FROM pg_catalog.pg_event_trigger et
         WHERE et.evtenabled OPERATOR(pg_catalog.<>) 'D'
    ) THEN 0
    ELSE 1
END AS wave1_event_trigger_guard;

LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;

-- Privilege/reachability admission is part of this same reuse transaction and runs
-- before any ALTER/REVOKE/COMMENT/CREATE OR REPLACE mutation below. Migration 003
-- repeats this boundary independently as a post-canonicalization pre-C2 assertion.
DO $wave1_reuse_privilege_preflight$
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
    IF v_schema IS NULL OR v_table IS NULL THEN
        RAISE EXCEPTION 'Wave 1 reused fence privilege objects are incomplete';
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
        SELECT 1 FROM owner_role_members
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

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.proowner OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid
           AND p.prosecdef
    ) THEN
        RAISE EXCEPTION 'database contains migration-owner SECURITY DEFINER routine';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.proowner OPERATOR(pg_catalog.<>) current_user::pg_catalog.regrole::oid
    ) THEN
        RAISE EXCEPTION 'pre-existing fence authority function is not owned by the current migration authority';
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
        RAISE EXCEPTION 'pre-existing fence authority function has inherited non-owner privileges';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.prosecdef
    ) THEN
        RAISE EXCEPTION 'pre-existing fence authority function must remain SECURITY INVOKER';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_proc p
         WHERE p.oid IN (v_initialize::oid, v_advance::oid)
           AND p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[]
    ) THEN
        RAISE EXCEPTION 'pre-existing fence authority functions must retain exact pg_catalog-only search_path';
    END IF;
END
$wave1_reuse_privilege_preflight$;

-- Existing persisted authority is structurally validated before any mutation.
DO $wave1_revalidate$
DECLARE
    v_table pg_catalog.regclass := pg_catalog.to_regclass('platform.authority_fences');
    v_pk_index oid;
    v_btree_am oid;
    v_text_btree_opclass oid;
BEGIN
    IF v_table IS NULL THEN
        RAISE EXCEPTION 'platform.authority_fences is absent; apply 001 before revalidation';
    END IF;

    SELECT am.oid
      INTO v_btree_am
      FROM pg_catalog.pg_am am
     WHERE am.amname OPERATOR(pg_catalog.=) 'btree';

    SELECT opc.oid
      INTO v_text_btree_opclass
      FROM pg_catalog.pg_opclass opc
     WHERE opc.opcnamespace OPERATOR(pg_catalog.=) 'pg_catalog'::pg_catalog.regnamespace
       AND opc.opcmethod OPERATOR(pg_catalog.=) v_btree_am
       AND opc.opcname OPERATOR(pg_catalog.=) 'text_ops'
       AND opc.opcintype OPERATOR(pg_catalog.=) 'text'::pg_catalog.regtype
       AND opc.opcdefault;

    IF v_btree_am IS NULL OR v_text_btree_opclass IS NULL THEN
        RAISE EXCEPTION 'canonical pg_catalog btree text_ops authority is unavailable';
    END IF;

    IF (
        SELECT ROW(relkind, relpersistence, relispartition, relrowsecurity, relforcerowsecurity)
          FROM pg_catalog.pg_class
         WHERE oid OPERATOR(pg_catalog.=) v_table
    ) IS DISTINCT FROM ROW('r'::"char", 'p'::"char", false, false, false) THEN
        RAISE EXCEPTION 'authority_fences must be an ordinary permanent logged table without partition/RLS semantics';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_inherits
         WHERE inhrelid OPERATOR(pg_catalog.=) v_table
            OR inhparent OPERATOR(pg_catalog.=) v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot inherit from or parent another relation';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_policy
         WHERE polrelid OPERATOR(pg_catalog.=) v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot carry row-security policies';
    END IF;

    IF (
        SELECT pg_catalog.array_agg(attname::text ORDER BY attnum)
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
    ) IS DISTINCT FROM ARRAY[
        'fence_scope_id','current_fence_epoch','current_generation_id','authority_state','updated_at'
    ]::text[] THEN
        RAISE EXCEPTION 'authority_fences must expose exactly the canonical Wave 1 column set and order';
    END IF;

    IF (
        SELECT atttypid FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'fence_scope_id'
           AND attnum OPERATOR(pg_catalog.>) 0 AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.fence_scope_id must be text';
    END IF;

    IF (
        SELECT atttypid FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'current_fence_epoch'
           AND attnum OPERATOR(pg_catalog.>) 0 AND NOT attisdropped
    ) IS DISTINCT FROM 'int8'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.current_fence_epoch must be bigint';
    END IF;

    IF (
        SELECT atttypid FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'current_generation_id'
           AND attnum OPERATOR(pg_catalog.>) 0 AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.current_generation_id must be text';
    END IF;

    IF (
        SELECT atttypid FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'authority_state'
           AND attnum OPERATOR(pg_catalog.>) 0 AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.authority_state must be text';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
           AND attname IN ('fence_scope_id','current_generation_id','authority_state')
           AND attcollation IS DISTINCT FROM 'pg_catalog."C"'::pg_catalog.regcollation
    ) THEN
        RAISE EXCEPTION 'authority_fences canonical text authority columns must use pg_catalog.C collation';
    END IF;

    IF (
        SELECT atttypid FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'updated_at'
           AND attnum OPERATOR(pg_catalog.>) 0 AND NOT attisdropped
    ) IS DISTINCT FROM 'timestamptz'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.updated_at must be timestamptz';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attnum OPERATOR(pg_catalog.>) 0 AND NOT attisdropped
           AND (attgenerated OPERATOR(pg_catalog.<>) '' OR attidentity OPERATOR(pg_catalog.<>) '')
    ) THEN
        RAISE EXCEPTION 'authority_fences columns cannot be generated or identity columns';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attrdef d
          JOIN pg_catalog.pg_attribute a
            ON a.attrelid OPERATOR(pg_catalog.=) d.adrelid
           AND a.attnum OPERATOR(pg_catalog.=) d.adnum
         WHERE d.adrelid OPERATOR(pg_catalog.=) v_table
           AND a.attname OPERATOR(pg_catalog.<>) 'updated_at'
    ) THEN
        RAISE EXCEPTION 'authority_fences authority columns cannot inherit unreviewed defaults';
    END IF;

    IF (
        SELECT pg_catalog.pg_get_expr(d.adbin, d.adrelid)
          FROM pg_catalog.pg_attrdef d
          JOIN pg_catalog.pg_attribute a
            ON a.attrelid OPERATOR(pg_catalog.=) d.adrelid
           AND a.attnum OPERATOR(pg_catalog.=) d.adnum
         WHERE d.adrelid OPERATOR(pg_catalog.=) v_table
           AND a.attname OPERATOR(pg_catalog.=) 'updated_at'
    ) IS DISTINCT FROM 'statement_timestamp()' THEN
        RAISE EXCEPTION 'authority_fences.updated_at must retain the canonical statement_timestamp() evidence default';
    END IF;

    IF (
        SELECT pg_catalog.array_agg(conname::text ORDER BY conname)
          FROM pg_catalog.pg_constraint
         WHERE conrelid OPERATOR(pg_catalog.=) v_table
    ) IS DISTINCT FROM ARRAY[
        'wave1_authority_fences_pkey',
        'wave1_fence_epoch_positive',
        'wave1_fence_generation_canonical',
        'wave1_fence_scope_id_canonical',
        'wave1_fence_state_canonical'
    ]::text[] THEN
        RAISE EXCEPTION 'authority_fences contains noncanonical or missing write constraints';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint
         WHERE conrelid OPERATOR(pg_catalog.=) v_table
           AND conname IN ('wave1_fence_epoch_positive','wave1_fence_generation_canonical','wave1_fence_scope_id_canonical','wave1_fence_state_canonical')
           AND (contype OPERATOR(pg_catalog.<>) 'c' OR NOT convalidated)
    ) THEN
        RAISE EXCEPTION 'authority_fences canonical CHECK constraints must be validated CHECK constraints';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint c
          JOIN pg_catalog.pg_depend d
            ON d.classid OPERATOR(pg_catalog.=) 'pg_catalog.pg_constraint'::pg_catalog.regclass
           AND d.objid OPERATOR(pg_catalog.=) c.oid
          LEFT JOIN pg_catalog.pg_proc p
            ON d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_proc'::pg_catalog.regclass
           AND p.oid OPERATOR(pg_catalog.=) d.refobjid
          LEFT JOIN pg_catalog.pg_operator o
            ON d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_operator'::pg_catalog.regclass
           AND o.oid OPERATOR(pg_catalog.=) d.refobjid
         WHERE c.conrelid OPERATOR(pg_catalog.=) v_table
           AND c.conname IN ('wave1_fence_epoch_positive','wave1_fence_generation_canonical','wave1_fence_scope_id_canonical','wave1_fence_state_canonical')
           AND (
               (d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_proc'::pg_catalog.regclass AND p.pronamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace)
               OR (d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_operator'::pg_catalog.regclass AND o.oprnamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace)
               OR (d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_collation'::pg_catalog.regclass AND d.refobjid OPERATOR(pg_catalog.<>) 'pg_catalog."C"'::pg_catalog.regcollation)
           )
    ) THEN
        RAISE EXCEPTION 'authority_fences CHECK expression depends on noncanonical function/operator/collation authority';
    END IF;

    SELECT c.conindid
      INTO v_pk_index
      FROM pg_catalog.pg_constraint c
      JOIN pg_catalog.pg_attribute a
        ON a.attrelid OPERATOR(pg_catalog.=) c.conrelid
       AND a.attname OPERATOR(pg_catalog.=) 'fence_scope_id'
       AND a.attnum OPERATOR(pg_catalog.>) 0
       AND NOT a.attisdropped
      JOIN pg_catalog.pg_index i
        ON i.indexrelid OPERATOR(pg_catalog.=) c.conindid
      JOIN pg_catalog.pg_class index_class
        ON index_class.oid OPERATOR(pg_catalog.=) i.indexrelid
     WHERE c.conrelid OPERATOR(pg_catalog.=) v_table
       AND c.conname OPERATOR(pg_catalog.=) 'wave1_authority_fences_pkey'
       AND c.contype OPERATOR(pg_catalog.=) 'p'
       AND c.conkey OPERATOR(pg_catalog.=) ARRAY[a.attnum]::smallint[]
       AND NOT c.condeferrable
       AND NOT c.condeferred
       AND c.convalidated
       AND i.indisprimary
       AND i.indisunique
       AND i.indimmediate
       AND i.indisvalid
       AND i.indisready
       AND i.indislive
       AND i.indnkeyatts OPERATOR(pg_catalog.=) 1
       AND i.indnatts OPERATOR(pg_catalog.=) 1
       AND i.indexprs IS NULL
       AND i.indpred IS NULL
       AND index_class.relam OPERATOR(pg_catalog.=) v_btree_am
       AND i.indcollation[0] OPERATOR(pg_catalog.=) 'pg_catalog."C"'::pg_catalog.regcollation::oid
       AND i.indclass[0] OPERATOR(pg_catalog.=) v_text_btree_opclass;

    IF v_pk_index IS NULL THEN
        RAISE EXCEPTION 'authority_fences primary key must be the canonical C-collated btree text_ops immediate valid ready conflict arbiter on fence_scope_id';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_index i
         WHERE i.indrelid OPERATOR(pg_catalog.=) v_table
           AND i.indexrelid OPERATOR(pg_catalog.<>) v_pk_index
    ) THEN
        RAISE EXCEPTION 'authority_fences contains noncanonical index metadata';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_constraint c
         WHERE c.contype OPERATOR(pg_catalog.=) 'f'
           AND (c.conrelid OPERATOR(pg_catalog.=) v_table OR c.confrelid OPERATOR(pg_catalog.=) v_table)
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot participate in foreign-key referential actions';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_trigger t
         WHERE t.tgrelid OPERATOR(pg_catalog.=) v_table
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'authority_fences has unexpected non-internal trigger behavior';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_rewrite r
         WHERE r.ev_class OPERATOR(pg_catalog.=) v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences has unexpected rewrite rule behavior';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_rewrite r
          JOIN pg_catalog.pg_depend d
            ON d.classid OPERATOR(pg_catalog.=) 'pg_catalog.pg_rewrite'::pg_catalog.regclass
           AND d.objid OPERATOR(pg_catalog.=) r.oid
           AND d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_class'::pg_catalog.regclass
           AND d.refobjid OPERATOR(pg_catalog.=) v_table
         WHERE r.ev_class OPERATOR(pg_catalog.<>) v_table
    ) THEN
        RAISE EXCEPTION 'external rewrite dependency can reach authority_fences';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_subscription_rel sr
         WHERE sr.srrelid OPERATOR(pg_catalog.=) v_table
    ) THEN
        RAISE EXCEPTION 'logical replication subscription can write authority_fences';
    END IF;
END
$wave1_revalidate$;

ALTER TABLE platform.authority_fences
    ALTER COLUMN fence_scope_id SET NOT NULL,
    ALTER COLUMN current_fence_epoch SET NOT NULL,
    ALTER COLUMN current_generation_id SET NOT NULL,
    ALTER COLUMN authority_state SET NOT NULL,
    ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE platform.authority_fences
    DROP CONSTRAINT wave1_fence_scope_id_canonical,
    DROP CONSTRAINT wave1_fence_epoch_positive,
    DROP CONSTRAINT wave1_fence_generation_canonical,
    DROP CONSTRAINT wave1_fence_state_canonical;

ALTER TABLE platform.authority_fences
    ADD CONSTRAINT wave1_fence_scope_id_canonical
        CHECK (
            pg_catalog.btrim(fence_scope_id) OPERATOR(pg_catalog.<>) ''
            AND fence_scope_id COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ) NOT VALID,
    ADD CONSTRAINT wave1_fence_epoch_positive
        CHECK (current_fence_epoch OPERATOR(pg_catalog.>) 0) NOT VALID,
    ADD CONSTRAINT wave1_fence_generation_canonical
        CHECK (
            pg_catalog.btrim(current_generation_id) OPERATOR(pg_catalog.<>) ''
            AND current_generation_id COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ) NOT VALID,
    ADD CONSTRAINT wave1_fence_state_canonical
        CHECK (
            pg_catalog.btrim(authority_state) OPERATOR(pg_catalog.<>) ''
            AND authority_state COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ) NOT VALID;

ALTER TABLE platform.authority_fences VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;
ALTER TABLE platform.authority_fences VALIDATE CONSTRAINT wave1_fence_epoch_positive;
ALTER TABLE platform.authority_fences VALIDATE CONSTRAINT wave1_fence_generation_canonical;
ALTER TABLE platform.authority_fences VALIDATE CONSTRAINT wave1_fence_state_canonical;

REVOKE CREATE ON SCHEMA platform FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE ALL ON TABLE platform.authority_fences FROM PUBLIC;

COMMENT ON TABLE platform.authority_fences IS
'IR-D-003 scope-local monotonic fencing authority. Wall clock and process identity are evidence only.';
COMMENT ON COLUMN platform.authority_fences.current_fence_epoch IS
'Positive signed BIGINT; no wrap, reset or reuse semantics.';

CREATE OR REPLACE FUNCTION platform.initialize_authority_fence(
    p_fence_scope_id text,
    p_generation_id text,
    p_authority_state text
)
RETURNS TABLE (
    fence_scope_id text,
    current_fence_epoch bigint,
    current_generation_id text,
    authority_state text
)
LANGUAGE sql
SECURITY INVOKER
SET search_path = pg_catalog
AS $wave1_function$
    INSERT INTO platform.authority_fences (
        fence_scope_id,
        current_fence_epoch,
        current_generation_id,
        authority_state
    ) VALUES (p_fence_scope_id,1,p_generation_id,p_authority_state)
    ON CONFLICT (fence_scope_id) DO NOTHING
    RETURNING authority_fences.fence_scope_id,
              authority_fences.current_fence_epoch,
              authority_fences.current_generation_id,
              authority_fences.authority_state;
$wave1_function$;

REVOKE ALL ON FUNCTION platform.initialize_authority_fence(text, text, text) FROM PUBLIC;

CREATE OR REPLACE FUNCTION platform.advance_authority_fence(
    p_fence_scope_id text,
    p_expected_predecessor_epoch bigint,
    p_expected_predecessor_generation_id text,
    p_successor_generation_id text,
    p_successor_state text
)
RETURNS TABLE (
    fence_scope_id text,
    current_fence_epoch bigint,
    current_generation_id text,
    authority_state text
)
LANGUAGE sql
SECURITY INVOKER
SET search_path = pg_catalog
AS $wave1_function$
    UPDATE platform.authority_fences
       SET current_fence_epoch = current_fence_epoch OPERATOR(pg_catalog.+) 1,
           current_generation_id = p_successor_generation_id,
           authority_state = p_successor_state,
           updated_at = pg_catalog.statement_timestamp()
     WHERE authority_fences.fence_scope_id COLLATE "C" OPERATOR(pg_catalog.=) p_fence_scope_id COLLATE "C"
       AND authority_fences.current_fence_epoch OPERATOR(pg_catalog.=) p_expected_predecessor_epoch
       AND authority_fences.current_generation_id COLLATE "C" OPERATOR(pg_catalog.=) p_expected_predecessor_generation_id COLLATE "C"
       AND authority_fences.authority_state COLLATE "C" OPERATOR(pg_catalog.=) 'active' COLLATE "C"
       AND authority_fences.current_fence_epoch OPERATOR(pg_catalog.<) 9223372036854775807
       AND pg_catalog.btrim(p_expected_predecessor_generation_id) OPERATOR(pg_catalog.<>) ''
       AND pg_catalog.btrim(p_successor_generation_id) OPERATOR(pg_catalog.<>) ''
       AND pg_catalog.btrim(p_successor_state) OPERATOR(pg_catalog.<>) ''
       AND p_expected_predecessor_generation_id COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
       AND p_successor_generation_id COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
       AND p_successor_state COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    RETURNING authority_fences.fence_scope_id,
              authority_fences.current_fence_epoch,
              authority_fences.current_generation_id,
              authority_fences.authority_state;
$wave1_function$;

REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text, text) FROM PUBLIC;

-- No positive GRANT follows this validation. The separately reviewed C2 runtime/
-- database mapping remains responsible for least-privilege capability assignment.

COMMIT;
