\set ON_ERROR_STOP on

DROP SCHEMA IF EXISTS history_reconcile_evidence CASCADE;
DROP ROLE IF EXISTS history_reconcile_worker;
DROP ROLE IF EXISTS history_reconcile_owner;

CREATE ROLE history_reconcile_owner
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE history_reconcile_worker
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

CREATE SCHEMA history_reconcile_evidence AUTHORIZATION history_reconcile_owner;
GRANT USAGE ON SCHEMA history_reconcile_evidence TO history_reconcile_worker;

SET ROLE history_reconcile_owner;

CREATE TYPE history_reconcile_evidence.completeness_state AS ENUM (
    'provisional',
    'reconciliation_required',
    'complete',
    'gap'
);

-- Durable owner/provider currentness authority. Workers can never supply these
-- timestamps as finalization facts. Every sweep binds to one exact generation.
CREATE TABLE history_reconcile_evidence.provider_authority (
    stream_id text PRIMARY KEY,
    authority_generation bigint NOT NULL CHECK (authority_generation > 0),
    current_snapshot_at timestamptz NOT NULL,
    finality_floor timestamptz NOT NULL,
    required_reconciliation_snapshot_at timestamptz NOT NULL,
    CHECK (finality_floor <= current_snapshot_at),
    CHECK (required_reconciliation_snapshot_at <= current_snapshot_at)
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
    authority_generation bigint NOT NULL,
    window_from timestamptz NOT NULL,
    window_to timestamptz NOT NULL,
    provider_snapshot_at timestamptz NOT NULL,
    discovered_count bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (window_from <= window_to)
);

-- Owner-only authority transition. The worker receives no EXECUTE privilege.
CREATE OR REPLACE FUNCTION history_reconcile_evidence.advance_provider_authority(
    p_stream_id text,
    p_expected_generation bigint,
    p_current_snapshot_at timestamptz,
    p_finality_floor timestamptz,
    p_required_reconciliation_snapshot_at timestamptz
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_current history_reconcile_evidence.provider_authority%ROWTYPE;
    v_next bigint;
BEGIN
    SELECT * INTO v_current
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown provider authority';
    END IF;
    IF v_current.authority_generation <> p_expected_generation THEN
        RAISE EXCEPTION 'provider authority generation mismatch';
    END IF;
    IF p_current_snapshot_at < v_current.current_snapshot_at
       OR p_finality_floor < v_current.finality_floor
       OR p_required_reconciliation_snapshot_at < v_current.required_reconciliation_snapshot_at
       OR p_finality_floor > p_current_snapshot_at
       OR p_required_reconciliation_snapshot_at > p_current_snapshot_at THEN
        RAISE EXCEPTION 'provider authority regression or invalid currentness';
    END IF;

    v_next := v_current.authority_generation + 1;
    UPDATE history_reconcile_evidence.provider_authority
       SET authority_generation = v_next,
           current_snapshot_at = p_current_snapshot_at,
           finality_floor = p_finality_floor,
           required_reconciliation_snapshot_at = p_required_reconciliation_snapshot_at
     WHERE stream_id = p_stream_id;
    RETURN v_next;
END;
$$;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.contiguous_covered_through(
    p_stream_id text,
    p_min_provider_snapshot_at timestamptz
)
RETURNS timestamptz
LANGUAGE plpgsql
SECURITY DEFINER
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

-- Worker supplies only the window and the generation it believes current. The
-- actual snapshot timestamp is resolved and locked from owner authority here.
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
        p_stream_id, '-infinity'::timestamptz
    ) INTO v_covered;

    UPDATE history_reconcile_evidence.stream_state
       SET reconciliation_covered_from = CASE WHEN v_covered IS NULL THEN NULL ELSE v_supported_floor END,
           reconciliation_covered_through = v_covered,
           state = CASE WHEN state = 'gap' THEN state ELSE 'provisional' END
     WHERE stream_id = p_stream_id;

    RETURN v_after - v_before;
