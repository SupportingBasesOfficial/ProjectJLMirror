\set ON_ERROR_STOP on

-- #51 — canonical history authority lock order.
--
-- Provider-visible mutation and authority advancement acquire
-- provider_authority before stream_state. Finalization and sweep must acquire
-- the same rows in the same order before entering their already-proven logic;
-- otherwise ordinary mutation/finalization concurrency can form the cycle
-- stream_state -> provider_authority / provider_authority -> stream_state.
--
-- Keep the #49/#50 implementations intact behind owner-only internal entry
-- points. Public worker entry points become thin authority-order wrappers.

SET ROLE history_reconcile_owner;

ALTER FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint)
  RENAME TO sweep_pre_lock_order;
ALTER FUNCTION history_reconcile_evidence.try_finalize(text,timestamptz)
  RENAME TO try_finalize_pre_lock_order;

REVOKE ALL ON FUNCTION history_reconcile_evidence.sweep_pre_lock_order(text,timestamptz,timestamptz,bigint)
  FROM PUBLIC, history_reconcile_worker;
REVOKE ALL ON FUNCTION history_reconcile_evidence.try_finalize_pre_lock_order(text,timestamptz)
  FROM PUBLIC, history_reconcile_worker;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.sweep(
    p_stream_id text,
    p_window_from timestamptz,
    p_window_to timestamptz,
    p_expected_authority_generation bigint
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
BEGIN
    IF p_window_from > p_window_to THEN
        RAISE EXCEPTION 'invalid reconciliation window';
    END IF;

    -- Canonical authority order: provider_authority -> stream_state.
    PERFORM 1
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown provider authority';
    END IF;

    PERFORM 1
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    RETURN history_reconcile_evidence.sweep_pre_lock_order(
        p_stream_id,
        p_window_from,
        p_window_to,
        p_expected_authority_generation
    );
END;
$$;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.try_finalize(
    p_stream_id text,
    p_finalize_through timestamptz
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
BEGIN
    -- Preserve #50 fail-closed malformed-input semantics before authority work.
    IF p_finalize_through IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '22004',
            MESSAGE = 'finalization cutoff must not be null';
    END IF;

    -- Canonical authority order: provider_authority -> stream_state.
    PERFORM 1
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown provider authority';
    END IF;

    PERFORM 1
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    RETURN history_reconcile_evidence.try_finalize_pre_lock_order(
        p_stream_id,
        p_finalize_through
    );
END;
$$;

REVOKE ALL ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint)
  FROM PUBLIC;
REVOKE ALL ON FUNCTION history_reconcile_evidence.try_finalize(text,timestamptz)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint)
  TO history_reconcile_worker;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.try_finalize(text,timestamptz)
  TO history_reconcile_worker;

RESET ROLE;

DO $$
DECLARE
    v_worker_can_internal_sweep boolean;
    v_worker_can_internal_finalize boolean;
    v_null_rejected boolean := false;
BEGIN
    SELECT has_function_privilege(
        'history_reconcile_worker',
        'history_reconcile_evidence.sweep_pre_lock_order(text,timestamptz,timestamptz,bigint)',
        'EXECUTE'
    ) INTO v_worker_can_internal_sweep;
    SELECT has_function_privilege(
        'history_reconcile_worker',
        'history_reconcile_evidence.try_finalize_pre_lock_order(text,timestamptz)',
        'EXECUTE'
    ) INTO v_worker_can_internal_finalize;

    IF v_worker_can_internal_sweep OR v_worker_can_internal_finalize THEN
        RAISE EXCEPTION 'worker can bypass canonical history lock-order wrappers';
    END IF;

    BEGIN
        SET LOCAL ROLE history_reconcile_worker;
        PERFORM history_reconcile_evidence.try_finalize(
            'zabbix:item:null-finalization-watermark', NULL::timestamptz
        );
    EXCEPTION WHEN SQLSTATE '22004' THEN
        v_null_rejected := true;
    END;

    IF NOT v_null_rejected THEN
        RAISE EXCEPTION '#50 null-finalize rejection was not preserved by lock-order wrapper';
    END IF;
END;
$$;

SELECT 'history_lock_order_wrappers_installed=PASS' AS result;
SELECT 'history_internal_entrypoints_not_worker_callable=PASS' AS result;
SELECT 'history_null_finalize_guard_preserved_after_lock_order=PASS' AS result;
