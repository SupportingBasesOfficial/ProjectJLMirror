\set ON_ERROR_STOP on

DROP SCHEMA IF EXISTS tel_evidence CASCADE;
CREATE SCHEMA tel_evidence;

CREATE TABLE tel_evidence.observation (
    tenant_id uuid NOT NULL,
    observation_identity_scope text NOT NULL,
    observation_id uuid NOT NULL,
    metric_definition_id uuid NOT NULL,
    source_instance_generation uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, observation_identity_scope, observation_id)
);

CREATE TABLE tel_evidence.historical_projection_outbox (
    tenant_id uuid NOT NULL,
    observation_identity_scope text NOT NULL,
    observation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, observation_identity_scope, observation_id),
    FOREIGN KEY (tenant_id, observation_identity_scope, observation_id)
        REFERENCES tel_evidence.observation (
            tenant_id,
            observation_identity_scope,
            observation_id
        )
);

CREATE TABLE tel_evidence.metric_current_state (
    tenant_id uuid NOT NULL,
    metric_definition_id uuid NOT NULL,
    observation_identity_scope text NOT NULL,
    observation_id uuid NOT NULL,
    source_instance_generation uuid NOT NULL,
    poll_epoch bigint NOT NULL CHECK (poll_epoch >= 0),
    poll_generation bigint NOT NULL CHECK (poll_generation >= 0),
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, metric_definition_id),
    FOREIGN KEY (tenant_id, observation_identity_scope, observation_id)
        REFERENCES tel_evidence.observation (
            tenant_id,
            observation_identity_scope,
            observation_id
        )
);

