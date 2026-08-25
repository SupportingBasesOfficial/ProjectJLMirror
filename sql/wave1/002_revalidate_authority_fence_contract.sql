-- Wave 1 IR-D-003 hardening for migration/replay safety.
--
-- 001 may be applied into an environment where the logical schema already exists.
-- This migration makes reuse fail closed: an existing authority_fences table must
-- satisfy the canonical structural, durability, identifier, deterministic-collation
-- and positive-epoch contract before Wave 1 can consider it eligible for authority use.
-- Invalid historical shape/rows or hidden mutation behavior fail; they are not
-- normalized, deleted, or silently accepted here.

-- A table name is not conformance. Verify the exact ordinary-table shape that makes
-- compare-and-advance single-winner and preserves the accepted BIGINT fence domain.
DO $$
DECLARE
    v_table regclass := to_regclass('platform.authority_fences');
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

    -- Canonical authority identifiers participate in PK/conflict/equality semantics.
    -- They must not inherit a database-default case-insensitive/nondeterministic
    -- collation that could alias distinct canonical IDs. Reuse fails closed rather
    -- than rewriting an existing table under a different comparison domain.
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

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint c
          JOIN pg_attribute a
            ON a.attrelid = c.conrelid
           AND a.attname = 'fence_scope_id'
           AND a.attnum > 0
           AND NOT a.attisdropped
         WHERE c.conrelid = v_table
           AND c.contype = 'p'
           AND c.conkey = ARRAY[a.attnum]::smallint[]
    ) THEN
        RAISE EXCEPTION 'authority_fences must have a single-column primary key on fence_scope_id';
    END IF;

    -- User-defined triggers/rules are hidden mutation semantics. They could alter
    -- scope/epoch/generation/state after the compare predicate or perform an
    -- unreviewed side effect while the SQL function still appears to have won.
    -- Internal PostgreSQL constraint triggers are allowed; any user trigger/rule
    -- requires an explicit reviewed migration instead of being inherited silently.
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
END
$$;

ALTER TABLE platform.authority_fences
    ALTER COLUMN fence_scope_id SET NOT NULL,
    ALTER COLUMN current_fence_epoch SET NOT NULL,
    ALTER COLUMN current_generation_id SET NOT NULL,
    ALTER COLUMN authority_state SET NOT NULL,
    ALTER COLUMN updated_at SET NOT NULL;

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