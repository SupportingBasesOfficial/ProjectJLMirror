-- Wave 4 Monitoring -> Alerting publication bridge runtime.
-- Authority: wave4.monitoring-alerting-publication@1.
-- This is a composed cross-wave migration: it requires the accepted Wave 2
-- async outbox substrate plus the accepted Wave 4 Problem/Health transition tables.
-- It creates no broker, no second outbox, and no Alerting business state.

BEGIN;

DO $$
BEGIN
    IF to_regclass('system.async_outbox_message') IS NULL
       OR to_regclass('system.async_outbox_dispatch') IS NULL THEN
        RAISE EXCEPTION 'monitoring.publication_wave2_outbox_substrate_required';
    END IF;
    IF to_regclass('monitoring.monitoring_problem_transition') IS NULL
       OR to_regclass('monitoring.health_projection_transition') IS NULL THEN
        RAISE EXCEPTION 'monitoring.publication_wave4_transition_substrate_required';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_recovery_authority') THEN
        RAISE EXCEPTION 'monitoring.publication_recovery_authority_required';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_monitoring_publication_executor') THEN
        CREATE ROLE jlmirror_wave4_monitoring_publication_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring, system
TO jlmirror_wave4_monitoring_publication_executor;
REVOKE CREATE ON SCHEMA monitoring, system
FROM jlmirror_wave4_monitoring_publication_executor;

-- The publication executor is NOLOGIN and is never granted to application roles.
-- It owns the SECURITY DEFINER bridge functions and has only the exact storage
-- privileges required to materialize/recover accepted outbox obligations.
GRANT SELECT, INSERT ON system.async_outbox_message
TO jlmirror_wave4_monitoring_publication_executor;
GRANT SELECT, INSERT ON system.async_outbox_dispatch
TO jlmirror_wave4_monitoring_publication_executor;
GRANT USAGE, SELECT ON SEQUENCE system.async_outbox_message_outbox_record_id_seq
TO jlmirror_wave4_monitoring_publication_executor;
GRANT SELECT ON monitoring.monitoring_problem_transition,
    monitoring.health_projection_transition
TO jlmirror_wave4_monitoring_publication_executor;

