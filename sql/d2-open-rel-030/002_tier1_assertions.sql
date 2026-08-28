\set ON_ERROR_STOP on

DO $$
DECLARE
    v_count bigint;
BEGIN
    SELECT count(*) INTO v_count
      FROM tel_evidence.observation
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND observation_identity_scope = 'zabbix:source:metric'
       AND observation_id = '44444444-4444-4444-4444-444444444444'::uuid;
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'concurrency acceptance cardinality expected 1, got %', v_count;
    END IF;

    SELECT count(*) INTO v_count
      FROM tel_evidence.historical_projection_outbox
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND observation_identity_scope = 'zabbix:source:metric'
       AND observation_id = '44444444-4444-4444-4444-444444444444'::uuid;
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'historical intent cardinality expected 1, got %', v_count;
    END IF;

    SELECT count(*) INTO v_count
      FROM tel_evidence.current_changed_outbox
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'initial semantic signal cardinality expected 1, got %', v_count;
    END IF;
END;
$$;

-- Re-reading the same canonical observation under a newer owner ordering token
-- advances only the fence/order evidence. It must not manufacture a second
-- semantic current-state transition.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    'zabbix:source:metric',
    '44444444-4444-4444-4444-444444444444'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    10, 101,
    '2026-08-28T12:00:00Z'::timestamptz,
    42.0,
    true,
    NULL
);

DO $$
DECLARE
    v_generation bigint;
    v_signals bigint;
BEGIN
    SELECT poll_generation INTO v_generation
      FROM tel_evidence.metric_current_state
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_generation <> 101 THEN
        RAISE EXCEPTION 'repeated-current ordering fence did not advance: %', v_generation;
    END IF;

    SELECT count(*) INTO v_signals
      FROM tel_evidence.current_changed_outbox
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_signals <> 1 THEN
        RAISE EXCEPTION 'repeated-current manufactured semantic signal(s): %', v_signals;
    END IF;
END;
$$;

-- A different observation with a numerically larger provider timestamp but a
-- stale owner ordering token is accepted historically and must not regress the
-- current projection.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    'zabbix:source:metric',
    '55555555-5555-5555-5555-555555555555'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    10, 99,
    '2036-08-28T12:00:00Z'::timestamptz,
    999.0,
    true,
    NULL
);

DO $$
DECLARE
    v_observation uuid;
    v_history bigint;
BEGIN
    SELECT observation_id INTO v_observation
      FROM tel_evidence.metric_current_state
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_observation <> '44444444-4444-4444-4444-444444444444'::uuid THEN
        RAISE EXCEPTION 'stale owner token regressed current state to %', v_observation;
    END IF;

    SELECT count(*) INTO v_history
      FROM tel_evidence.historical_projection_outbox
     WHERE observation_id = '55555555-5555-5555-5555-555555555555'::uuid;
    IF v_history <> 1 THEN
        RAISE EXCEPTION 'stale current candidate lost/duplicated historical obligation: %', v_history;
    END IF;
END;
$$;

-- Historical acceptance and current candidacy are independent. First accept as
-- history only, then encounter the same canonical observation through an
-- authoritative current snapshot.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    'zabbix:source:metric',
    '66666666-6666-6666-6666-666666666666'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    10, 102,
    '2026-08-28T11:00:00Z'::timestamptz,
    43.0,
    false,
    NULL
);
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    'zabbix:source:metric',
    '66666666-6666-6666-6666-666666666666'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    10, 102,
    '2026-08-28T11:00:00Z'::timestamptz,
    43.0,
    true,
    NULL
);

DO $$
DECLARE
    v_history bigint;
    v_observation uuid;
BEGIN
    SELECT count(*) INTO v_history
      FROM tel_evidence.historical_projection_outbox
     WHERE observation_id = '66666666-6666-6666-6666-666666666666'::uuid;
    IF v_history <> 1 THEN
        RAISE EXCEPTION 'history-first/current-later duplicated historical intent: %', v_history;
    END IF;

    SELECT observation_id INTO v_observation
      FROM tel_evidence.metric_current_state
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_observation <> '66666666-6666-6666-6666-666666666666'::uuid THEN
        RAISE EXCEPTION 'already-accepted observation failed later current candidacy: %', v_observation;
    END IF;
END;
$$;

-- Provider event time can move backwards while owner ordering moves forward.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    'zabbix:source:metric',
    '77777777-7777-7777-7777-777777777777'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    10, 103,
    '2020-01-01T00:00:00Z'::timestamptz,
    44.0,
    true,
    NULL
);

