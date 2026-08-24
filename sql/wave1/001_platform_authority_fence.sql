-- Wave 1 concrete IR-D-003 fence storage/advance contract.
-- Executed only by the accepted migration/admin authority; serving principals do
-- not gain DDL or function-execution authority merely because this file exists.

CREATE SCHEMA IF NOT EXISTS platform;
REVOKE CREATE ON SCHEMA platform FROM PUBLIC;

CREATE TABLE IF NOT EXISTS platform.authority_fences (
    fence_scope_id text PRIMARY KEY CHECK (btrim(fence_scope_id) <> ''),
    current_fence_epoch bigint NOT NULL CHECK (current_fence_epoch > 0),
    current_generation_id text NOT NULL CHECK (btrim(current_generation_id) <> ''),
    authority_state text NOT NULL CHECK (btrim(authority_state) <> ''),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
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
-- can win for one expected predecessor epoch. BIGINT exhaustion fails closed.
CREATE OR REPLACE FUNCTION platform.advance_authority_fence(
    p_fence_scope_id text,
    p_expected_predecessor_epoch bigint,
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
     WHERE authority_fences.fence_scope_id = p_fence_scope_id
       AND authority_fences.current_fence_epoch = p_expected_predecessor_epoch
       AND authority_fences.current_fence_epoch < 9223372036854775807
       AND btrim(p_successor_generation_id) <> ''
       AND btrim(p_successor_state) <> ''
    RETURNING
        authority_fences.fence_scope_id,
        authority_fences.current_fence_epoch,
        authority_fences.current_generation_id,
        authority_fences.authority_state;
$$;

REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text) FROM PUBLIC;

-- Co-resident protected mutations MUST bind the scope, epoch and generation in
-- the same PostgreSQL transaction as the protected effect. A separate prior
-- SELECT/check is not sufficient authority and is intentionally not provided as
-- a convenience function here.
--
-- GRANTs are deliberately absent: an implementation must explicitly bind the
-- least-privilege migration/control principal to these objects in a separately
-- reviewed C2 runtime/database mapping. PUBLIC or serving-role execution is not
-- a safe default.
