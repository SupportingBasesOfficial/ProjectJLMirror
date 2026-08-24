-- Wave 1 IR-D-003 hardening for migration/replay safety.
--
-- 001 may be applied into an environment where the logical schema already exists.
-- This migration makes reuse fail closed: an existing authority_fences table must
-- satisfy the canonical structural, identifier and positive-epoch contract before
-- Wave 1 can consider it eligible for authority use. Invalid historical shape/rows
-- fail; they are not normalized, deleted, or silently accepted here.

-- A table name is not conformance. Verify the structural properties that make
-- compare-and-advance single-winner and preserve the accepted BIGINT fence domain.
DO $$
DECLARE
    v_table regclass := to_regclass('platform.authority_fences');
BEGIN
    IF v_table IS NULL THEN
        RAISE EXCEPTION 'platform.authority_fences is absent; apply 001 before revalidation';
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
END
$$;

ALTER TABLE platform.authority_fences
    ALTER COLUMN fence_scope_id SET NOT NULL,
    ALTER COLUMN current_fence_epoch SET NOT NULL,
    ALTER COLUMN current_generation_id SET NOT NULL,
    ALTER COLUMN authority_state SET NOT NULL;

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
