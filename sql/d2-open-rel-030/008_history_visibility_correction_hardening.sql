\set ON_ERROR_STOP on

-- Panoramic hardening for owner corrections that move became_visible_at beyond
-- the current provider snapshot. Visibility controls whether a not-yet-accepted
-- provider row may be inserted during this sweep; it must never hide a conflict
-- for a stable identity that is already present in accepted_history.

SET ROLE history_reconcile_owner;

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
    v_dataset_revision bigint;
    v_covered timestamptz;
BEGIN
    IF p_window_from > p_window_to THEN
        RAISE EXCEPTION 'invalid reconciliation window';
    END IF;

    SELECT s.supported_history_floor,
           a.authority_generation,
           a.current_snapshot_at,
           a.provider_dataset_revision
      INTO v_supported_floor, v_generation, v_snapshot, v_dataset_revision
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

    -- Stable accepted identity is authority-relevant independently of the
    -- provider row's current visibility timestamp. If either the accepted or
    -- owner-current observation time intersects this sweep window, compare the
    -- canonical content before provider-time/visibility insertion filtering.
    IF EXISTS (
        SELECT 1
          FROM history_reconcile_evidence.provider_visible_history p
          JOIN history_reconcile_evidence.accepted_history a
            ON a.stream_id = p.stream_id
           AND a.observation_id = p.observation_id
         WHERE p.stream_id = p_stream_id
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

    -- Visibility remains valid only for admitting previously unaccepted rows.
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
        stream_id, authority_generation, provider_dataset_revision,
        window_from, window_to, provider_snapshot_at, discovered_count
    ) VALUES (
        p_stream_id, v_generation, v_dataset_revision,
        p_window_from, p_window_to, v_snapshot, v_after - v_before
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

RESET ROLE;

-- Dedicated visibility-shift vector. Begin from a complete stream where the
-- accepted and provider copies agree. The owner then corrects the stable
-- identity, moves observed_at outside the requested window and moves
-- became_visible_at beyond the locked current snapshot. Dataset revision must
-- invalidate old coverage, and the fresh sweep must still reject the conflict.
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id, supported_history_floor, state
) VALUES (
    'zabbix:item:visibility-shift',
    '2026-08-28T11:00:00Z',
    'reconciliation_required'
);

INSERT INTO history_reconcile_evidence.provider_authority (
    stream_id, authority_generation, current_snapshot_at,
    finality_floor, required_reconciliation_snapshot_at
) VALUES (
    'zabbix:item:visibility-shift', 1,
    '2026-08-28T12:00:00Z', '2026-08-28T12:00:00Z', '2026-08-28T12:00:00Z'
);

INSERT INTO history_reconcile_evidence.accepted_history (
    stream_id, observation_id, observed_at, numeric_value
) VALUES (
    'zabbix:item:visibility-shift',
    '08080808-0808-0808-0808-080808080808',
    '2026-08-28T11:58:00Z', 7
);

INSERT INTO history_reconcile_evidence.provider_visible_history (
    stream_id, observation_id, observed_at, became_visible_at, numeric_value
) VALUES (
    'zabbix:item:visibility-shift',
    '08080808-0808-0808-0808-080808080808',
    '2026-08-28T11:58:00Z', '2026-08-28T11:59:00Z', 7
);

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:visibility-shift',
    '2026-08-28T11:00:00Z','2026-08-28T12:00:00Z',1
);
RESET ROLE;

DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:visibility-shift','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'visibility-shift baseline failed to finalize';
    END IF;
END;
$$;

SET ROLE history_reconcile_owner;
UPDATE history_reconcile_evidence.provider_visible_history
   SET observed_at = '2026-08-28T12:01:00Z',
       became_visible_at = '2026-08-28T12:30:00Z',
       numeric_value = 8
 WHERE stream_id='zabbix:item:visibility-shift'
   AND observation_id='08080808-0808-0808-0808-080808080808'::uuid;
RESET ROLE;

DO $$
DECLARE
    v_revision bigint;
    v_covered timestamptz;
    v_state history_reconcile_evidence.completeness_state;
    v_runs_before bigint;
    v_runs_after bigint;
    v_accepted_time timestamptz;
    v_accepted_value numeric;
BEGIN
    SELECT provider_dataset_revision INTO v_revision
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id='zabbix:item:visibility-shift';
    IF v_revision <> 3 THEN
        RAISE EXCEPTION 'visibility correction did not advance dataset revision: %', v_revision;
    END IF;

    SELECT reconciliation_covered_through, state
      INTO v_covered, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:visibility-shift';
    IF v_covered IS NOT NULL OR v_state <> 'reconciliation_required' THEN
        RAISE EXCEPTION 'visibility correction retained stale coverage';
    END IF;

    SELECT count(*) INTO v_runs_before
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:visibility-shift';

    BEGIN
        PERFORM history_reconcile_evidence.sweep(
            'zabbix:item:visibility-shift',
            '2026-08-28T11:00:00Z','2026-08-28T12:00:00Z',1
        );
        RAISE EXCEPTION 'future-visible conflicting stable identity unexpectedly swept';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%reconciled observation identity content mismatch%' THEN
            RAISE;
        END IF;
    END;

    SELECT count(*) INTO v_runs_after
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:visibility-shift';
    IF v_runs_after <> v_runs_before THEN
        RAISE EXCEPTION 'rejected visibility-shift conflict minted reconciliation coverage';
    END IF;

    SELECT observed_at, numeric_value
      INTO v_accepted_time, v_accepted_value
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id='zabbix:item:visibility-shift'
       AND observation_id='08080808-0808-0808-0808-080808080808'::uuid;
    IF v_accepted_time <> '2026-08-28T11:58:00Z'::timestamptz OR v_accepted_value <> 7 THEN
        RAISE EXCEPTION 'rejected visibility correction mutated accepted canonical history';
    END IF;
END;
$$;

SELECT 'history_visibility_shift_conflict_rejected=PASS' AS result;
SELECT 'history_visibility_shift_cannot_mint_coverage=PASS' AS result;