END;
$$;

-- Finalization takes no caller-provided finality/currentness timestamp. Both are
-- locked and derived from owner/provider authority in the same transaction.
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
    v_finality_floor timestamptz;
    v_required_snapshot timestamptz;
    v_current_covered timestamptz;
BEGIN
    SELECT * INTO v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream';
    END IF;

    SELECT finality_floor, required_reconciliation_snapshot_at
      INTO v_finality_floor, v_required_snapshot
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id = p_stream_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown provider authority';
    END IF;

    IF v_state.state = 'gap' THEN
        RETURN false;
    END IF;

    SELECT history_reconcile_evidence.contiguous_covered_through(
        p_stream_id, v_required_snapshot
    ) INTO v_current_covered;

    IF p_finalize_through > v_finality_floor
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
       SET state = 'gap', gap_from = p_gap_from, gap_to = p_gap_to,
           finalized_through = CASE
               WHEN finalized_through IS NULL THEN NULL
               ELSE LEAST(finalized_through, p_gap_from)
           END
     WHERE stream_id = p_stream_id;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA history_reconcile_evidence FROM PUBLIC, history_reconcile_worker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA history_reconcile_evidence FROM PUBLIC;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint)
  TO history_reconcile_worker;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.try_finalize(text,timestamptz)
  TO history_reconcile_worker;

RESET ROLE;

-- Owner/provider authority begins at snapshot 12:00, but finality has not yet
-- reached the requested 12:00 event-time boundary.
INSERT INTO history_reconcile_evidence.provider_authority (
    stream_id, authority_generation, current_snapshot_at, finality_floor,
    required_reconciliation_snapshot_at
) VALUES (
    'zabbix:item:42', 1,
    '2026-08-28T12:00:00Z', '2026-08-28T11:50:00Z', '2026-08-28T12:00:00Z'
);

INSERT INTO history_reconcile_evidence.stream_state (
    stream_id, provisional_high_water, fast_overlap_floor, supported_history_floor, state
) VALUES (
    'zabbix:item:42', '2026-08-28T12:00:00Z', '2026-08-28T11:55:00Z',
    '2026-08-27T00:00:00Z', 'provisional'
);

INSERT INTO history_reconcile_evidence.provider_visible_history (
    stream_id, observation_id, observed_at, became_visible_at, numeric_value
) VALUES
    ('zabbix:item:42','01010101-0101-0101-0101-010101010101','2026-08-28T11:58:00Z','2026-08-28T11:58:05Z',1),
    ('zabbix:item:42','02020202-0202-0202-0202-020202020202','2026-08-28T10:30:00Z','2026-08-28T12:10:00Z',2);

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-28T11:55:00Z','2026-08-28T12:00:00Z',1
);
RESET ROLE;

DO $$
DECLARE v_rows bigint; v_covered timestamptz; v_finalized boolean;
BEGIN
    SELECT count(*) INTO v_rows FROM history_reconcile_evidence.accepted_history
     WHERE stream_id='zabbix:item:42';
    IF v_rows <> 1 THEN RAISE EXCEPTION 'fast overlap expected one row, got %', v_rows; END IF;
    SELECT reconciliation_covered_through INTO v_covered FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:42';
    IF v_covered IS NOT NULL THEN RAISE EXCEPTION 'high sweep fabricated anchored coverage'; END IF;
    SELECT history_reconcile_evidence.try_finalize('zabbix:item:42','2026-08-28T12:00:00Z') INTO v_finalized;
    IF v_finalized THEN RAISE EXCEPTION 'finalized before owner finality'; END IF;
END;
$$;

-- The worker cannot mutate provider-currentness authority directly.
SET ROLE history_reconcile_worker;
DO $$
BEGIN
    BEGIN
        PERFORM history_reconcile_evidence.advance_provider_authority(
            'zabbix:item:42',1,'2099-01-01Z','2099-01-01Z','2099-01-01Z'
        );
        RAISE EXCEPTION 'worker unexpectedly advanced provider authority';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END;
