-- Wave 1 concrete IR-D-003 fence storage/advance contract.
-- Executed only by the accepted migration/admin authority; serving principals do
-- not gain DDL or function-execution authority merely because this file exists.
--
-- Bootstrap is self-transactional and closes database-wide event-trigger execution
-- before the first event-trigger-capable DDL. It also fixes the migration search_path
-- to pg_catalog so writable schemas cannot shadow catalog functions/operators.
--
-- CRITICAL reuse rule: this bootstrap mutates authority objects only when the fence
-- table is absent. If platform.authority_fences already exists, migration 001 performs
-- no persistent object mutation; migration 002 owns reuse validation and may mutate
-- only after that existing object passes its fail-closed contract under one transaction.

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
END AS wave1_bootstrap_event_trigger_guard;

DO $wave1_bootstrap$
DECLARE
    v_existing_table pg_catalog.regclass := pg_catalog.to_regclass('platform.authority_fences');
BEGIN
    -- Reuse is deliberately non-mutating here. Migration 002 must validate the
    -- existing object before any canonicalization/replacement is attempted.
    IF v_existing_table IS NOT NULL THEN
        RETURN;
    END IF;

    EXECUTE 'CREATE SCHEMA IF NOT EXISTS platform';
    EXECUTE 'REVOKE CREATE ON SCHEMA platform FROM PUBLIC';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC';

    EXECUTE $wave1_ddl$
        CREATE TABLE platform.authority_fences (
            fence_scope_id text COLLATE "C" NOT NULL,
            current_fence_epoch bigint NOT NULL,
            current_generation_id text COLLATE "C" NOT NULL,
            authority_state text COLLATE "C" NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp(),

            CONSTRAINT wave1_authority_fences_pkey
                PRIMARY KEY (fence_scope_id),
            CONSTRAINT wave1_fence_scope_id_canonical
                CHECK (
                    pg_catalog.btrim(fence_scope_id) OPERATOR(pg_catalog.<>) ''
                    AND fence_scope_id COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
                ),
            CONSTRAINT wave1_fence_epoch_positive
                CHECK (current_fence_epoch OPERATOR(pg_catalog.>) 0),
            CONSTRAINT wave1_fence_generation_canonical
                CHECK (
                    pg_catalog.btrim(current_generation_id) OPERATOR(pg_catalog.<>) ''
                    AND current_generation_id COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
                ),
            CONSTRAINT wave1_fence_state_canonical
                CHECK (
                    pg_catalog.btrim(authority_state) OPERATOR(pg_catalog.<>) ''
                    AND authority_state COLLATE "C" OPERATOR(pg_catalog.~) '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
                )
        )
    $wave1_ddl$;

    EXECUTE 'REVOKE ALL ON TABLE platform.authority_fences FROM PUBLIC';

    EXECUTE $wave1_ddl$
        COMMENT ON TABLE platform.authority_fences IS
        'IR-D-003 scope-local monotonic fencing authority. Wall clock and process identity are evidence only.'
    $wave1_ddl$;
    EXECUTE $wave1_ddl$
        COMMENT ON COLUMN platform.authority_fences.current_fence_epoch IS
        'Positive signed BIGINT; no wrap, reset or reuse semantics.'
    $wave1_ddl$;

    EXECUTE $wave1_ddl$
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
        $wave1_function$
    $wave1_ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION platform.initialize_authority_fence(text, text, text) FROM PUBLIC';

    EXECUTE $wave1_ddl$
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
        $wave1_function$
    $wave1_ddl$;

    EXECUTE 'REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text, text) FROM PUBLIC';
END
$wave1_bootstrap$;

-- Co-resident protected mutations MUST bind an effect-eligible current authority
-- state plus the scope, epoch and generation in the same PostgreSQL transaction
-- as the protected effect. A separate prior SELECT/check is not sufficient authority.
-- GRANTs remain absent; C2 runtime/database mapping is separately governed.

COMMIT;
