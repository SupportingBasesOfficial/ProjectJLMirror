-- Wave 1 IR-D-003 hardening for migration/replay safety.
--
-- Migration 001 is fresh-bootstrap-only when platform.authority_fences is absent.
-- If the table already exists, 001 performs no persistent authority-object mutation;
-- this migration owns reuse validation. It takes an ACCESS EXCLUSIVE lock, proves
-- the complete reusable table contract, rejects hidden mutation/dependency surfaces,
-- and only then canonicalizes constraints/functions inside the same transaction.
--
-- This file is deliberately self-transactional. Event-trigger execution is disabled
-- transaction-locally before DDL and search_path is pinned to pg_catalog so writable
-- schemas cannot shadow catalog functions/operators during validation or canonical DDL.

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

-- Existing persisted authority is validated before any mutation in this transaction.
DO $wave1_revalidate$
DECLARE
    v_table pg_catalog.regclass := pg_catalog.to_regclass('platform.authority_fences');
    v_pk_index oid;
BEGIN
    IF v_table IS NULL THEN
        RAISE EXCEPTION 'platform.authority_fences is absent; apply 001 before revalidation';
    END IF;

    IF (
        SELECT ROW(relkind, relpersistence, relispartition, relrowsecurity, relforcerowsecurity)
          FROM pg_catalog.pg_class
         WHERE oid OPERATOR(pg_catalog.=) v_table
    ) IS DISTINCT FROM ROW('r'::"char", 'p'::"char", false, false, false) THEN
        RAISE EXCEPTION 'authority_fences must be an ordinary permanent logged table without partition/RLS semantics';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_inherits
         WHERE inhrelid OPERATOR(pg_catalog.=) v_table
            OR inhparent OPERATOR(pg_catalog.=) v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot inherit from or parent another relation';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_policy
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
        'fence_scope_id',
        'current_fence_epoch',
        'current_generation_id',
        'authority_state',
        'updated_at'
    ]::text[] THEN
        RAISE EXCEPTION 'authority_fences must expose exactly the canonical Wave 1 column set and order';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'fence_scope_id'
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.fence_scope_id must be text';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'current_fence_epoch'
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'int8'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.current_fence_epoch must be bigint';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'current_generation_id'
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.current_generation_id must be text';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'authority_state'
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.authority_state must be text';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
           AND attname IN ('fence_scope_id', 'current_generation_id', 'authority_state')
           AND attcollation IS DISTINCT FROM 'pg_catalog."C"'::pg_catalog.regcollation
    ) THEN
        RAISE EXCEPTION 'authority_fences canonical text authority columns must use pg_catalog.C collation';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attname OPERATOR(pg_catalog.=) 'updated_at'
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'timestamptz'::pg_catalog.regtype THEN
        RAISE EXCEPTION 'authority_fences.updated_at must be timestamptz';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_attribute
         WHERE attrelid OPERATOR(pg_catalog.=) v_table
           AND attnum OPERATOR(pg_catalog.>) 0
           AND NOT attisdropped
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
        SELECT 1
          FROM pg_catalog.pg_constraint
         WHERE conrelid OPERATOR(pg_catalog.=) v_table
           AND conname IN (
               'wave1_fence_epoch_positive',
               'wave1_fence_generation_canonical',
               'wave1_fence_scope_id_canonical',
               'wave1_fence_state_canonical'
           )
           AND (contype OPERATOR(pg_catalog.<>) 'c' OR NOT convalidated)
    ) THEN
        RAISE EXCEPTION 'authority_fences canonical CHECK constraints must be validated CHECK constraints';
    END IF;

    -- Stored CHECK expressions must depend only on catalog operators/functions and
    -- the exact C collation. An attacker-owned overload in a writable schema cannot
    -- be grandfathered into authority semantics merely because names/types look right.
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
           AND c.conname IN (
               'wave1_fence_epoch_positive',
               'wave1_fence_generation_canonical',
               'wave1_fence_scope_id_canonical',
               'wave1_fence_state_canonical'
           )
           AND (
               (d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_proc'::pg_catalog.regclass
                AND p.pronamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace)
               OR
               (d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_operator'::pg_catalog.regclass
                AND o.oprnamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace)
               OR
               (d.refclassid OPERATOR(pg_catalog.=) 'pg_catalog.pg_collation'::pg_catalog.regclass
                AND d.refobjid OPERATOR(pg_catalog.<>) 'pg_catalog."C"'::pg_catalog.regcollation)
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
       AND i.indpred IS NULL;

    IF v_pk_index IS NULL THEN
        RAISE EXCEPTION 'authority_fences primary key must be the canonical single-column immediate valid ready conflict arbiter on fence_scope_id';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_index i
         WHERE i.indrelid OPERATOR(pg_catalog.=) v_table
           AND i.indexrelid OPERATOR(pg_catalog.<>) v_pk_index
    ) THEN
        RAISE EXCEPTION 'authority_fences contains noncanonical index metadata';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_constraint c
         WHERE c.contype OPERATOR(pg_catalog.=) 'f'
           AND (c.conrelid OPERATOR(pg_catalog.=) v_table OR c.confrelid OPERATOR(pg_catalog.=) v_table)
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot participate in foreign-key referential actions';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_trigger t
         WHERE t.tgrelid OPERATOR(pg_catalog.=) v_table
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'authority_fences has unexpected non-internal trigger behavior';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_rewrite r
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
        SELECT 1
          FROM pg_catalog.pg_subscription_rel sr
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

ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;
ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_epoch_positive;
ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_generation_canonical;
ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_state_canonical;

-- Only after the existing authority relation has passed the complete preflight do
-- we canonicalize the function layer and narrowing PUBLIC/default privileges.
REVOKE CREATE ON SCHEMA platform FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
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
    ) VALUES (
        p_fence_scope_id,
        1,
        p_generation_id,
        p_authority_state
    )
    ON CONFLICT (fence_scope_id) DO NOTHING
    RETURNING
        authority_fences.fence_scope_id,
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
    RETURNING
        authority_fences.fence_scope_id,
        authority_fences.current_fence_epoch,
        authority_fences.current_generation_id,
        authority_fences.authority_state;
$wave1_function$;

REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text, text) FROM PUBLIC;

-- No positive GRANT follows this validation. The separately reviewed C2 runtime/
-- database mapping remains responsible for least-privilege capability assignment.

COMMIT;
