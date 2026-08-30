\set ON_ERROR_STOP on

-- #49/#50 — retained finalized watermark revalidation and null-cutoff rejection.
--
-- A dataset mutation intentionally invalidates current coverage while preserving
-- the durable historical finalized watermark. A later request to finalize only
-- an earlier T1 must therefore revalidate the *retained* T2 watermark before the
-- stream may return to complete. Otherwise GREATEST(finalized_through,T1) can
-- advertise stale coverage for (T1,T2]. A missing requested cutoff is malformed
-- authority input and must fail closed before it can participate in SQL three-
-- valued comparisons or mint a NULL completeness watermark.

SET ROLE history_reconcile_owner;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.try_finalize(
    p_stream_id text,
    p_finalize_through timestamptz
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_state history_reconcile_evidence.stream_state%ROWTYPE;
    v_generation bigint;
    v_finality_floor timestamptz;
    v_required_snapshot timestamptz;
    v_current_covered timestamptz;
    v_required_through timestamptz;
BEGIN
    IF p_finalize_through IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '22004',
            MESSAGE = 'finalization cutoff must not be null';
    END IF;

    SELECT * INTO v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    SELECT authority_generation, finality_floor, required_reconciliation_snapshot_at
      INTO v_generation, v_finality_floor, v_required_snapshot
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown provider authority';
    END IF;

    IF v_state.state = 'gap' THEN
        RETURN false;
    END IF;

    v_required_through := CASE
        WHEN v_state.finalized_through IS NULL THEN p_finalize_through
        ELSE GREATEST(v_state.finalized_through, p_finalize_through)
    END;

    SELECT history_reconcile_evidence.contiguous_covered_through(
        p_stream_id, v_generation, v_required_snapshot
    ) INTO v_current_covered;

    IF v_required_through > v_finality_floor
       OR v_current_covered IS NULL
       OR v_current_covered < v_required_through THEN
        UPDATE history_reconcile_evidence.stream_state
           SET reconciliation_covered_from = CASE
                   WHEN v_current_covered IS NULL THEN NULL
                   ELSE supported_history_floor
               END,
               reconciliation_covered_through = v_current_covered,
               state = 'reconciliation_required'
         WHERE stream_id = p_stream_id;
        RETURN false;
    END IF;

    UPDATE history_reconcile_evidence.stream_state
       SET reconciliation_covered_from = supported_history_floor,
           reconciliation_covered_through = v_current_covered,
           finalized_through = v_required_through,
           state = 'complete'
     WHERE stream_id = p_stream_id;
    RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION history_reconcile_evidence.try_finalize(text,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.try_finalize(text,timestamptz)
  TO history_reconcile_worker;

RESET ROLE;

-- #50 regression: a worker with only short current coverage must not be able to
-- mint completeness by omitting the requested finalization watermark.
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id, supported_history_floor, state
) VALUES (
    'zabbix:item:null-finalization-watermark',
    '2026-08-28T11:00:00Z',
    'reconciliation_required'
);

INSERT INTO history_reconcile_evidence.provider_authority (
    stream_id, authority_generation, current_snapshot_at,
    finality_floor, required_reconciliation_snapshot_at
) VALUES (
    'zabbix:item:null-finalization-watermark', 1,
    '2026-08-28T13:00:00Z', '2026-08-28T13:00:00Z', '2026-08-28T13:00:00Z'
);

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:null-finalization-watermark',
    '2026-08-28T11:00:00Z','2026-08-28T11:15:00Z',1
);
DO $$
DECLARE
    v_rejected boolean := false;
BEGIN
    BEGIN
        PERFORM history_reconcile_evidence.try_finalize(
            'zabbix:item:null-finalization-watermark', NULL::timestamptz
        );
    EXCEPTION
        WHEN SQLSTATE '22004' THEN
            v_rejected := true;
    END;

    IF NOT v_rejected THEN
        RAISE EXCEPTION 'NULL finalization cutoff was not rejected with SQLSTATE 22004';
    END IF;
END;
$$;
RESET ROLE;

DO $$
DECLARE
    v_covered timestamptz;
    v_finalized_through timestamptz;
    v_state history_reconcile_evidence.completeness_state;
BEGIN
    SELECT reconciliation_covered_through, finalized_through, state
      INTO v_covered, v_finalized_through, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:null-finalization-watermark';

    IF v_covered <> '2026-08-28T11:15:00Z'::timestamptz
       OR v_finalized_through IS NOT NULL
       OR v_state <> 'provisional' THEN
        RAISE EXCEPTION 'NULL finalization cutoff changed completeness state: % % %',
            v_covered, v_finalized_through, v_state;
    END IF;
END;
$$;
SELECT 'history_null_finalize_cutoff_rejected=PASS' AS result;
SELECT 'history_null_finalize_preserves_noncomplete_state=PASS' AS result;