$$;
RESET ROLE;

-- Owner advances durable authority to generation 2 / snapshot 12:15.
SELECT history_reconcile_evidence.advance_provider_authority(
    'zabbix:item:42',1,'2026-08-28T12:15:00Z','2026-08-28T12:00:00Z','2026-08-28T12:15:00Z'
);

-- A stale worker generation is rejected; it cannot self-assert a fresh snapshot.
DO $$
BEGIN
    BEGIN
        PERFORM history_reconcile_evidence.sweep(
            'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T10:00:00Z',1
        );
        RAISE EXCEPTION 'stale reconciliation generation unexpectedly accepted';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%stale reconciliation worker authority%' THEN RAISE; END IF;
    END;
END;
$$;

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T10:00:00Z',2
);
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-28T10:00:00Z','2026-08-28T12:00:00Z',2
);
RESET ROLE;

DO $$
DECLARE v_rows bigint; v_late bigint; v_covered timestamptz;
BEGIN
    SELECT count(*) INTO v_rows FROM history_reconcile_evidence.accepted_history
     WHERE stream_id='zabbix:item:42';
    SELECT count(*) INTO v_late FROM history_reconcile_evidence.accepted_history
     WHERE stream_id='zabbix:item:42'
       AND observation_id='02020202-0202-0202-0202-020202020202'::uuid;
    SELECT reconciliation_covered_through INTO v_covered FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:42';
    IF v_rows <> 2 OR v_late <> 1 THEN RAISE EXCEPTION 'late history not recovered'; END IF;
    IF v_covered IS DISTINCT FROM '2026-08-28T12:00:00Z'::timestamptz THEN
        RAISE EXCEPTION 'gen2 contiguous coverage incorrect: %', v_covered;
    END IF;
END;
$$;

-- Owner now requires reconciliation current through snapshot 12:16. Existing
-- generation-2 runs at 12:15 cannot satisfy this stronger currentness authority.
SELECT history_reconcile_evidence.advance_provider_authority(
    'zabbix:item:42',2,'2026-08-28T12:16:00Z','2026-08-28T12:00:00Z','2026-08-28T12:16:00Z'
);

DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize('zabbix:item:42','2026-08-28T12:00:00Z') INTO v_finalized;
    IF v_finalized THEN RAISE EXCEPTION 'stale 12:15 runs satisfied 12:16 owner currentness'; END IF;
END;
$$;

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T12:00:00Z',3
);
RESET ROLE;

DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize('zabbix:item:42','2026-08-28T12:00:00Z') INTO v_finalized;
    IF NOT v_finalized THEN RAISE EXCEPTION 'owner-current gen3 full sweep failed to finalize'; END IF;
END;
$$;

-- Separate stream demonstrates unrecoverable provider retention loss remains a
-- durable gap and can never become false complete.
INSERT INTO history_reconcile_evidence.provider_authority (
    stream_id, authority_generation, current_snapshot_at, finality_floor,
    required_reconciliation_snapshot_at
) VALUES (
    'zabbix:item:retention-loss',1,'2026-08-28T12:16:00Z','2026-08-28T12:00:00Z','2026-08-28T12:16:00Z'
);
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id, supported_history_floor, state
) VALUES ('zabbix:item:retention-loss','2026-08-27T00:00:00Z','provisional');
SELECT history_reconcile_evidence.record_unrecoverable_gap(
    'zabbix:item:retention-loss','2026-08-28T09:00:00Z','2026-08-28T11:00:00Z'
);

DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
      'zabbix:item:retention-loss','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN RAISE EXCEPTION 'gap stream falsely finalized'; END IF;
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

SELECT 'history_owner_currentness_authority=PASS' AS result;
