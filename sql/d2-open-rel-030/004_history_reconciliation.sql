\set ON_ERROR_STOP on

DROP SCHEMA IF EXISTS history_reconcile_evidence CASCADE;
CREATE SCHEMA history_reconcile_evidence;

CREATE TYPE history_reconcile_evidence.completeness_state AS ENUM (
    'provisional',
    'reconciliation_required',
    'complete',
    'gap'
);

CREATE TABLE history_reconcile_evidence.provider_visible_history (
    stream_id text NOT NULL,
    observation_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    became_visible_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    PRIMARY KEY (stream_id, observation_id)
);

CREATE TABLE history_reconcile_evidence.accepted_history (
    stream_id text NOT NULL,
    observation_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (stream_id, observation_id)
);

CREATE TABLE history_reconcile_evidence.stream_state (
    stream_id text PRIMARY KEY,
    provisional_high_water timestamptz,
    fast_overlap_floor timestamptz,
    supported_history_floor timestamptz NOT NULL,
    finalized_through timestamptz,
    reconciliation_covered_from timestamptz,
    reconciliation_covered_through timestamptz,
    state history_reconcile_evidence.completeness_state NOT NULL DEFAULT 'provisional',
    gap_from timestamptz,
    gap_to timestamptz,
    CHECK (
        (reconciliation_covered_from IS NULL AND reconciliation_covered_through IS NULL)
        OR (
            reconciliation_covered_from IS NOT NULL
            AND reconciliation_covered_through IS NOT NULL
            AND reconciliation_covered_from <= reconciliation_covered_through
        )
    ),
    CHECK ((state = 'gap') = (gap_from IS NOT NULL AND gap_to IS NOT NULL)),
    CHECK (gap_from IS NULL OR gap_from <= gap_to)
);

CREATE TABLE history_reconcile_evidence.reconciliation_run (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stream_id text NOT NULL,
    window_from timestamptz NOT NULL,
    window_to timestamptz NOT NULL,
    provider_snapshot_at timestamptz NOT NULL,
    discovered_count bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (window_from <= window_to)
);

-- Derive only the interval that is continuously covered starting at the
-- owner's supported history floor. A high disjoint window cannot advance this
-- result across an unswept hole. p_min_provider_snapshot_at additionally lets
-- finalization ignore sweeps that predate the finality/currentness evidence it
-- relies on.
CREATE OR REPLACE FUNCTION history_reconcile_evidence.contiguous_covered_through(
    p_stream_id text,
    p_min_provider_snapshot_at timestamptz DEFAULT '-infinity'::timestamptz
)
RETURNS timestamptz
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_floor timestamptz;
    v_covered timestamptz;
    v_started boolean := false;
    v_run record;
BEGIN
    SELECT supported_history_floor INTO v_floor
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    v_covered := v_floor;

    FOR v_run IN
        SELECT window_from, window_to
          FROM history_reconcile_evidence.reconciliation_run
         WHERE stream_id = p_stream_id
           AND provider_snapshot_at >= p_min_provider_snapshot_at
           AND window_to >= v_floor
         ORDER BY window_from, window_to
    LOOP
        IF NOT v_started THEN
            IF v_run.window_from > v_floor THEN
                EXIT;
            END IF;
            v_covered := GREATEST(v_floor, v_run.window_to);
            v_started := true;
        ELSE
            IF v_run.window_from > v_covered THEN
                EXIT;
            END IF;
            v_covered := GREATEST(v_covered, v_run.window_to);
        END IF;
    END LOOP;

    IF NOT v_started THEN
        RETURN NULL;
    END IF;
    RETURN v_covered;
