-- Wave 1 IR-D-003 hardening for migration/replay safety.
--
-- 001 may be applied into an environment where the logical schema already exists.
-- This migration makes reuse fail closed: an existing authority_fences table must
-- satisfy the canonical structural, durability, identifier, deterministic-collation,
-- conflict-arbiter, constraint/index, referential-action, rewrite-reachability-free,
-- replication-writer-free and event-trigger-execution-safe contract before Wave 1
-- can consider it eligible for authority use. Invalid historical shape/rows or hidden
-- mutation/write-constraining behavior fail; rows are not normalized, deleted, or
-- silently accepted here.
--
-- This file is deliberately self-transactional. Constraint replacement is not safe
-- under statement-by-statement autocommit because a failed later validation could
-- otherwise leave canonical checks absent or only partially replaced. The session
-- disables event-trigger execution for this transaction before any event-trigger-
-- capable DDL, and ACCESS EXCLUSIVE is acquired before structural validation and
-- retained through final COMMIT so validation/replacement share one closed mutation
-- window.

BEGIN;

-- A catalog preflight by itself has a TOCTOU window: a superuser could create or
-- enable an event trigger after the SELECT and before a later ALTER TABLE. PostgreSQL
-- provides the session-local event_triggers switch specifically to disable all event
-- trigger execution. Requiring SET LOCAL here closes the execution window for this
-- transaction; if the migration authority lacks permission to set it, migration fails
-- closed instead of executing fence DDL under unbounded database-wide hooks.
SET LOCAL event_triggers = off;

-- Event triggers are database-wide DDL hooks and are not represented by pg_trigger,
-- table/column ACLs, rewrite dependencies, SECURITY DEFINER scans or subscription
-- mappings. The catalog check remains a conformance preflight: a database that already
-- has an enabled event trigger is not silently normalized or treated as clean merely
-- because this migration session has disabled trigger execution.
SELECT 1 / CASE
    WHEN current_setting('event_triggers') IS DISTINCT FROM 'off' THEN 0
    WHEN EXISTS (
        SELECT 1
          FROM pg_catalog.pg_event_trigger et
         WHERE et.evtenabled <> 'D'
    ) THEN 0
    ELSE 1
END AS wave1_event_trigger_guard;

LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;

-- A table name is not conformance. Verify the exact ordinary-table shape that makes
-- compare-and-advance single-winner and preserves the accepted BIGINT fence domain.
DO $$
DECLARE
    v_table regclass := to_regclass('platform.authority_fences');
    v_pk_index oid;