CREATE TABLE tel_evidence.current_transition (
    transition_identity text PRIMARY KEY,
    tenant_id uuid NOT NULL,
    metric_definition_id uuid NOT NULL,
    observation_identity_scope text NOT NULL,
    observation_id uuid NOT NULL,
    source_instance_generation uuid NOT NULL,
    poll_epoch bigint NOT NULL,
    poll_generation bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE tel_evidence.current_changed_outbox (
    transition_identity text PRIMARY KEY
        REFERENCES tel_evidence.current_transition (transition_identity),
    tenant_id uuid NOT NULL,
    metric_definition_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE OR REPLACE FUNCTION tel_evidence.accept_observation(
    p_tenant_id uuid,
    p_observation_identity_scope text,
    p_observation_id uuid,
    p_metric_definition_id uuid,
    p_source_instance_generation uuid,
    p_active_source_instance_generation uuid,
    p_poll_epoch bigint,
    p_poll_generation bigint,
    p_observed_at timestamptz,
    p_numeric_value numeric,
    p_current_candidate boolean,
    p_failpoint text DEFAULT NULL
)
RETURNS TABLE (
    newly_accepted boolean,
    ordering_advanced boolean,
    semantic_transition boolean
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, tel_evidence
AS $$
DECLARE
    v_rows integer := 0;
    v_current tel_evidence.metric_current_state%ROWTYPE;
    v_transition_identity text;
BEGIN
    IF p_poll_epoch < 0 OR p_poll_generation < 0 THEN
        RAISE EXCEPTION 'negative owner ordering token';
    END IF;

    INSERT INTO tel_evidence.observation (
        tenant_id,
        observation_identity_scope,
        observation_id,
        metric_definition_id,
        source_instance_generation,
        observed_at,
        numeric_value
    )
    VALUES (
        p_tenant_id,
        p_observation_identity_scope,
        p_observation_id,
        p_metric_definition_id,
        p_source_instance_generation,
        p_observed_at,
        p_numeric_value
    )
    ON CONFLICT (tenant_id, observation_identity_scope, observation_id) DO NOTHING;

    GET DIAGNOSTICS v_rows = ROW_COUNT;
    newly_accepted := (v_rows = 1);
    ordering_advanced := false;
    semantic_transition := false;

    IF p_failpoint = 'after_observation' THEN
        RAISE EXCEPTION 'injected:after_observation';
    END IF;

    IF newly_accepted THEN
        INSERT INTO tel_evidence.historical_projection_outbox (
            tenant_id,
            observation_identity_scope,
            observation_id
        )
        VALUES (
            p_tenant_id,
            p_observation_identity_scope,
            p_observation_id
        );
    END IF;

    IF p_failpoint = 'after_history_intent' THEN
        RAISE EXCEPTION 'injected:after_history_intent';
    END IF;

    IF p_current_candidate
       AND p_source_instance_generation = p_active_source_instance_generation THEN
        LOOP
            SELECT *
              INTO v_current
              FROM tel_evidence.metric_current_state
             WHERE tenant_id = p_tenant_id
               AND metric_definition_id = p_metric_definition_id
             FOR UPDATE;

            IF NOT FOUND THEN
                INSERT INTO tel_evidence.metric_current_state (
                    tenant_id,
                    metric_definition_id,
                    observation_identity_scope,
                    observation_id,
                    source_instance_generation,
                    poll_epoch,
                    poll_generation
                )
                VALUES (
                    p_tenant_id,
                    p_metric_definition_id,
                    p_observation_identity_scope,
                    p_observation_id,
                    p_source_instance_generation,
                    p_poll_epoch,
                    p_poll_generation
                )
                ON CONFLICT (tenant_id, metric_definition_id) DO NOTHING;

                GET DIAGNOSTICS v_rows = ROW_COUNT;
                IF v_rows = 0 THEN
                    CONTINUE;
                END IF;

                ordering_advanced := true;
                semantic_transition := true;
                EXIT;
            END IF;

            IF v_current.source_instance_generation <> p_active_source_instance_generation THEN
                UPDATE tel_evidence.metric_current_state
                   SET observation_identity_scope = p_observation_identity_scope,
                       observation_id = p_observation_id,
                       source_instance_generation = p_source_instance_generation,
                       poll_epoch = p_poll_epoch,
                       poll_generation = p_poll_generation,
                       changed_at = clock_timestamp()
                 WHERE tenant_id = p_tenant_id
                   AND metric_definition_id = p_metric_definition_id;
                ordering_advanced := true;
                semantic_transition := true;
                EXIT;
            END IF;

            IF (p_poll_epoch, p_poll_generation)
               > (v_current.poll_epoch, v_current.poll_generation) THEN
                IF v_current.observation_identity_scope = p_observation_identity_scope
                   AND v_current.observation_id = p_observation_id THEN
                    UPDATE tel_evidence.metric_current_state
                       SET poll_epoch = p_poll_epoch,
                           poll_generation = p_poll_generation
                     WHERE tenant_id = p_tenant_id
                       AND metric_definition_id = p_metric_definition_id;
                    ordering_advanced := true;
                    semantic_transition := false;
                ELSE
                    UPDATE tel_evidence.metric_current_state
                       SET observation_identity_scope = p_observation_identity_scope,
                           observation_id = p_observation_id,
                           source_instance_generation = p_source_instance_generation,
                           poll_epoch = p_poll_epoch,
                           poll_generation = p_poll_generation,
                           changed_at = clock_timestamp()
                     WHERE tenant_id = p_tenant_id
                       AND metric_definition_id = p_metric_definition_id;
                    ordering_advanced := true;
                    semantic_transition := true;
                END IF;
            END IF;

            EXIT;
        END LOOP;
    END IF;

    IF p_failpoint = 'after_current_cas' THEN
        RAISE EXCEPTION 'injected:after_current_cas';
    END IF;

    IF semantic_transition THEN
        v_transition_identity := concat_ws(
            '|',
            p_tenant_id::text,
            p_metric_definition_id::text,
            p_source_instance_generation::text,
            p_poll_epoch::text,
            p_poll_generation::text,
            p_observation_identity_scope,
            p_observation_id::text
        );

        INSERT INTO tel_evidence.current_transition (
            transition_identity,
            tenant_id,
            metric_definition_id,
            observation_identity_scope,
            observation_id,
            source_instance_generation,
            poll_epoch,
            poll_generation
        )
        VALUES (
            v_transition_identity,
            p_tenant_id,
            p_metric_definition_id,
            p_observation_identity_scope,
            p_observation_id,
            p_source_instance_generation,
            p_poll_epoch,
            p_poll_generation
        )
        ON CONFLICT (transition_identity) DO NOTHING;

        INSERT INTO tel_evidence.current_changed_outbox (
            transition_identity,
            tenant_id,
            metric_definition_id
        )
        VALUES (
            v_transition_identity,
            p_tenant_id,
            p_metric_definition_id
        )
        ON CONFLICT (transition_identity) DO NOTHING;
    END IF;

    IF p_failpoint = 'after_transition_signal' THEN
        RAISE EXCEPTION 'injected:after_transition_signal';
    END IF;

    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION tel_evidence.accept_observation(
    uuid, text, uuid, uuid, uuid, uuid, bigint, bigint,
    timestamptz, numeric, boolean, text
) IS
'OPEN-REL-030 evidence-only transactional oracle. Not a production Monitoring implementation.';
