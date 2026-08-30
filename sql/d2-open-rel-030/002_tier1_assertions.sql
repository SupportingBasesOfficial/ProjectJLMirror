\set ON_ERROR_STOP on

-- Constants for the primary source vector:
-- tenant 1111..., source 1010..., generation 3333..., metric 2222...
DO $$
DECLARE
    v_count bigint;
BEGIN
    SELECT count(*) INTO v_count
      FROM tel_evidence.observation
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
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
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_count <> 1 THEN
        RAISE EXCEPTION 'initial semantic signal cardinality expected 1, got %', v_count;
    END IF;
END;
$$;

-- Same canonical identity under a newer admitted ordering token: order/fence may
-- advance, but semantic current state and signal identity do not change.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    'zabbix:source:metric',
    '44444444-4444-4444-4444-444444444444'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
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
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_generation <> 101 THEN
        RAISE EXCEPTION 'repeated-current ordering fence did not advance: %', v_generation;
    END IF;

    SELECT count(*) INTO v_signals
      FROM tel_evidence.current_changed_outbox
     WHERE tenant_id = '11111111-1111-1111-1111-111111111111'::uuid
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_signals <> 1 THEN
        RAISE EXCEPTION 'repeated-current manufactured semantic signal(s): %', v_signals;
    END IF;
END;
$$;

-- Codex P1 class: a replay cannot reuse a canonical identity with different
-- immutable content. The conflicting attempt must roll back completely, not be
-- interpreted as a duplicate and not use attacker/replay parameters for current
-- state.
DO $$
DECLARE
    v_value numeric;
    v_history bigint;
BEGIN
    BEGIN
        PERFORM * FROM tel_evidence.accept_observation(
            '11111111-1111-1111-1111-111111111111'::uuid,
            '10101010-1010-1010-1010-101010101010'::uuid,
            'zabbix:source:metric',
            '44444444-4444-4444-4444-444444444444'::uuid,
            '22222222-2222-2222-2222-222222222222'::uuid,
            '33333333-3333-3333-3333-333333333333'::uuid,
            10, 104,
            '2026-08-28T12:00:00Z'::timestamptz,
            420.0,
            true,
            NULL
        );
        RAISE EXCEPTION 'conflicting canonical observation content was accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM <> 'observation identity content mismatch' THEN
                RAISE;
            END IF;
    END;

    SELECT numeric_value INTO v_value
      FROM tel_evidence.observation
     WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
       AND observation_identity_scope='zabbix:source:metric'
       AND observation_id='44444444-4444-4444-4444-444444444444'::uuid;
    IF v_value <> 42.0 THEN
        RAISE EXCEPTION 'canonical observation content mutated after conflict: %', v_value;
    END IF;

    SELECT count(*) INTO v_history
      FROM tel_evidence.historical_projection_outbox
     WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
       AND observation_identity_scope='zabbix:source:metric'
       AND observation_id='44444444-4444-4444-4444-444444444444'::uuid;
    IF v_history <> 1 THEN
        RAISE EXCEPTION 'identity conflict changed historical obligation cardinality: %', v_history;
    END IF;
END;
$$;

-- A different observation with a numerically larger provider timestamp but a
-- valid yet stale owner ordering token is accepted historically and cannot
-- regress the current projection.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    'zabbix:source:metric',
    '55555555-5555-5555-5555-555555555555'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
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
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
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

-- Historical acceptance and current candidacy are independent.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    'zabbix:source:metric',
    '66666666-6666-6666-6666-666666666666'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333333'::uuid,
    10, 102,
    '2026-08-28T11:00:00Z'::timestamptz,
    43.0,
    false,
    NULL
);
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    'zabbix:source:metric',
    '66666666-6666-6666-6666-666666666666'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
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
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_observation <> '66666666-6666-6666-6666-666666666666'::uuid THEN
        RAISE EXCEPTION 'already-accepted observation failed later current candidacy: %', v_observation;
    END IF;
END;
$$;

-- Provider event time can move backwards while owner ordering moves forward.
SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    'zabbix:source:metric',
    '77777777-7777-7777-7777-777777777777'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
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
       AND source_id = '10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id = '22222222-2222-2222-2222-222222222222'::uuid;
    IF v_observation <> '77777777-7777-7777-7777-777777777777'::uuid THEN
        RAISE EXCEPTION 'provider event-time rollback incorrectly froze current state: %', v_observation;
    END IF;
END;
$$;