BEGIN
    IF v_table IS NULL THEN
        RAISE EXCEPTION 'platform.authority_fences is absent; apply 001 before revalidation';
    END IF;

    IF (
        SELECT ROW(relkind, relpersistence, relispartition, relrowsecurity, relforcerowsecurity)
          FROM pg_class
         WHERE oid = v_table
    ) IS DISTINCT FROM ROW('r'::"char", 'p'::"char", false, false, false) THEN
        RAISE EXCEPTION 'authority_fences must be an ordinary permanent logged table without partition/RLS semantics';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_inherits
         WHERE inhrelid = v_table
            OR inhparent = v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot inherit from or parent another relation';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_policy
         WHERE polrelid = v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot carry row-security policies';
    END IF;

    IF (
        SELECT array_agg(attname::text ORDER BY attnum)
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attnum > 0
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
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attname = 'fence_scope_id'
           AND attnum > 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::regtype THEN
        RAISE EXCEPTION 'authority_fences.fence_scope_id must be text';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attname = 'current_fence_epoch'
           AND attnum > 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'int8'::regtype THEN
        RAISE EXCEPTION 'authority_fences.current_fence_epoch must be bigint';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attname = 'current_generation_id'
           AND attnum > 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::regtype THEN
        RAISE EXCEPTION 'authority_fences.current_generation_id must be text';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attname = 'authority_state'
           AND attnum > 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'text'::regtype THEN
        RAISE EXCEPTION 'authority_fences.authority_state must be text';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attnum > 0
           AND NOT attisdropped
           AND attname IN ('fence_scope_id', 'current_generation_id', 'authority_state')
           AND attcollation IS DISTINCT FROM 'pg_catalog."C"'::regcollation
    ) THEN
        RAISE EXCEPTION 'authority_fences canonical text authority columns must use pg_catalog.C collation';
    END IF;

    IF (
        SELECT atttypid
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attname = 'updated_at'
           AND attnum > 0
           AND NOT attisdropped
    ) IS DISTINCT FROM 'timestamptz'::regtype THEN
        RAISE EXCEPTION 'authority_fences.updated_at must be timestamptz';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_attribute
         WHERE attrelid = v_table
           AND attnum > 0
           AND NOT attisdropped
           AND (attgenerated <> '' OR attidentity <> '')
    ) THEN
        RAISE EXCEPTION 'authority_fences columns cannot be generated or identity columns';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_attrdef d
          JOIN pg_attribute a
            ON a.attrelid = d.adrelid
           AND a.attnum = d.adnum
         WHERE d.adrelid = v_table
           AND a.attname <> 'updated_at'
    ) THEN
        RAISE EXCEPTION 'authority_fences authority columns cannot inherit unreviewed defaults';
    END IF;

    IF (
        SELECT pg_get_expr(d.adbin, d.adrelid)
          FROM pg_attrdef d
          JOIN pg_attribute a
            ON a.attrelid = d.adrelid
           AND a.attnum = d.adnum
         WHERE d.adrelid = v_table
           AND a.attname = 'updated_at'
    ) IS DISTINCT FROM 'statement_timestamp()' THEN
        RAISE EXCEPTION 'authority_fences.updated_at must retain the canonical statement_timestamp() evidence default';
    END IF;

    IF (
        SELECT array_agg(conname::text ORDER BY conname)
          FROM pg_constraint
         WHERE conrelid = v_table
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
          FROM pg_constraint
         WHERE conrelid = v_table
           AND conname IN (
               'wave1_fence_epoch_positive',
               'wave1_fence_generation_canonical',
               'wave1_fence_scope_id_canonical',
               'wave1_fence_state_canonical'
           )
           AND (contype <> 'c' OR NOT convalidated)
    ) THEN
        RAISE EXCEPTION 'authority_fences canonical CHECK constraints must be validated CHECK constraints';
    END IF;

    SELECT c.conindid
      INTO v_pk_index
      FROM pg_constraint c
      JOIN pg_attribute a
        ON a.attrelid = c.conrelid
       AND a.attname = 'fence_scope_id'
       AND a.attnum > 0
       AND NOT a.attisdropped
      JOIN pg_index i
        ON i.indexrelid = c.conindid
     WHERE c.conrelid = v_table
       AND c.conname = 'wave1_authority_fences_pkey'
       AND c.contype = 'p'
       AND c.conkey = ARRAY[a.attnum]::smallint[]
       AND NOT c.condeferrable
       AND NOT c.condeferred
       AND c.convalidated
       AND i.indisprimary
       AND i.indisunique
       AND i.indimmediate
       AND i.indisvalid
       AND i.indisready
       AND i.indislive
       AND i.indnkeyatts = 1
       AND i.indnatts = 1
       AND i.indexprs IS NULL
       AND i.indpred IS NULL;

    IF v_pk_index IS NULL THEN
        RAISE EXCEPTION 'authority_fences primary key must be the canonical single-column immediate valid ready conflict arbiter on fence_scope_id';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_index i
         WHERE i.indrelid = v_table
           AND i.indexrelid <> v_pk_index
    ) THEN
        RAISE EXCEPTION 'authority_fences contains noncanonical index metadata';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
         WHERE c.contype = 'f'
           AND (c.conrelid = v_table OR c.confrelid = v_table)
    ) THEN
        RAISE EXCEPTION 'authority_fences cannot participate in foreign-key referential actions';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_trigger t
         WHERE t.tgrelid = v_table
           AND NOT t.tgisinternal
    ) THEN
        RAISE EXCEPTION 'authority_fences has unexpected non-internal trigger behavior';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_rewrite r
         WHERE r.ev_class = v_table
    ) THEN
        RAISE EXCEPTION 'authority_fences has unexpected rewrite rule behavior';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_rewrite r
          JOIN pg_depend d
            ON d.classid = 'pg_rewrite'::regclass
           AND d.objid = r.oid
           AND d.refclassid = 'pg_class'::regclass
           AND d.refobjid = v_table
         WHERE r.ev_class <> v_table
    ) THEN
        RAISE EXCEPTION 'external rewrite dependency can reach authority_fences';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_subscription_rel sr
         WHERE sr.srrelid = v_table
    ) THEN
        RAISE EXCEPTION 'logical replication subscription can write authority_fences';
    END IF;
END
$$;

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
            btrim(fence_scope_id) <> ''
            AND fence_scope_id COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ) NOT VALID,
    ADD CONSTRAINT wave1_fence_epoch_positive
        CHECK (current_fence_epoch > 0) NOT VALID,
    ADD CONSTRAINT wave1_fence_generation_canonical
        CHECK (
            btrim(current_generation_id) <> ''
            AND current_generation_id COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ) NOT VALID,
    ADD CONSTRAINT wave1_fence_state_canonical
        CHECK (
            btrim(authority_state) <> ''
            AND authority_state COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ) NOT VALID;

ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;
ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_epoch_positive;
ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_generation_canonical;
ALTER TABLE platform.authority_fences
    VALIDATE CONSTRAINT wave1_fence_state_canonical;

-- Do not grant anything here. The separately reviewed C2 runtime/database mapping
-- remains responsible for least-privilege ownership/GRANTs after this contract is
-- proven. A successful validation is schema/data conformance evidence only.

COMMIT;