CREATE OR REPLACE FUNCTION monitoring.wave4_ensure_monitoring_invalidation(
    p_tenant_id TEXT,
    p_contract_name TEXT,
    p_subject_type TEXT,
    p_subject_id TEXT,
    p_transition_id TEXT,
    p_occurred_at TIMESTAMPTZ,
    p_payload JSONB
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
DECLARE
    v_keys TEXT[];
    v_message_id TEXT;
    v_producer_scope TEXT;
    v_payload_bytes BYTEA;
    v_equivalence_bytes BYTEA;
    v_outbox_id BIGINT;
    v_existing system.async_outbox_message%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR length(p_tenant_id)>512
       OR p_subject_id IS NULL OR p_subject_id='' OR length(p_subject_id)>1024
       OR p_transition_id IS NULL OR p_transition_id='' OR length(p_transition_id)>1024
       OR p_occurred_at IS NULL
       OR p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' THEN
        RAISE EXCEPTION 'monitoring.publication_invalid_input';
    END IF;

    SELECT array_agg(k ORDER BY k)
      INTO v_keys
      FROM jsonb_object_keys(p_payload) AS keys(k);

    IF p_contract_name='monitoring.problem-state.changed' THEN
        IF p_subject_type<>'monitoring_problem'
           OR v_keys IS DISTINCT FROM ARRAY[
                'monitoring_resource_id','monitoring_source_id','problem_id',
                'problem_transition_id','projection_revision','source_instance_generation'
           ]::TEXT[]
           OR p_payload->>'problem_id' IS DISTINCT FROM p_subject_id
           OR p_payload->>'problem_transition_id' IS DISTINCT FROM p_transition_id THEN
            RAISE EXCEPTION 'monitoring.publication_problem_contract_shape_mismatch';
        END IF;
    ELSIF p_contract_name='monitoring.health-projection.changed' THEN
        IF p_subject_type<>'monitoring_resource'
           OR v_keys IS DISTINCT FROM ARRAY[
                'health_transition_id','monitoring_resource_id','monitoring_source_id',
                'projection_revision','source_instance_generation'
           ]::TEXT[]
           OR p_payload->>'monitoring_resource_id' IS DISTINCT FROM p_subject_id
           OR p_payload->>'health_transition_id' IS DISTINCT FROM p_transition_id THEN
            RAISE EXCEPTION 'monitoring.publication_health_contract_shape_mismatch';
        END IF;
    ELSE
        RAISE EXCEPTION 'monitoring.publication_contract_not_authorized';
    END IF;

    -- Stable compact logical identity. md5 is used only as a deterministic
    -- compaction function; any collision with non-equivalent immutable meaning
    -- is detected below and fails closed rather than being accepted as duplicate.
    v_producer_scope := 'monitoring:tenant:' || md5(p_tenant_id);
    v_message_id := p_contract_name || '@1:' || md5(p_tenant_id || chr(31) || p_transition_id);

    v_payload_bytes := convert_to(p_payload::TEXT, 'UTF8');
    IF octet_length(v_payload_bytes)>16384 THEN
        RAISE EXCEPTION 'monitoring.publication_payload_overbound';
    END IF;

    v_equivalence_bytes := convert_to(jsonb_build_object(
        'message_class','integration_event',
        'contract_name',p_contract_name,
        'contract_version','1',
        'producer','Monitoring',
        'tenant_id',p_tenant_id,
        'subject_type',p_subject_type,
        'subject_id',p_subject_id,
        'message_id',v_message_id,
        'occurred_at_epoch',extract(epoch FROM p_occurred_at),
        'correlation_id',v_message_id,
        'causation_id',NULL,
        'data_classification','confidential_tenant',
        'payload',p_payload
    )::TEXT, 'UTF8');

    INSERT INTO system.async_outbox_message(
        producer_message_scope,message_id,message_class,contract_name,contract_version,
        producer,producer_generation,scope_class,tenant_id,subject_type,subject_id,
        occurred_at,created_at,operation_id,not_before,deadline,correlation_id,causation_id,
        data_classification,serialization_profile_id,encoded_payload,
        comparison_profile_id,comparison_profile_version,comparison_evidence_form,
        comparison_verifier_generation,comparison_evidence
    ) VALUES (
        v_producer_scope,v_message_id,'integration_event',p_contract_name,'1',
        'Monitoring',NULL,'tenant',p_tenant_id,p_subject_type,p_subject_id,
        p_occurred_at,NULL,NULL,NULL,NULL,v_message_id,NULL,
        'confidential_tenant','jsonb-text-utf8@1',v_payload_bytes,
        'monitoring-invalidation-equivalence','1','canonical-jsonb-envelope-payload',
        NULL,v_equivalence_bytes
    )
    ON CONFLICT (producer_message_scope,message_id) DO NOTHING
    RETURNING outbox_record_id INTO v_outbox_id;

    IF v_outbox_id IS NULL THEN
        SELECT * INTO v_existing
          FROM system.async_outbox_message
         WHERE producer_message_scope=v_producer_scope
           AND message_id=v_message_id;

        IF NOT FOUND
           OR v_existing.message_class IS DISTINCT FROM 'integration_event'
           OR v_existing.contract_name IS DISTINCT FROM p_contract_name
           OR v_existing.contract_version IS DISTINCT FROM '1'
           OR v_existing.producer IS DISTINCT FROM 'Monitoring'
           OR v_existing.producer_generation IS NOT NULL
           OR v_existing.scope_class IS DISTINCT FROM 'tenant'
           OR v_existing.tenant_id IS DISTINCT FROM p_tenant_id
           OR v_existing.subject_type IS DISTINCT FROM p_subject_type
           OR v_existing.subject_id IS DISTINCT FROM p_subject_id
           OR v_existing.occurred_at IS DISTINCT FROM p_occurred_at
           OR v_existing.created_at IS NOT NULL
           OR v_existing.operation_id IS NOT NULL
           OR v_existing.not_before IS NOT NULL
           OR v_existing.deadline IS NOT NULL
           OR v_existing.correlation_id IS DISTINCT FROM v_message_id
           OR v_existing.causation_id IS NOT NULL
           OR v_existing.data_classification IS DISTINCT FROM 'confidential_tenant'
           OR v_existing.serialization_profile_id IS DISTINCT FROM 'jsonb-text-utf8@1'
           OR v_existing.encoded_payload IS DISTINCT FROM v_payload_bytes
           OR v_existing.comparison_profile_id IS DISTINCT FROM 'monitoring-invalidation-equivalence'
           OR v_existing.comparison_profile_version IS DISTINCT FROM '1'
           OR v_existing.comparison_evidence_form IS DISTINCT FROM 'canonical-jsonb-envelope-payload'
           OR v_existing.comparison_verifier_generation IS NOT NULL
           OR v_existing.comparison_evidence IS DISTINCT FROM v_equivalence_bytes THEN
            RAISE EXCEPTION 'monitoring.publication_identity_conflict';
        END IF;
        v_outbox_id := v_existing.outbox_record_id;
    END IF;

    -- Dispatch bookkeeping is recoverable. The Wave 2 AFTER INSERT trigger normally
    -- creates this row atomically; this insert repairs missing restored bookkeeping
    -- without changing the immutable logical message.
    INSERT INTO system.async_outbox_dispatch(outbox_record_id)
    VALUES (v_outbox_id)
    ON CONFLICT (outbox_record_id) DO NOTHING;

    RETURN v_outbox_id;
END;
$$;
ALTER FUNCTION monitoring.wave4_ensure_monitoring_invalidation(TEXT,TEXT,TEXT,TEXT,TEXT,TIMESTAMPTZ,JSONB)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.wave4_ensure_monitoring_invalidation(TEXT,TEXT,TEXT,TEXT,TEXT,TIMESTAMPTZ,JSONB)
    FROM PUBLIC;

CREATE OR REPLACE FUNCTION monitoring.wave4_publish_problem_transition()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
BEGIN
    PERFORM monitoring.wave4_ensure_monitoring_invalidation(
        NEW.tenant_id,
        'monitoring.problem-state.changed',
        'monitoring_problem',
        NEW.problem_id,
        NEW.problem_transition_id,
        NEW.occurred_at,
        jsonb_build_object(
            'problem_id',NEW.problem_id,
            'monitoring_source_id',NEW.monitoring_source_id,
            'source_instance_generation',NEW.source_instance_generation,
            'monitoring_resource_id',NEW.monitoring_resource_id,
            'projection_revision',NEW.projection_revision,
            'problem_transition_id',NEW.problem_transition_id
        )
    );
    RETURN NEW;
END;
$$;
ALTER FUNCTION monitoring.wave4_publish_problem_transition()
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.wave4_publish_problem_transition() FROM PUBLIC;

CREATE OR REPLACE FUNCTION monitoring.wave4_publish_health_transition()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
BEGIN
    PERFORM monitoring.wave4_ensure_monitoring_invalidation(
        NEW.tenant_id,
        'monitoring.health-projection.changed',
        'monitoring_resource',
        NEW.monitoring_resource_id,
        NEW.health_transition_id,
        NEW.occurred_at,
        jsonb_build_object(
            'monitoring_source_id',NEW.monitoring_source_id,
            'source_instance_generation',NEW.source_instance_generation,
            'monitoring_resource_id',NEW.monitoring_resource_id,
            'projection_revision',NEW.projection_revision,
            'health_transition_id',NEW.health_transition_id
        )
    );
    RETURN NEW;
END;
$$;
ALTER FUNCTION monitoring.wave4_publish_health_transition()
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.wave4_publish_health_transition() FROM PUBLIC;

CREATE TRIGGER monitoring_problem_transition_outbox
AFTER INSERT ON monitoring.monitoring_problem_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_problem_transition();

CREATE TRIGGER health_projection_transition_outbox
AFTER INSERT ON monitoring.health_projection_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_health_transition();

CREATE OR REPLACE FUNCTION monitoring.recover_problem_state_publication(
    p_tenant_id TEXT,
    p_problem_transition_id TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
DECLARE
    v_transition monitoring.monitoring_problem_transition%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR p_problem_transition_id IS NULL OR p_problem_transition_id='' THEN
        RAISE EXCEPTION 'monitoring.publication_invalid_recovery_input';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT * INTO v_transition
      FROM monitoring.monitoring_problem_transition
     WHERE tenant_id=p_tenant_id
       AND problem_transition_id=p_problem_transition_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.publication_problem_transition_not_found';
    END IF;
    RETURN monitoring.wave4_ensure_monitoring_invalidation(
        v_transition.tenant_id,
        'monitoring.problem-state.changed',
        'monitoring_problem',
        v_transition.problem_id,
        v_transition.problem_transition_id,
        v_transition.occurred_at,
        jsonb_build_object(
            'problem_id',v_transition.problem_id,
            'monitoring_source_id',v_transition.monitoring_source_id,
            'source_instance_generation',v_transition.source_instance_generation,
            'monitoring_resource_id',v_transition.monitoring_resource_id,
            'projection_revision',v_transition.projection_revision,
            'problem_transition_id',v_transition.problem_transition_id
        )
    );
END;
$$;
ALTER FUNCTION monitoring.recover_problem_state_publication(TEXT,TEXT)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.recover_problem_state_publication(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.recover_problem_state_publication(TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.recover_health_projection_publication(
    p_tenant_id TEXT,
    p_health_transition_id TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
DECLARE
    v_transition monitoring.health_projection_transition%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR p_health_transition_id IS NULL OR p_health_transition_id='' THEN
        RAISE EXCEPTION 'monitoring.publication_invalid_recovery_input';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT * INTO v_transition
      FROM monitoring.health_projection_transition
     WHERE tenant_id=p_tenant_id
       AND health_transition_id=p_health_transition_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.publication_health_transition_not_found';
    END IF;
    RETURN monitoring.wave4_ensure_monitoring_invalidation(
        v_transition.tenant_id,
        'monitoring.health-projection.changed',
        'monitoring_resource',
        v_transition.monitoring_resource_id,
        v_transition.health_transition_id,
        v_transition.occurred_at,
        jsonb_build_object(
            'monitoring_source_id',v_transition.monitoring_source_id,
            'source_instance_generation',v_transition.source_instance_generation,
            'monitoring_resource_id',v_transition.monitoring_resource_id,
            'projection_revision',v_transition.projection_revision,
            'health_transition_id',v_transition.health_transition_id
        )
    );
END;
$$;
ALTER FUNCTION monitoring.recover_health_projection_publication(TEXT,TEXT)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.recover_health_projection_publication(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.recover_health_projection_publication(TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

COMMIT;