-- Owner-ordering authority cannot be invented by the caller. No durable claim
-- exists for generation 105; the whole attempt, including first acceptance and
-- historical intent, must roll back.
DO $$
DECLARE
    v_rows bigint;
BEGIN
    BEGIN
        PERFORM * FROM tel_evidence.accept_observation(
            '11111111-1111-1111-1111-111111111111'::uuid,
            '10101010-1010-1010-1010-101010101010'::uuid,
            'zabbix:source:metric',
            '70707070-7070-7070-7070-707070707070'::uuid,
            '22222222-2222-2222-2222-222222222222'::uuid,
            '33333333-3333-3333-3333-333333333333'::uuid,
            10, 105,
            '2026-08-28T14:00:00Z'::timestamptz,
            70.0,
            true,
            NULL
        );
        RAISE EXCEPTION 'fabricated poll generation was accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM <> 'missing or retired durable poll claim' THEN RAISE; END IF;
    END;
    SELECT count(*) INTO v_rows FROM tel_evidence.observation
     WHERE observation_id='70707070-7070-7070-7070-707070707070'::uuid;
    IF v_rows <> 0 THEN RAISE EXCEPTION 'fabricated poll claim left accepted history'; END IF;
END;
$$;

-- A claim that once existed but is retired is equally non-authoritative.
UPDATE tel_evidence.poll_claim
   SET claim_state='retired'
 WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
   AND source_id='10101010-1010-1010-1010-101010101010'::uuid
   AND source_instance_generation='33333333-3333-3333-3333-333333333333'::uuid
   AND poll_epoch=10 AND poll_generation=104;
DO $$
BEGIN
    BEGIN
        PERFORM * FROM tel_evidence.accept_observation(
            '11111111-1111-1111-1111-111111111111'::uuid,
            '10101010-1010-1010-1010-101010101010'::uuid,
            'zabbix:source:metric',
            '71717171-7171-7171-7171-717171717171'::uuid,
            '22222222-2222-2222-2222-222222222222'::uuid,
            '33333333-3333-3333-3333-333333333333'::uuid,
            10, 104,
            '2026-08-28T14:01:00Z'::timestamptz,
            71.0,
            true,
            NULL
        );
        RAISE EXCEPTION 'retired poll claim was accepted';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM <> 'missing or retired durable poll claim' THEN RAISE; END IF;
    END;
END;
$$;

-- Codex P1 source-generation class: replacement changes owner-controlled source
-- authority. Even though old poll claims still exist, the stale generation
-- cannot use them to mutate current state. Only a successor claim under the new
-- epoch may advance current state.
UPDATE tel_evidence.monitoring_source_authority
   SET active_source_instance_generation='33333333-3333-3333-3333-333333333334'::uuid,
       active_poll_epoch=11,
       placement_version=2
 WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
   AND source_id='10101010-1010-1010-1010-101010101010'::uuid;
INSERT INTO tel_evidence.poll_claim (
    tenant_id, source_id, source_instance_generation, poll_epoch, poll_generation, claim_state
) VALUES (
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    '33333333-3333-3333-3333-333333333334'::uuid,
    11, 1, 'live'
);

DO $$
DECLARE
    v_before uuid;
    v_after uuid;
    v_rows bigint;
BEGIN
    SELECT observation_id INTO v_before FROM tel_evidence.metric_current_state
     WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
       AND source_id='10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id='22222222-2222-2222-2222-222222222222'::uuid;
    BEGIN
        PERFORM * FROM tel_evidence.accept_observation(
            '11111111-1111-1111-1111-111111111111'::uuid,
            '10101010-1010-1010-1010-101010101010'::uuid,
            'zabbix:source:metric',
            '72727272-7272-7272-7272-727272727272'::uuid,
            '22222222-2222-2222-2222-222222222222'::uuid,
            '33333333-3333-3333-3333-333333333333'::uuid,
            10, 103,
            '2026-08-28T14:02:00Z'::timestamptz,
            72.0,
            true,
            NULL
        );
        RAISE EXCEPTION 'retired source generation mutated current state';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM <> 'stale source generation current candidate' THEN RAISE; END IF;
    END;
    SELECT observation_id INTO v_after FROM tel_evidence.metric_current_state
     WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
       AND source_id='10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id='22222222-2222-2222-2222-222222222222'::uuid;
    IF v_after <> v_before THEN RAISE EXCEPTION 'stale source changed current row'; END IF;
    SELECT count(*) INTO v_rows FROM tel_evidence.observation
     WHERE observation_id='72727272-7272-7272-7272-727272727272'::uuid;
    IF v_rows <> 0 THEN RAISE EXCEPTION 'stale current attempt escaped transaction rollback'; END IF;