-- Dedicated #49 regression vector: establish T2, invalidate the dataset revision,
-- re-sweep only to T1<T2 and prove that T2 cannot be retained as complete until
-- current-revision coverage has again reached T2.
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id, supported_history_floor, state
) VALUES (
    'zabbix:item:retained-finalized-watermark',
    '2026-08-28T11:00:00Z',
    'reconciliation_required'
);

INSERT INTO history_reconcile_evidence.provider_authority (
    stream_id, authority_generation, current_snapshot_at,
    finality_floor, required_reconciliation_snapshot_at
) VALUES (
    'zabbix:item:retained-finalized-watermark', 1,
    '2026-08-28T13:00:00Z', '2026-08-28T13:00:00Z', '2026-08-28T13:00:00Z'
);

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:retained-finalized-watermark',
    '2026-08-28T11:00:00Z','2026-08-28T12:00:00Z',1
);
DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:retained-finalized-watermark','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'retained-watermark baseline failed to finalize through T2';
    END IF;
END;
$$;
RESET ROLE;

DO $$
DECLARE v_finalized_through timestamptz; v_state history_reconcile_evidence.completeness_state;
BEGIN
    SELECT finalized_through, state INTO v_finalized_through, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:retained-finalized-watermark';
    IF v_finalized_through <> '2026-08-28T12:00:00Z'::timestamptz OR v_state <> 'complete' THEN
        RAISE EXCEPTION 'retained-watermark baseline state mismatch: % %', v_finalized_through, v_state;
    END IF;
END;
$$;

SET ROLE history_reconcile_owner;
INSERT INTO history_reconcile_evidence.provider_visible_history (
    stream_id, observation_id, observed_at, became_visible_at, numeric_value
) VALUES (
    'zabbix:item:retained-finalized-watermark',
    '09090909-0909-0909-0909-090909090909',
    '2026-08-28T11:15:00Z','2026-08-28T11:20:00Z',9
);
RESET ROLE;

DO $$
DECLARE
    v_revision bigint;
    v_covered timestamptz;
    v_finalized_through timestamptz;
    v_state history_reconcile_evidence.completeness_state;
BEGIN
    SELECT provider_dataset_revision INTO v_revision
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id='zabbix:item:retained-finalized-watermark';
    SELECT reconciliation_covered_through, finalized_through, state
      INTO v_covered, v_finalized_through, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:retained-finalized-watermark';
    IF v_revision <> 2 OR v_covered IS NOT NULL
       OR v_finalized_through <> '2026-08-28T12:00:00Z'::timestamptz
       OR v_state <> 'reconciliation_required' THEN
        RAISE EXCEPTION 'dataset invalidation did not preserve only the historical T2 watermark';
    END IF;
END;
$$;

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:retained-finalized-watermark',
    '2026-08-28T11:00:00Z','2026-08-28T11:30:00Z',1
);
DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:retained-finalized-watermark','2026-08-28T11:30:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'partial current-revision sweep resurrected stale T2 completeness';
    END IF;
END;
$$;
RESET ROLE;

DO $$
DECLARE
    v_covered timestamptz;
    v_finalized_through timestamptz;
    v_state history_reconcile_evidence.completeness_state;
BEGIN
    SELECT reconciliation_covered_through, finalized_through, state
      INTO v_covered, v_finalized_through, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:retained-finalized-watermark';
    IF v_covered <> '2026-08-28T11:30:00Z'::timestamptz
       OR v_finalized_through <> '2026-08-28T12:00:00Z'::timestamptz
       OR v_state <> 'reconciliation_required' THEN
        RAISE EXCEPTION 'partial revalidation did not fail closed against retained T2';
    END IF;
END;
$$;
SELECT 'history_retained_finalized_watermark_requires_revalidation=PASS' AS result;

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:retained-finalized-watermark',
    '2026-08-28T11:30:00Z','2026-08-28T12:00:00Z',1
);
DO $$
DECLARE v_finalized boolean;
BEGIN
    -- Deliberately request only T1 again. The retained T2 is what forces the
    -- current-revision coverage proof through T2.
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:retained-finalized-watermark','2026-08-28T11:30:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'full T2 revalidation did not restore completion';
    END IF;
END;
$$;
RESET ROLE;

DO $$
DECLARE
    v_covered timestamptz;
    v_finalized_through timestamptz;
    v_state history_reconcile_evidence.completeness_state;
BEGIN
    SELECT reconciliation_covered_through, finalized_through, state
      INTO v_covered, v_finalized_through, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:retained-finalized-watermark';
    IF v_covered < '2026-08-28T12:00:00Z'::timestamptz
       OR v_finalized_through <> '2026-08-28T12:00:00Z'::timestamptz
       OR v_state <> 'complete' THEN
        RAISE EXCEPTION 'retained T2 was not restored only after full current-revision coverage';
    END IF;
END;
$$;
SELECT 'history_retained_finalized_watermark_recovers_after_full_revalidation=PASS' AS result;
