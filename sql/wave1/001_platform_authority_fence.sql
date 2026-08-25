-- Wave 1 concrete IR-D-003 fence storage/advance contract.
-- Executed only by the accepted migration/admin authority; serving principals do
-- not gain DDL or function-execution authority merely because this file exists.

CREATE SCHEMA IF NOT EXISTS platform;
REVOKE CREATE ON SCHEMA platform FROM PUBLIC;

-- PostgreSQL grants EXECUTE on newly created functions to PUBLIC by default.
-- Remove that default for functions created by this migration role in this schema
-- BEFORE any authority function is created. Explicit per-function REVOKEs below
-- remain defense in depth and cover reruns/existing objects.
ALTER DEFAULT PRIVILEGES IN SCHEMA platform
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Canonical identifier/equality-bearing columns use deterministic C collation.
-- The constraint set is deliberately named and finite so migration 002 can prove
-- there is no extra CHECK/UNIQUE/EXCLUDE/index metadata capable of changing valid
-- canonical writes on a reused authority table.
CREATE TABLE IF NOT EXISTS platform.authority_fences (
    fence_scope_id text COLLATE "C" NOT NULL,
    current_fence_epoch bigint NOT NULL,
    current_generation_id text COLLATE "C" NOT NULL,
    authority_state text COLLATE "C" NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),

    CONSTRAINT wave1_authority_fences_pkey
        PRIMARY KEY (fence_scope_id),
    CONSTRAINT wave1_fence_scope_id_canonical
        CHECK (
            btrim(fence_scope_id) <> ''
            AND fence_scope_id COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ),
    CONSTRAINT wave1_fence_epoch_positive
        CHECK (current_fence_epoch > 0),
    CONSTRAINT wave1_fence_generation_canonical
        CHECK (
            btrim(current_generation_id) <> ''
            AND current_generation_id COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        ),
    CONSTRAINT wave1_fence_state_canonical
        CHECK (
            btrim(authority_state) <> ''
            AND authority_state COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
        )
);

REVOKE ALL ON TABLE platform.authority_fences FROM PUBLIC;

COMMENT ON TABLE platform.authority_fences IS
'IR-D-003 scope-local monotonic fencing authority. Wall clock and process identity are evidence only.';
COMMENT ON COLUMN platform.authority_fences.current_fence_epoch IS
'Positive signed BIGINT; no wrap, reset or reuse semantics.';

-- Initial scope creation is single-winner. A conflict means the caller must
-- observe/reconcile the existing authority instead of overwriting it.
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
AS $$
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
$$;

REVOKE ALL ON FUNCTION platform.initialize_authority_fence(text, text, text) FROM PUBLIC;

-- Successor acquisition is compare-and-advance. Exactly one concurrent caller
-- can win for one exact expected active predecessor (scope + epoch + generation).
-- A quarantined/retired/unknown predecessor cannot be advanced through this
-- ordinary effect-authority path; recovery/state-transition flows require their
-- separately governed authority and cannot resurrect effect eligibility here.
-- BIGINT exhaustion fails closed. Canonical row CHECK constraints apply to the
-- successor generation/state in the same statement; malformed identifiers cannot
-- become persisted authority merely because a caller reached this function.
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
AS $$
    UPDATE platform.authority_fences
       SET current_fence_epoch = current_fence_epoch + 1,
           current_generation_id = p_successor_generation_id,
           authority_state = p_successor_state,
           updated_at = statement_timestamp()
     WHERE authority_fences.fence_scope_id COLLATE "C" = p_fence_scope_id COLLATE "C"
       AND authority_fences.current_fence_epoch = p_expected_predecessor_epoch
       AND authority_fences.current_generation_id COLLATE "C" = p_expected_predecessor_generation_id COLLATE "C"
       AND authority_fences.authority_state COLLATE "C" = 'active' COLLATE "C"
       AND authority_fences.current_fence_epoch < 9223372036854775807
       AND btrim(p_expected_predecessor_generation_id) <> ''
       AND btrim(p_successor_generation_id) <> ''
       AND btrim(p_successor_state) <> ''
       AND p_expected_predecessor_generation_id COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
       AND p_successor_generation_id COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
       AND p_successor_state COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    RETURNING
        authority_fences.fence_scope_id,
        authority_fences.current_fence_epoch,
        authority_fences.current_generation_id,
        authority_fences.authority_state;
$$;

REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text, text) FROM PUBLIC;

-- Co-resident protected mutations MUST bind an effect-eligible current authority
-- state plus the scope, epoch and generation in the same PostgreSQL transaction
-- as the protected effect. A separate prior SELECT/check is not sufficient
-- authority and is intentionally not provided as a convenience function here.
--
-- GRANTs are deliberately absent: an implementation must explicitly bind the
-- least-privilege migration/control principal to these objects in a separately
-- reviewed C2 runtime/database mapping. PUBLIC or serving-role execution is not
-- a safe default.