END;
$$;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.sweep(
    p_stream_id text,
    p_window_from timestamptz,
    p_window_to timestamptz,
    p_provider_snapshot_at timestamptz
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_before bigint;
    v_after bigint;
    v_supported_floor timestamptz;
    v_covered timestamptz;
BEGIN
    IF p_window_from > p_window_to THEN
        RAISE EXCEPTION 'invalid reconciliation window';
    END IF;

    -- Serialize coverage evidence per stream. This prevents two concurrent
    -- sweeps from publishing stale/non-monotonic derived coverage state.
    SELECT supported_history_floor INTO v_supported_floor
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    SELECT count(*) INTO v_before
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = p_stream_id;

    INSERT INTO history_reconcile_evidence.accepted_history (
        stream_id,
        observation_id,
        observed_at,
        numeric_value
    )
    SELECT
        stream_id,
        observation_id,
        observed_at,
        numeric_value
    FROM history_reconcile_evidence.provider_visible_history
    WHERE stream_id = p_stream_id
      AND observed_at >= p_window_from
      AND observed_at <= p_window_to
      AND became_visible_at <= p_provider_snapshot_at
    ON CONFLICT (stream_id, observation_id) DO NOTHING;

    SELECT count(*) INTO v_after
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = p_stream_id;

    INSERT INTO history_reconcile_evidence.reconciliation_run (
        stream_id,
        window_from,
        window_to,
        provider_snapshot_at,
        discovered_count
    ) VALUES (
        p_stream_id,
        p_window_from,
        p_window_to,
        p_provider_snapshot_at,
        v_after - v_before
    );

    SELECT history_reconcile_evidence.contiguous_covered_through(
        p_stream_id,
        '-infinity'::timestamptz
    ) INTO v_covered;

    UPDATE history_reconcile_evidence.stream_state
       SET reconciliation_covered_from = CASE
               WHEN v_covered IS NULL THEN NULL
               ELSE v_supported_floor
           END,
           reconciliation_covered_through = v_covered,
           state = CASE WHEN state = 'gap' THEN state ELSE 'provisional' END
     WHERE stream_id = p_stream_id;

    RETURN v_after - v_before;
END;
$$;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.try_finalize(
    p_stream_id text,
    p_finalize_through timestamptz,
    p_provider_finality_floor timestamptz,
    p_min_reconciliation_snapshot_at timestamptz
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_state history_reconcile_evidence.stream_state%ROWTYPE;
    v_current_covered timestamptz;
BEGIN
    SELECT * INTO v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    IF v_state.state = 'gap' THEN
        RETURN false;
    END IF;

    SELECT history_reconcile_evidence.contiguous_covered_through(
        p_stream_id,
        p_min_reconciliation_snapshot_at
    ) INTO v_current_covered;

    -- Completeness needs all three conditions:
    --   1. provider finality covers the requested event-time boundary;
    --   2. reconciliation coverage is contiguous from supported_history_floor;
    --   3. every interval used for that coverage was swept at/after the
    --      minimum snapshot currentness required by this finalization.
    IF p_finalize_through > p_provider_finality_floor
       OR v_current_covered IS NULL
       OR v_current_covered < p_finalize_through THEN
        UPDATE history_reconcile_evidence.stream_state
           SET state = 'reconciliation_required'
         WHERE stream_id = p_stream_id;
        RETURN false;
    END IF;

    UPDATE history_reconcile_evidence.stream_state
       SET finalized_through = CASE
               WHEN finalized_through IS NULL THEN p_finalize_through
               ELSE GREATEST(finalized_through, p_finalize_through)
           END,
           state = 'complete'
     WHERE stream_id = p_stream_id;
    RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.record_unrecoverable_gap(
    p_stream_id text,
    p_gap_from timestamptz,
    p_gap_to timestamptz
)
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
BEGIN
    IF p_gap_from > p_gap_to THEN
        RAISE EXCEPTION 'invalid gap interval';
    END IF;

    UPDATE history_reconcile_evidence.stream_state
       SET state = 'gap',
           gap_from = p_gap_from,
           gap_to = p_gap_to,
           finalized_through = CASE
               WHEN finalized_through IS NULL THEN NULL
               ELSE LEAST(finalized_through, p_gap_from)
           END
     WHERE stream_id = p_stream_id;
END;
$$;

-- A provisional high-water mark has moved ahead. One provider observation from
-- an older time becomes visible only after the ordinary fast-overlap floor has
-- already advanced past it.
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id,
    provisional_high_water,
    fast_overlap_floor,
    supported_history_floor,
    state
) VALUES (
    'zabbix:item:42',
    '2026-08-28T12:00:00Z',
    '2026-08-28T11:55:00Z',
    '2026-08-27T00:00:00Z',
    'provisional'
);

INSERT INTO history_reconcile_evidence.provider_visible_history (
    stream_id, observation_id, observed_at, became_visible_at, numeric_value
) VALUES
    (
        'zabbix:item:42',
        '01010101-0101-0101-0101-010101010101',
        '2026-08-28T11:58:00Z',
        '2026-08-28T11:58:05Z',
        1
    ),
    (
        'zabbix:item:42',
        '02020202-0202-0202-0202-020202020202',
        '2026-08-28T10:30:00Z',
        '2026-08-28T12:10:00Z',
        2
    );

-- Fast overlap at 12:00 sees only the recent row. Because it starts above the
-- supported history floor, it MUST NOT create anchored completeness coverage.
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42',
    '2026-08-28T11:55:00Z',
    '2026-08-28T12:00:00Z',
    '2026-08-28T12:00:00Z'
);

DO $$
DECLARE
    v_rows bigint;
    v_covered timestamptz;
    v_finalized boolean;
