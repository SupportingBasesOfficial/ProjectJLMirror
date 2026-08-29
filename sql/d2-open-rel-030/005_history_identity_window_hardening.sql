\set ON_ERROR_STOP on

-- Panoramic repair for owner-current corrections that move a stable accepted
-- observation across a requested reconciliation-window boundary. Stable
-- identity/content validation happens before the provider timestamp is used to
-- select new rows for this window. A conflict is relevant when either the
-- accepted timestamp or owner-current provider timestamp intersects the window.
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
DECLARE
    v_before bigint;
    v_after bigint;
    v_supported_floor timestamptz;
    v_snapshot timestamptz;
    v_generation bigint;
    v_covered timestamptz;
BEGIN
    IF p_window_from > p_window_to THEN
        RAISE EXCEPTION 'invalid reconciliation window';
    END IF;

    SELECT s.supported_history_floor, a.authority_generation, a.current_snapshot_at
      INTO v_supported_floor, v_generation, v_snapshot
      FROM history_reconcile_evidence.stream_state s
      JOIN history_reconcile_evidence.provider_authority a USING (stream_id)
     WHERE s.stream_id = p_stream_id
     FOR UPDATE OF s, a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream or provider authority';
    END IF;
    IF v_generation <> p_expected_authority_generation THEN
        RAISE EXCEPTION 'stale reconciliation worker authority';
    END IF;

    -- Validate stable identities before provider-time windowing. A correction
    -- cannot escape validation merely by moving p.observed_at outside the
    -- requested window while the already accepted observation was inside (or
    -- vice versa).
    IF EXISTS (
        SELECT 1
          FROM history_reconcile_evidence.provider_visible_history p
          JOIN history_reconcile_evidence.accepted_history a
            ON a.stream_id = p.stream_id
           AND a.observation_id = p.observation_id
         WHERE p.stream_id = p_stream_id
           AND p.became_visible_at <= v_snapshot
           AND (
               (a.observed_at >= p_window_from AND a.observed_at <= p_window_to)
               OR
               (p.observed_at >= p_window_from AND p.observed_at <= p_window_to)
           )
           AND (
               a.observed_at IS DISTINCT FROM p.observed_at
               OR a.numeric_value IS DISTINCT FROM p.numeric_value
           )
    ) THEN
        RAISE EXCEPTION 'reconciled observation identity content mismatch';
    END IF;

    SELECT count(*) INTO v_before
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = p_stream_id;

    INSERT INTO history_reconcile_evidence.accepted_history (
        stream_id, observation_id, observed_at, numeric_value
    )
    SELECT stream_id, observation_id, observed_at, numeric_value
      FROM history_reconcile_evidence.provider_visible_history
     WHERE stream_id = p_stream_id
       AND observed_at >= p_window_from
       AND observed_at <= p_window_to
       AND became_visible_at <= v_snapshot
    ON CONFLICT (stream_id, observation_id) DO NOTHING;

    SELECT count(*) INTO v_after
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = p_stream_id;

    INSERT INTO history_reconcile_evidence.reconciliation_run (
        stream_id, authority_generation, window_from, window_to,
        provider_snapshot_at, discovered_count
    ) VALUES (
        p_stream_id, v_generation, p_window_from, p_window_to,
        v_snapshot, v_after - v_before
    );

    SELECT history_reconcile_evidence.contiguous_covered_through(
        p_stream_id, v_generation, '-infinity'::timestamptz
    ) INTO v_covered;

    UPDATE history_reconcile_evidence.stream_state
       SET reconciliation_covered_from = CASE WHEN v_covered IS NULL THEN NULL ELSE v_supported_floor END,
           reconciliation_covered_through = v_covered,
           state = CASE WHEN state = 'gap' THEN state ELSE 'provisional' END
     WHERE stream_id = p_stream_id;

    RETURN v_after - v_before;
END;
$$;

REVOKE ALL ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint)
  TO history_reconcile_worker;

-- Negative: the accepted identity is at 11:58, owner-current provider history
-- corrects the same identity to 12:01. Provider-time-only filtering would omit
-- the row from an 11:55..12:00 sweep and falsely mint coverage.
UPDATE history_reconcile_evidence.provider_visible_history
   SET observed_at = '2026-08-28T12:01:00Z'
 WHERE stream_id='zabbix:item:42'
   AND observation_id='01010101-0101-0101-0101-010101010101'::uuid;

DO $$
DECLARE
    v_runs_before bigint;
    v_runs_after bigint;
    v_accepted_at timestamptz;
BEGIN
    SELECT count(*) INTO v_runs_before
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:42';

    BEGIN
        PERFORM history_reconcile_evidence.sweep(
            'zabbix:item:42',
            '2026-08-28T11:55:00Z',
            '2026-08-28T12:00:00Z',
            4
        );
        RAISE EXCEPTION 'cross-window stable-identity correction unexpectedly minted coverage';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%reconciled observation identity content mismatch%' THEN
            RAISE;
        END IF;
    END;

    SELECT count(*) INTO v_runs_after
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:42';
    SELECT observed_at INTO v_accepted_at
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id='zabbix:item:42'
       AND observation_id='01010101-0101-0101-0101-010101010101'::uuid;

    IF v_runs_after <> v_runs_before THEN
        RAISE EXCEPTION 'cross-window conflict minted reconciliation_run';
    END IF;
    IF v_accepted_at IS DISTINCT FROM '2026-08-28T11:58:00Z'::timestamptz THEN
        RAISE EXCEPTION 'cross-window conflict mutated accepted canonical timestamp: %', v_accepted_at;
    END IF;
END;
$$;

-- Restore provider-visible canonical content, then prove the same window can be
-- swept normally again under the same owner generation.
UPDATE history_reconcile_evidence.provider_visible_history
   SET observed_at = '2026-08-28T11:58:00Z'
 WHERE stream_id='zabbix:item:42'
   AND observation_id='01010101-0101-0101-0101-010101010101'::uuid;

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42',
    '2026-08-28T11:55:00Z',
    '2026-08-28T12:00:00Z',
    4
);
RESET ROLE;

SELECT 'history_cross_window_identity_conflict_rejected=PASS' AS result;