DO $$
DECLARE
    v_observation uuid;
BEGIN
    SELECT observation_id INTO v_observation
      FROM tel_evidence.metric_current_state
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_observation <> '77777777-7777-7777-7777-777777777777'::uuid THEN
        RAISE EXCEPTION 'provider event-time rollback incorrectly froze current state: %', v_observation;
    END IF;
END;
$$;

-- Crash injection: each failure occurs inside the same transaction and must
-- leave no partial acceptance, historical intent, current projection or signal.
DO $$
DECLARE
    v_failpoint text;
    v_observation uuid;
    v_suffix integer := 0;
    v_rows bigint;
BEGIN
    FOREACH v_failpoint IN ARRAY ARRAY[
        'after_observation',
        'after_history_intent',
        'after_current_cas',
        'after_transition_signal'
    ]
    LOOP
        v_suffix := v_suffix + 1;
        v_observation := (
            '88888888-8888-8888-8888-' || lpad(v_suffix::text, 12, '0')
        )::uuid;

        BEGIN
            PERFORM * FROM tel_evidence.accept_observation(
                'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
                'crash-vector',
                v_observation,
                'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
                'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid,
                'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid,
                1, v_suffix,
                clock_timestamp(),
                v_suffix,
                true,
                v_failpoint
            );
            RAISE EXCEPTION 'failpoint % did not fire', v_failpoint;
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLERRM <> 'injected:' || v_failpoint THEN
                    RAISE;
                END IF;
        END;

        SELECT count(*) INTO v_rows
          FROM tel_evidence.observation
         WHERE tenant_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid
           AND observation_id = v_observation;
        IF v_rows <> 0 THEN
            RAISE EXCEPTION 'partial observation survived failpoint %', v_failpoint;
        END IF;

        SELECT count(*) INTO v_rows
          FROM tel_evidence.historical_projection_outbox
         WHERE tenant_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid
           AND observation_id = v_observation;
        IF v_rows <> 0 THEN
            RAISE EXCEPTION 'partial historical intent survived failpoint %', v_failpoint;
        END IF;
    END LOOP;

    SELECT count(*) INTO v_rows
      FROM tel_evidence.metric_current_state
     WHERE tenant_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;
    IF v_rows <> 0 THEN
        RAISE EXCEPTION 'partial current state survived crash matrix: % row(s)', v_rows;
    END IF;

    SELECT count(*) INTO v_rows
      FROM tel_evidence.current_changed_outbox
     WHERE tenant_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;
    IF v_rows <> 0 THEN
        RAISE EXCEPTION 'partial current signal survived crash matrix: % row(s)', v_rows;
    END IF;
END;
$$;

-- Tier 2 is intentionally absent here. Tier 1 must continue to accept bounded
-- history and accumulate durable projection obligations rather than pretending
-- downstream projection already happened.
DO $$
DECLARE
    i integer;
    v_observation uuid;
    v_observations bigint;
    v_outbox bigint;
BEGIN
    FOR i IN 1..300 LOOP
        v_observation := (
            '99999999-9999-9999-9999-' || lpad(i::text, 12, '0')
        )::uuid;
        PERFORM * FROM tel_evidence.accept_observation(
            'dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid,
            'tier2-backlog',
            v_observation,
            'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'::uuid,
            'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid,
            'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid,
            1, i,
            '2026-08-28T00:00:00Z'::timestamptz + make_interval(secs => i),
            i,
            false,
            NULL
        );
    END LOOP;

    SELECT count(*) INTO v_observations
      FROM tel_evidence.observation
     WHERE tenant_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid
       AND observation_identity_scope = 'tier2-backlog';
    SELECT count(*) INTO v_outbox
      FROM tel_evidence.historical_projection_outbox
     WHERE tenant_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid
       AND observation_identity_scope = 'tier2-backlog';

    IF v_observations <> 300 OR v_outbox <> 300 THEN
        RAISE EXCEPTION 'Tier2-down backlog lost/duplicated durable responsibility observations=% outbox=%',
            v_observations, v_outbox;
    END IF;
END;
$$;

SELECT
    'tier1_assertions=PASS' AS result,
    pg_total_relation_size('tel_evidence.observation') AS observation_bytes,
    pg_total_relation_size('tel_evidence.historical_projection_outbox') AS historical_outbox_bytes,
    pg_total_relation_size('tel_evidence.metric_current_state') AS current_state_bytes,
    pg_total_relation_size('tel_evidence.current_changed_outbox') AS current_outbox_bytes;