END;
$$;

SELECT * FROM tel_evidence.accept_observation(
    '11111111-1111-1111-1111-111111111111'::uuid,
    '10101010-1010-1010-1010-101010101010'::uuid,
    'zabbix:source:metric:g2',
    '73737373-7373-7373-7373-737373737373'::uuid,
    '22222222-2222-2222-2222-222222222222'::uuid,
    '33333333-3333-3333-3333-333333333334'::uuid,
    11, 1,
    '2019-01-01T00:00:00Z'::timestamptz,
    73.0,
    true,
    NULL
);
DO $$
DECLARE
    v_state text;
BEGIN
    SELECT source_instance_generation::text||'|'||poll_epoch||'|'||poll_generation||'|'||observation_id::text
      INTO v_state
      FROM tel_evidence.metric_current_state
     WHERE tenant_id='11111111-1111-1111-1111-111111111111'::uuid
       AND source_id='10101010-1010-1010-1010-101010101010'::uuid
       AND metric_definition_id='22222222-2222-2222-2222-222222222222'::uuid;
    IF v_state <> '33333333-3333-3333-3333-333333333334|11|1|73737373-7373-7373-7373-737373737373' THEN
        RAISE EXCEPTION 'successor generation failed authoritative cutover: %', v_state;
    END IF;
END;
$$;

-- Crash injection under a separate owner-controlled source.
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
        v_observation := ('88888888-8888-8888-8888-' || lpad(v_suffix::text, 12, '0'))::uuid;
        BEGIN
            PERFORM * FROM tel_evidence.accept_observation(
                'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid,
                'abababab-abab-abab-abab-abababababab'::uuid,
                'crash-vector',
                v_observation,
                'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid,
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
                IF SQLERRM <> 'injected:' || v_failpoint THEN RAISE; END IF;
        END;

        SELECT count(*) INTO v_rows FROM tel_evidence.observation
         WHERE tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid
           AND observation_id=v_observation;
        IF v_rows <> 0 THEN RAISE EXCEPTION 'partial observation survived failpoint %', v_failpoint; END IF;

        SELECT count(*) INTO v_rows FROM tel_evidence.historical_projection_outbox
         WHERE tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid
           AND observation_id=v_observation;
        IF v_rows <> 0 THEN RAISE EXCEPTION 'partial historical intent survived failpoint %', v_failpoint; END IF;
    END LOOP;

    SELECT count(*) INTO v_rows FROM tel_evidence.metric_current_state
     WHERE tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;
    IF v_rows <> 0 THEN RAISE EXCEPTION 'partial current state survived crash matrix: %', v_rows; END IF;

    SELECT count(*) INTO v_rows FROM tel_evidence.current_changed_outbox
     WHERE tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;
    IF v_rows <> 0 THEN RAISE EXCEPTION 'partial current signal survived crash matrix: %', v_rows; END IF;
END;
$$;

-- Tier 2 intentionally absent: bounded historical acceptance accumulates durable
-- projection obligations without requiring current-source authority.
DO $$
DECLARE
    i integer;
    v_observation uuid;
    v_observations bigint;
    v_outbox bigint;
BEGIN
    FOR i IN 1..300 LOOP
        v_observation := ('99999999-9999-9999-9999-' || lpad(i::text, 12, '0'))::uuid;
        PERFORM * FROM tel_evidence.accept_observation(
            'dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid,
            'd0d0d0d0-d0d0-d0d0-d0d0-d0d0d0d0d0d0'::uuid,
            'tier2-backlog',
            v_observation,
            'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'::uuid,
            'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid,
            1, i,
            '2026-08-28T00:00:00Z'::timestamptz + make_interval(secs => i),
            i,
            false,
            NULL
        );
    END LOOP;

    SELECT count(*) INTO v_observations FROM tel_evidence.observation
     WHERE tenant_id='dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid
       AND observation_identity_scope='tier2-backlog';
    SELECT count(*) INTO v_outbox FROM tel_evidence.historical_projection_outbox
     WHERE tenant_id='dddddddd-dddd-dddd-dddd-dddddddddddd'::uuid
       AND observation_identity_scope='tier2-backlog';

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