BEGIN
    SELECT count(*) INTO v_rows
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = 'zabbix:item:42';
    IF v_rows <> 1 THEN
        RAISE EXCEPTION 'fast overlap expected one visible row, got %', v_rows;
    END IF;

    SELECT reconciliation_covered_through INTO v_covered
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = 'zabbix:item:42';
    IF v_covered IS NOT NULL THEN
        RAISE EXCEPTION 'disjoint high sweep fabricated anchored coverage through %', v_covered;
    END IF;

    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'high-only sweep fabricated complete watermark';
    END IF;
END;
$$;

-- Sweep from the supported floor only to 10:00. The run set now has a low
-- interval and a high interval but still contains a real hole (10:00..11:55).
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42',
    '2026-08-27T00:00:00Z',
    '2026-08-28T10:00:00Z',
    '2026-08-28T12:15:00Z'
);

DO $$
DECLARE
    v_covered timestamptz;
    v_max_window_to timestamptz;
    v_finalized boolean;
BEGIN
    SELECT reconciliation_covered_through INTO v_covered
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = 'zabbix:item:42';
    IF v_covered IS DISTINCT FROM '2026-08-28T10:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'contiguous coverage crossed unswept interval: %', v_covered;
    END IF;

    SELECT max(window_to) INTO v_max_window_to
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id = 'zabbix:item:42';
    IF v_max_window_to IS DISTINCT FROM '2026-08-28T12:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'negative vector did not retain a misleading high window endpoint: %', v_max_window_to;
    END IF;

    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:15:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'disjoint sweeps fabricated completeness from max(window_to)';
    END IF;
END;
$$;

-- Bridge the actual hole using a sufficiently current provider snapshot. This
-- also recovers the delayed 10:30 observation that was invisible earlier.
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42',
    '2026-08-28T10:00:00Z',
    '2026-08-28T12:00:00Z',
    '2026-08-28T12:15:00Z'
);

DO $$
DECLARE
    v_rows bigint;
    v_late bigint;
    v_covered timestamptz;
    v_finalized boolean;
BEGIN
    SELECT count(*) INTO v_rows
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = 'zabbix:item:42';
    SELECT count(*) INTO v_late
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id = 'zabbix:item:42'
       AND observation_id = '02020202-0202-0202-0202-020202020202'::uuid;
    SELECT reconciliation_covered_through INTO v_covered
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = 'zabbix:item:42';

    IF v_rows <> 2 OR v_late <> 1 THEN
        RAISE EXCEPTION 'bridging reconciliation failed to recover late history rows=% late=%',
            v_rows, v_late;
    END IF;
    IF v_covered IS DISTINCT FROM '2026-08-28T12:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'bridging sweep failed to establish contiguous coverage: %', v_covered;
    END IF;

    -- Even complete interval geometry cannot be reused for a finalization that
    -- requires a newer reconciliation snapshot than any covering run.
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:16:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'stale reconciliation snapshot fabricated current completeness';
    END IF;

    -- At the snapshot actually used by the covering sweeps, provider finality
    -- and anchored contiguous reconciliation both prove the region complete.
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:15:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'eligible contiguous/current reconciliation failed finalization';
    END IF;
END;
$$;

-- A second stream models provider retention having already discarded an interval
-- before reconciliation could prove it. The system must record an explicit gap
-- instead of advancing a fabricated complete watermark.
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id,
    provisional_high_water,
    fast_overlap_floor,
    supported_history_floor,
    state
) VALUES (
    'zabbix:item:retention-loss',
    '2026-08-28T12:00:00Z',
    '2026-08-28T11:55:00Z',
    '2026-08-28T11:00:00Z',
    'reconciliation_required'
);

SELECT history_reconcile_evidence.record_unrecoverable_gap(
    'zabbix:item:retention-loss',
    '2026-08-28T09:00:00Z',
    '2026-08-28T11:00:00Z'
);

DO $$
DECLARE
    v_state history_reconcile_evidence.completeness_state;
    v_finalized boolean;
BEGIN
    SELECT state INTO v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = 'zabbix:item:retention-loss';
    IF v_state <> 'gap' THEN
        RAISE EXCEPTION 'retention loss did not produce durable gap state: %', v_state;
    END IF;

    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:retention-loss',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:00:00Z',
        '2026-08-28T12:15:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'stream with unrecoverable gap fabricated completeness';
    END IF;
END;
$$;

SELECT
    'late_history_reconciliation=PASS' AS result,
    stream_id,
    state,
    reconciliation_covered_from,
    reconciliation_covered_through,
    finalized_through,
    gap_from,
    gap_to
FROM history_reconcile_evidence.stream_state
ORDER BY stream_id;
