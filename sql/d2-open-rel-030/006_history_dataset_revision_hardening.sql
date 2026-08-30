\set ON_ERROR_STOP on

-- Panoramic hardening for provider-visible dataset mutation after a successful
-- sweep. Authority generation answers "which owner authority is current";
-- provider_dataset_revision answers "which immutable owner-visible dataset was
-- actually swept". Every provider-visible INSERT/UPDATE atomically advances the
-- dataset revision and invalidates materialized coverage. DELETE and stable
-- identity rewrites fail closed and require an explicit gap/authority workflow.
SET ROLE history_reconcile_owner;

ALTER TABLE history_reconcile_evidence.provider_authority
  ADD COLUMN provider_dataset_revision bigint NOT NULL DEFAULT 1
  CHECK (provider_dataset_revision > 0);

-- Existing runs predate dataset-version binding and are intentionally marked
-- revision 0, which can never equal a current provider dataset revision.
ALTER TABLE history_reconcile_evidence.reconciliation_run
  ADD COLUMN provider_dataset_revision bigint NOT NULL DEFAULT 0
  CHECK (provider_dataset_revision >= 0);

UPDATE history_reconcile_evidence.stream_state
   SET reconciliation_covered_from = NULL,
       reconciliation_covered_through = NULL,
       state = CASE
           WHEN state = 'gap' THEN state
           ELSE 'reconciliation_required'::history_reconcile_evidence.completeness_state
       END;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.invalidate_provider_dataset(
    p_stream_id text
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_revision bigint;
BEGIN
    UPDATE history_reconcile_evidence.provider_authority
       SET provider_dataset_revision = provider_dataset_revision + 1
     WHERE stream_id = p_stream_id
     RETURNING provider_dataset_revision INTO v_revision;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'provider history mutation without provider authority';
    END IF;

    UPDATE history_reconcile_evidence.stream_state
       SET reconciliation_covered_from = NULL,
           reconciliation_covered_through = NULL,
           state = CASE
               WHEN state = 'gap' THEN state
               ELSE 'reconciliation_required'::history_reconcile_evidence.completeness_state
           END
     WHERE stream_id = p_stream_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'provider history mutation without stream state';
    END IF;

    RETURN v_revision;
END;
$$;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.provider_history_mutation_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'provider history deletion requires explicit gap authority';
    END IF;

    IF TG_OP = 'UPDATE'
       AND (OLD.stream_id IS DISTINCT FROM NEW.stream_id
            OR OLD.observation_id IS DISTINCT FROM NEW.observation_id) THEN
        RAISE EXCEPTION 'provider history stable identity mutation prohibited';
    END IF;

    PERFORM history_reconcile_evidence.invalidate_provider_dataset(NEW.stream_id);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS provider_history_revision_guard
  ON history_reconcile_evidence.provider_visible_history;
CREATE TRIGGER provider_history_revision_guard
BEFORE INSERT OR UPDATE OR DELETE
ON history_reconcile_evidence.provider_visible_history
FOR EACH ROW
EXECUTE FUNCTION history_reconcile_evidence.provider_history_mutation_guard();

-- Coverage is now bound to both owner authority generation and the exact
-- provider-visible dataset revision current under that authority lock.
CREATE OR REPLACE FUNCTION history_reconcile_evidence.contiguous_covered_through(
    p_stream_id text,
    p_authority_generation bigint,
    p_min_provider_snapshot_at timestamptz
)
RETURNS timestamptz
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
DECLARE
    v_floor timestamptz;
    v_dataset_revision bigint;
    v_covered timestamptz;
    v_started boolean := false;
    v_run record;
BEGIN
    SELECT s.supported_history_floor, a.provider_dataset_revision
      INTO v_floor, v_dataset_revision
      FROM history_reconcile_evidence.stream_state s
      JOIN history_reconcile_evidence.provider_authority a USING (stream_id)
     WHERE s.stream_id = p_stream_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown stream or provider authority';
    END IF;

    v_covered := v_floor;
    FOR v_run IN
        SELECT window_from, window_to
          FROM history_reconcile_evidence.reconciliation_run
         WHERE stream_id = p_stream_id
           AND authority_generation = p_authority_generation
           AND provider_dataset_revision = v_dataset_revision
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

-- Effective final sweep combines generation/currentness, cross-window stable
-- identity conflict detection, and dataset-revision binding. The authority row
-- is locked while provider rows are inspected and the run is minted; a
-- concurrent provider mutation must wait, then atomically advances the dataset
-- revision and invalidates the just-published coverage before it can commit.
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

REVOKE ALL ON FUNCTION history_reconcile_evidence.invalidate_provider_dataset(text) FROM PUBLIC, history_reconcile_worker;
REVOKE ALL ON FUNCTION history_reconcile_evidence.provider_history_mutation_guard() FROM PUBLIC, history_reconcile_worker;
REVOKE ALL ON FUNCTION history_reconcile_evidence.contiguous_covered_through(text,bigint,timestamptz) FROM PUBLIC, history_reconcile_worker;
REVOKE ALL ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION history_reconcile_evidence.sweep(text,timestamptz,timestamptz,bigint)
  TO history_reconcile_worker;

RESET ROLE;

-- Legacy pre-revision runs must never become current revision evidence.
DO $$
DECLARE v_bad bigint; v_covered timestamptz; v_state history_reconcile_evidence.completeness_state;
BEGIN
    SELECT count(*) INTO v_bad
      FROM history_reconcile_evidence.reconciliation_run
     WHERE provider_dataset_revision <> 0;
    IF v_bad <> 0 THEN
        RAISE EXCEPTION 'legacy reconciliation runs unexpectedly acquired current dataset revision';
    END IF;

    SELECT reconciliation_covered_through, state INTO v_covered, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:42';
    IF v_covered IS NOT NULL OR v_state <> 'reconciliation_required' THEN
        RAISE EXCEPTION 'dataset-revision installation retained pre-versioned coverage';
    END IF;
END;
$$;

-- Establish current full coverage under generation 4 / dataset revision 1.
SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T12:00:00Z',4
);
RESET ROLE;

DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'revision-1 full sweep failed to finalize';
    END IF;
END;
$$;

-- Critical negative from the Codex finding: new provider-visible content appears
-- after the completed sweep without any authority-generation transition, and is
-- already visible at the locked owner snapshot. The mutation itself must bump
-- dataset revision and invalidate coverage atomically.
INSERT INTO history_reconcile_evidence.provider_visible_history (
    stream_id, observation_id, observed_at, became_visible_at, numeric_value
) VALUES (
    'zabbix:item:42','03030303-0303-0303-0303-030303030303',
    '2026-08-28T11:30:00Z','2026-08-28T12:15:30Z',3
);

DO $$
DECLARE
    v_generation bigint;
    v_revision bigint;
    v_covered timestamptz;
    v_state history_reconcile_evidence.completeness_state;
    v_finalized boolean;
BEGIN
    SELECT authority_generation, provider_dataset_revision
      INTO v_generation, v_revision
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id='zabbix:item:42';
    SELECT reconciliation_covered_through, state
      INTO v_covered, v_state
      FROM history_reconcile_evidence.stream_state
     WHERE stream_id='zabbix:item:42';

    IF v_generation <> 4 OR v_revision <> 2 THEN
        RAISE EXCEPTION 'provider mutation did not advance dataset revision independently: gen %, rev %',
            v_generation, v_revision;
    END IF;
    IF v_covered IS NOT NULL OR v_state <> 'reconciliation_required' THEN
        RAISE EXCEPTION 'provider dataset mutation retained stale coverage';
    END IF;

    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'pre-mutation sweep finalized the mutated provider dataset';
    END IF;
END;
$$;

SELECT 'history_provider_mutation_invalidates_coverage=PASS' AS result;

-- A fresh sweep under the unchanged authority generation but new dataset
-- revision must discover the new row and may then re-establish completion.
SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T12:00:00Z',4
);
RESET ROLE;

DO $$
DECLARE v_finalized boolean; v_new bigint; v_revision bigint; v_run_revision bigint;
BEGIN
    SELECT count(*) INTO v_new
      FROM history_reconcile_evidence.accepted_history
     WHERE stream_id='zabbix:item:42'
       AND observation_id='03030303-0303-0303-0303-030303030303'::uuid;
    IF v_new <> 1 THEN
        RAISE EXCEPTION 'fresh dataset-revision sweep missed newly visible observation';
    END IF;

    SELECT provider_dataset_revision INTO v_revision
      FROM history_reconcile_evidence.provider_authority
     WHERE stream_id='zabbix:item:42';
    SELECT provider_dataset_revision INTO v_run_revision
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:42'
     ORDER BY run_id DESC LIMIT 1;
    IF v_run_revision <> v_revision THEN
        RAISE EXCEPTION 'reconciliation run not bound to current provider dataset revision';
    END IF;

    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'fresh dataset-revision sweep failed to re-establish completion';
    END IF;
END;
$$;

SELECT 'history_dataset_revision_bound_coverage=PASS' AS result;

-- Same-generation content correction also invalidates coverage before the
-- worker can inspect the conflict. The rejected sweep must not mint a run for
-- the new revision. Restoring canonical provider content itself creates another
-- revision and therefore requires another fresh sweep.
UPDATE history_reconcile_evidence.provider_visible_history
   SET numeric_value = 33
 WHERE stream_id='zabbix:item:42'
   AND observation_id='03030303-0303-0303-0303-030303030303'::uuid;

DO $$
DECLARE v_finalized boolean; v_runs_before bigint; v_runs_after bigint;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF v_finalized THEN
        RAISE EXCEPTION 'same-generation content mutation reused stale coverage';
    END IF;

    SELECT count(*) INTO v_runs_before
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:42';
    BEGIN
        PERFORM history_reconcile_evidence.sweep(
            'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T12:00:00Z',4
        );
        RAISE EXCEPTION 'conflicting same-generation provider mutation unexpectedly swept';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%reconciled observation identity content mismatch%' THEN
            RAISE;
        END IF;
    END;
    SELECT count(*) INTO v_runs_after
      FROM history_reconcile_evidence.reconciliation_run
     WHERE stream_id='zabbix:item:42';
    IF v_runs_after <> v_runs_before THEN
        RAISE EXCEPTION 'conflicting dataset revision minted reconciliation coverage';
    END IF;
END;
$$;

UPDATE history_reconcile_evidence.provider_visible_history
   SET numeric_value = 3
 WHERE stream_id='zabbix:item:42'
   AND observation_id='03030303-0303-0303-0303-030303030303'::uuid;

SET ROLE history_reconcile_worker;
SELECT history_reconcile_evidence.sweep(
    'zabbix:item:42','2026-08-27T00:00:00Z','2026-08-28T12:00:00Z',4
);
RESET ROLE;

DO $$
DECLARE v_finalized boolean;
BEGIN
    SELECT history_reconcile_evidence.try_finalize(
        'zabbix:item:42','2026-08-28T12:00:00Z'
    ) INTO v_finalized;
    IF NOT v_finalized THEN
        RAISE EXCEPTION 'restored provider dataset failed fresh-revision finalization';
    END IF;
END;
$$;

SELECT 'history_same_generation_dataset_mutation_fenced=PASS' AS result;

-- Destructive removal and identity rewriting are not silently translated into
-- a new snapshot. They require an explicit gap/authority workflow.
DO $$
BEGIN
    BEGIN
        DELETE FROM history_reconcile_evidence.provider_visible_history
         WHERE stream_id='zabbix:item:42'
           AND observation_id='03030303-0303-0303-0303-030303030303'::uuid;
        RAISE EXCEPTION 'provider history deletion unexpectedly allowed';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%provider history deletion requires explicit gap authority%' THEN
            RAISE;
        END IF;
    END;

    BEGIN
        UPDATE history_reconcile_evidence.provider_visible_history
           SET observation_id='04040404-0404-0404-0404-040404040404'::uuid
         WHERE stream_id='zabbix:item:42'
           AND observation_id='03030303-0303-0303-0303-030303030303'::uuid;
        RAISE EXCEPTION 'provider stable identity rewrite unexpectedly allowed';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%provider history stable identity mutation prohibited%' THEN
            RAISE;
        END IF;
    END;
END;
$$;

SELECT 'history_provider_destructive_mutation_fails_closed=PASS' AS result;
