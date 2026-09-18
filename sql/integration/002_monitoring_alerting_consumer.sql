-- G6 Monitoring -> Alerting durable consumer/resync bridge.
-- Authority: g6.monitoring-alerting-transport@1.
-- This migration composes the accepted Wave 2 inbox with canonical Monitoring
-- owner-state rereads. It creates no Alert business state and no async substrate.

BEGIN;

DO $$
DECLARE
    v_executor_oid OID;
    v_invoker_oid OID;
BEGIN
    IF to_regclass('system.async_consumer_inbox') IS NULL THEN
        RAISE EXCEPTION 'g6.wave2_consumer_inbox_required';
    END IF;
    IF to_regclass('monitoring.monitoring_source') IS NULL
       OR to_regclass('monitoring.monitoring_problem') IS NULL
       OR to_regclass('monitoring.health_projection') IS NULL THEN
        RAISE EXCEPTION 'g6.monitoring_owner_state_required';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g6_alerting_transport_executor') THEN
        CREATE ROLE jlmirror_g6_alerting_transport_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g6_alerting_transport_invoker') THEN
        CREATE ROLE jlmirror_g6_alerting_transport_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;

    SELECT oid INTO v_executor_oid FROM pg_roles WHERE rolname='jlmirror_g6_alerting_transport_executor';
    SELECT oid INTO v_invoker_oid FROM pg_roles WHERE rolname='jlmirror_g6_alerting_transport_invoker';

    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE oid IN (v_executor_oid,v_invoker_oid)
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'g6.transport_role_unsafe_attributes';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE roleid IN (v_executor_oid,v_invoker_oid)
           OR member IN (v_executor_oid,v_invoker_oid)
    ) THEN
        RAISE EXCEPTION 'g6.transport_role_unsafe_membership';
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA system, monitoring TO jlmirror_g6_alerting_transport_executor;
GRANT USAGE ON SCHEMA system TO jlmirror_g6_alerting_transport_invoker;
REVOKE CREATE ON SCHEMA system, monitoring FROM
    jlmirror_g6_alerting_transport_executor,
    jlmirror_g6_alerting_transport_invoker;

GRANT SELECT, INSERT, UPDATE ON system.async_consumer_inbox
TO jlmirror_g6_alerting_transport_executor;

GRANT SELECT ON monitoring.monitoring_source,
    monitoring.monitoring_problem,
    monitoring.health_projection
TO jlmirror_g6_alerting_transport_executor;

CREATE FUNCTION system.g6_admit_monitoring_alerting_message(
    p_producer_message_scope TEXT,
    p_message_id TEXT,
    p_message_class TEXT,
    p_contract_name TEXT,
    p_contract_version TEXT,
    p_producer TEXT,
    p_producer_generation TEXT,
    p_scope_class TEXT,
    p_tenant_id TEXT,
    p_subject_type TEXT,
    p_subject_id TEXT,
    p_occurred_at TIMESTAMPTZ,
    p_created_at TIMESTAMPTZ,
    p_operation_id TEXT,
    p_not_before TIMESTAMPTZ,
    p_deadline TIMESTAMPTZ,
    p_correlation_id TEXT,
    p_causation_id TEXT,
    p_data_classification TEXT,
    p_serialization_profile_id TEXT,
    p_encoded_payload BYTEA
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,system
AS $$
DECLARE
    v_payload JSONB;
    v_keys TEXT[];
    v_transition_id TEXT;
    v_expected_scope TEXT;
    v_expected_message_id TEXT;
    v_expected_correlation_id TEXT;
    v_expected_causation_id TEXT;
    v_comparison_evidence BYTEA;
    v_inserted INTEGER;
    v_receipt system.async_consumer_inbox%ROWTYPE;
BEGIN
    IF p_message_class IS DISTINCT FROM 'integration_event'
       OR p_contract_name NOT IN (
            'monitoring.problem-state.changed',
            'monitoring.health-projection.changed'
       )
       OR p_contract_version IS DISTINCT FROM '1'
       OR p_producer IS DISTINCT FROM 'Monitoring'
       OR p_producer_generation IS NOT NULL
       OR p_scope_class IS DISTINCT FROM 'tenant'
       OR p_tenant_id IS NULL OR p_tenant_id='' OR length(p_tenant_id)>512
       OR p_subject_id IS NULL OR p_subject_id='' OR length(p_subject_id)>1024
       OR p_occurred_at IS NULL
       OR p_created_at IS NOT NULL
       OR p_operation_id IS NOT NULL
       OR p_not_before IS NOT NULL
       OR p_deadline IS NOT NULL
       OR p_correlation_id IS NULL OR p_correlation_id=''
       OR p_data_classification IS DISTINCT FROM 'confidential_tenant'
       OR p_serialization_profile_id IS DISTINCT FROM 'jsonb-text-utf8@1'
       OR p_encoded_payload IS NULL
       OR octet_length(p_encoded_payload)>16384 THEN
        RAISE EXCEPTION 'g6.transport_envelope_invalid';
    END IF;

    BEGIN
        v_payload := convert_from(p_encoded_payload,'UTF8')::jsonb;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'g6.transport_payload_invalid';
    END;
    IF jsonb_typeof(v_payload)<>'object' THEN
        RAISE EXCEPTION 'g6.transport_payload_invalid';
    END IF;

    SELECT array_agg(k ORDER BY k)
      INTO v_keys
      FROM jsonb_object_keys(v_payload) AS keys(k);

    IF p_contract_name='monitoring.problem-state.changed' THEN
        IF p_subject_type IS DISTINCT FROM 'monitoring_problem'
           OR v_keys IS DISTINCT FROM ARRAY[
                'monitoring_resource_id','monitoring_source_id','problem_id',
                'problem_transition_id','projection_revision','source_instance_generation'
           ]::TEXT[]
           OR v_payload->>'problem_id' IS DISTINCT FROM p_subject_id THEN
            RAISE EXCEPTION 'g6.problem_contract_shape_invalid';
        END IF;
        v_transition_id := v_payload->>'problem_transition_id';
    ELSE
        IF p_subject_type IS DISTINCT FROM 'monitoring_resource'
           OR v_keys IS DISTINCT FROM ARRAY[
                'health_transition_id','monitoring_resource_id','monitoring_source_id',
                'projection_revision','source_instance_generation'
           ]::TEXT[]
           OR v_payload->>'monitoring_resource_id' IS DISTINCT FROM p_subject_id THEN
            RAISE EXCEPTION 'g6.health_contract_shape_invalid';
        END IF;
        v_transition_id := v_payload->>'health_transition_id';
    END IF;

    IF v_transition_id IS NULL OR v_transition_id='' OR length(v_transition_id)>1024
       OR v_payload->>'monitoring_source_id' IS NULL
       OR v_payload->>'monitoring_source_id'=''
       OR length(v_payload->>'monitoring_source_id')>512
       OR v_payload->>'source_instance_generation' IS NULL
       OR v_payload->>'source_instance_generation'=''
       OR length(v_payload->>'source_instance_generation')>512
       OR v_payload->>'monitoring_resource_id' IS NULL
       OR v_payload->>'monitoring_resource_id'=''
       OR length(v_payload->>'monitoring_resource_id')>512
       OR jsonb_typeof(v_payload->'projection_revision')<>'number'
       OR (v_payload->>'projection_revision')::BIGINT <= 0 THEN
        RAISE EXCEPTION 'g6.transport_payload_identity_invalid';
    END IF;

    v_expected_scope := 'monitoring:tenant:' || md5(p_tenant_id);
    v_expected_message_id := p_contract_name || '@1:' || md5(p_tenant_id || chr(31) || v_transition_id);
    v_expected_correlation_id := 'monitoring-correlation:' || md5(p_tenant_id || chr(31) || v_transition_id);
    v_expected_causation_id := 'monitoring-transition:' || md5(
        p_contract_name || chr(31) || p_tenant_id || chr(31) || v_transition_id
    );

    IF p_producer_message_scope IS DISTINCT FROM v_expected_scope
       OR p_message_id IS DISTINCT FROM v_expected_message_id
       OR p_correlation_id IS DISTINCT FROM v_expected_correlation_id
       OR p_causation_id IS DISTINCT FROM v_expected_causation_id THEN
        RAISE EXCEPTION 'g6.transport_envelope_identity_invalid';
    END IF;

    v_comparison_evidence := convert_to(jsonb_build_object(
        'message_class','integration_event',
        'contract_name',p_contract_name,
        'contract_version','1',
        'producer','Monitoring',
        'tenant_id',p_tenant_id,
        'subject_type',p_subject_type,
        'subject_id',p_subject_id,
        'message_id',p_message_id,
        'occurred_at_epoch',extract(epoch FROM p_occurred_at),
        'correlation_id',p_correlation_id,
        'causation_id',p_causation_id,
        'data_classification','confidential_tenant',
        'payload',v_payload
    )::TEXT,'UTF8');

    INSERT INTO system.async_consumer_inbox(
        consumer_contract,message_identity_scope,message_id,tenant_id,
        comparison_profile_id,comparison_profile_version,comparison_evidence_form,
        comparison_verifier_generation,comparison_evidence
    ) VALUES (
        'alerting.monitoring-resync@1',p_producer_message_scope,p_message_id,p_tenant_id,
        'monitoring-invalidation-equivalence','1','canonical-jsonb-envelope-payload',
        NULL,v_comparison_evidence
    )
    ON CONFLICT (consumer_contract,message_identity_scope,message_id) DO NOTHING;

    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    SELECT *
      INTO v_receipt
      FROM system.async_consumer_inbox
     WHERE consumer_contract='alerting.monitoring-resync@1'
       AND message_identity_scope=p_producer_message_scope
       AND message_id=p_message_id
     FOR SHARE;

    IF NOT FOUND
       OR v_receipt.tenant_id IS DISTINCT FROM p_tenant_id
       OR v_receipt.comparison_profile_id IS DISTINCT FROM 'monitoring-invalidation-equivalence'
       OR v_receipt.comparison_profile_version IS DISTINCT FROM '1'
       OR v_receipt.comparison_evidence_form IS DISTINCT FROM 'canonical-jsonb-envelope-payload'
       OR v_receipt.comparison_verifier_generation IS NOT NULL
       OR v_receipt.comparison_evidence IS DISTINCT FROM v_comparison_evidence THEN
        RAISE EXCEPTION 'g6.transport_duplicate_equivalence_conflict';
    END IF;

    RETURN jsonb_build_object(
        'consumer_contract',v_receipt.consumer_contract,
        'message_identity_scope',v_receipt.message_identity_scope,
        'message_id',v_receipt.message_id,
        'tenant_id',v_receipt.tenant_id,
        'receipt_state',v_receipt.state,
        'duplicate',(v_inserted=0)
    );
END;
$$;

CREATE FUNCTION system.g6_claim_monitoring_alerting_receipt(
    p_message_identity_scope TEXT,
    p_message_id TEXT,
    p_executor_id TEXT,
    p_claim_seconds INTEGER,
    p_execution_admission_revision TEXT,
    p_execution_authorization_revision TEXT,
    p_execution_principal_id TEXT,
    p_execution_principal_credential_generation TEXT,
    p_execution_runtime_generation TEXT,
    p_execution_environment_class TEXT,
    p_execution_placement_version TEXT,
    p_execution_fence_scope_id TEXT,
    p_execution_fence_epoch BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,system
AS $$
DECLARE
    v_receipt system.async_consumer_inbox%ROWTYPE;
BEGIN
    IF p_message_identity_scope IS NULL OR p_message_identity_scope=''
       OR p_message_id IS NULL OR p_message_id=''
       OR p_executor_id IS NULL OR p_executor_id='' OR length(p_executor_id)>512
       OR p_claim_seconds<1 OR p_claim_seconds>300
       OR p_execution_admission_revision IS NULL OR p_execution_admission_revision=''
       OR p_execution_authorization_revision IS NULL OR p_execution_authorization_revision=''
       OR p_execution_principal_id IS NULL OR p_execution_principal_id=''
       OR p_execution_principal_credential_generation IS NULL OR p_execution_principal_credential_generation=''
       OR p_execution_runtime_generation IS NULL OR p_execution_runtime_generation=''
       OR p_execution_environment_class IS NULL OR p_execution_environment_class=''
       OR p_execution_placement_version IS NULL OR p_execution_placement_version=''
       OR p_execution_fence_scope_id IS NULL OR p_execution_fence_scope_id=''
       OR p_execution_fence_epoch IS NULL OR p_execution_fence_epoch<=0 THEN
        RAISE EXCEPTION 'g6.transport_claim_evidence_invalid';
    END IF;

    SELECT *
      INTO v_receipt
      FROM system.async_consumer_inbox
     WHERE consumer_contract='alerting.monitoring-resync@1'
       AND message_identity_scope=p_message_identity_scope
       AND message_id=p_message_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'g6.transport_receipt_missing';
    END IF;

    IF v_receipt.state='processing' AND v_receipt.claim_expires_at<=transaction_timestamp() THEN
        UPDATE system.async_consumer_inbox
           SET state='reconciliation_required',
               executor_id=NULL,
               claim_expires_at=NULL,
               terminal_reason='processing_lease_expired_effect_absence_unproven',
               updated_at=transaction_timestamp()
         WHERE consumer_contract=v_receipt.consumer_contract
           AND message_identity_scope=v_receipt.message_identity_scope
           AND message_id=v_receipt.message_id;

        RETURN jsonb_build_object(
            'receipt_state','reconciliation_required',
            'execution_generation',v_receipt.execution_generation
        );
    END IF;

    IF v_receipt.state<>'admitted' THEN
        RETURN jsonb_build_object(
            'receipt_state',v_receipt.state,
            'execution_generation',v_receipt.execution_generation
        );
    END IF;

    UPDATE system.async_consumer_inbox
       SET state='processing',
           executor_id=p_executor_id,
           execution_generation=execution_generation+1,
           claim_expires_at=transaction_timestamp()+make_interval(secs=>p_claim_seconds),
           execution_admission_revision=p_execution_admission_revision,
           execution_authorization_revision=p_execution_authorization_revision,
           execution_principal_id=p_execution_principal_id,
           execution_principal_credential_generation=p_execution_principal_credential_generation,
           execution_runtime_profile_id='runtime.worker@1',
           execution_runtime_generation=p_execution_runtime_generation,
           execution_environment_class=p_execution_environment_class,
           execution_placement_version=p_execution_placement_version,
           execution_fence_scope_id=p_execution_fence_scope_id,
           execution_fence_epoch=p_execution_fence_epoch,
           terminal_reason=NULL,
           reconciliation_revision=NULL,
           updated_at=transaction_timestamp()
     WHERE consumer_contract=v_receipt.consumer_contract
       AND message_identity_scope=v_receipt.message_identity_scope
       AND message_id=v_receipt.message_id
     RETURNING * INTO v_receipt;

    RETURN jsonb_build_object(
        'receipt_state',v_receipt.state,
        'execution_generation',v_receipt.execution_generation,
        'claim_expires_at',v_receipt.claim_expires_at
    );
END;
$$;

CREATE FUNCTION system.g6_complete_monitoring_alerting_resync(
    p_message_identity_scope TEXT,
    p_message_id TEXT,
    p_executor_id TEXT,
    p_execution_generation BIGINT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,system,monitoring
AS $$
DECLARE
    v_receipt system.async_consumer_inbox%ROWTYPE;
    v_envelope JSONB;
    v_payload JSONB;
    v_contract TEXT;
    v_tenant_id TEXT;
    v_source_id TEXT;
    v_event_generation TEXT;
    v_active_generation TEXT;
    v_source_evidence TEXT;
    v_subject_id TEXT;
    v_event_revision BIGINT;
    v_current_revision BIGINT;
    v_current_evidence TEXT;
    v_result_id TEXT;
    v_result_kind TEXT;
BEGIN
    SELECT *
      INTO v_receipt
      FROM system.async_consumer_inbox
     WHERE consumer_contract='alerting.monitoring-resync@1'
       AND message_identity_scope=p_message_identity_scope
       AND message_id=p_message_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'g6.transport_receipt_missing';
    END IF;

    IF v_receipt.state='completed' THEN
        RETURN jsonb_build_object(
            'receipt_state','completed',
            'effect_result_id',v_receipt.effect_result_id,
            'effect_result_kind',v_receipt.effect_result_kind
        );
    END IF;

    IF v_receipt.state<>'processing'
       OR v_receipt.executor_id IS DISTINCT FROM p_executor_id
       OR v_receipt.execution_generation IS DISTINCT FROM p_execution_generation THEN
        RAISE EXCEPTION 'g6.transport_claim_not_current';
    END IF;

    IF v_receipt.claim_expires_at IS NULL OR v_receipt.claim_expires_at<=transaction_timestamp() THEN
        UPDATE system.async_consumer_inbox
           SET state='reconciliation_required',
               executor_id=NULL,
               claim_expires_at=NULL,
               terminal_reason='processing_lease_expired_effect_absence_unproven',
               updated_at=transaction_timestamp()
         WHERE consumer_contract=v_receipt.consumer_contract
           AND message_identity_scope=v_receipt.message_identity_scope
           AND message_id=v_receipt.message_id;
        RETURN jsonb_build_object('receipt_state','reconciliation_required');
    END IF;

    IF v_receipt.comparison_profile_id<>'monitoring-invalidation-equivalence'
       OR v_receipt.comparison_profile_version<>'1'
       OR v_receipt.comparison_evidence_form<>'canonical-jsonb-envelope-payload'
       OR v_receipt.comparison_verifier_generation IS NOT NULL THEN
        RAISE EXCEPTION 'g6.transport_receipt_equivalence_profile_invalid';
    END IF;

    BEGIN
        v_envelope := convert_from(v_receipt.comparison_evidence,'UTF8')::jsonb;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'g6.transport_receipt_equivalence_invalid';
    END;

    v_contract := v_envelope->>'contract_name';
    v_tenant_id := v_envelope->>'tenant_id';
    v_subject_id := v_envelope->>'subject_id';
    v_payload := v_envelope->'payload';

    IF v_contract NOT IN ('monitoring.problem-state.changed','monitoring.health-projection.changed')
       OR v_tenant_id IS NULL
       OR v_tenant_id IS DISTINCT FROM v_receipt.tenant_id
       OR jsonb_typeof(v_payload)<>'object' THEN
        RAISE EXCEPTION 'g6.transport_receipt_contract_invalid';
    END IF;

    v_source_id := v_payload->>'monitoring_source_id';
    v_event_generation := v_payload->>'source_instance_generation';
    v_event_revision := (v_payload->>'projection_revision')::BIGINT;

    PERFORM set_config('jlmirror.tenant_id',v_tenant_id,true);

    SELECT active_source_instance_generation,operational_evidence_state
      INTO v_active_generation,v_source_evidence
      FROM monitoring.monitoring_source
     WHERE tenant_id=v_tenant_id
       AND monitoring_source_id=v_source_id;

    IF NOT FOUND OR v_active_generation IS NULL OR v_source_evidence IS DISTINCT FROM 'current' THEN
        UPDATE system.async_consumer_inbox
           SET state='reconciliation_required',
               executor_id=NULL,
               claim_expires_at=NULL,
               terminal_reason='current_monitoring_source_authority_unavailable',
               updated_at=transaction_timestamp()
         WHERE consumer_contract=v_receipt.consumer_contract
           AND message_identity_scope=v_receipt.message_identity_scope
           AND message_id=v_receipt.message_id;
        RETURN jsonb_build_object('receipt_state','reconciliation_required');
    END IF;

    IF v_event_generation IS DISTINCT FROM v_active_generation THEN
        v_result_kind := 'monitoring_owner_reread_noncurrent_generation';
        v_result_id := 'g6-resync:' || md5(
            v_tenant_id || chr(31) || v_contract || chr(31) || v_subject_id
            || chr(31) || v_event_generation || chr(31) || v_active_generation
        );
    ELSE
        IF v_contract='monitoring.problem-state.changed' THEN
            SELECT projection_revision,evidence_state
              INTO v_current_revision,v_current_evidence
              FROM monitoring.monitoring_problem
             WHERE tenant_id=v_tenant_id
               AND problem_id=v_subject_id
               AND monitoring_source_id=v_source_id
               AND source_instance_generation=v_active_generation;
        ELSE
            SELECT projection_revision,evidence_state
              INTO v_current_revision,v_current_evidence
              FROM monitoring.health_projection
             WHERE tenant_id=v_tenant_id
               AND monitoring_resource_id=v_subject_id
               AND monitoring_source_id=v_source_id
               AND source_instance_generation=v_active_generation;
        END IF;

        IF NOT FOUND
           OR v_current_revision<v_event_revision
           OR v_current_evidence IS DISTINCT FROM 'current' THEN
            UPDATE system.async_consumer_inbox
               SET state='reconciliation_required',
                   executor_id=NULL,
                   claim_expires_at=NULL,
                   terminal_reason='current_monitoring_owner_state_unavailable',
                   updated_at=transaction_timestamp()
             WHERE consumer_contract=v_receipt.consumer_contract
               AND message_identity_scope=v_receipt.message_identity_scope
               AND message_id=v_receipt.message_id;
            RETURN jsonb_build_object('receipt_state','reconciliation_required');
        END IF;

        v_result_kind := CASE
            WHEN v_contract='monitoring.problem-state.changed'
                THEN 'monitoring_problem_owner_reread_current'
            ELSE 'monitoring_health_owner_reread_current'
        END;
        v_result_id := 'g6-resync:' || md5(
            v_tenant_id || chr(31) || v_contract || chr(31) || v_subject_id
            || chr(31) || v_active_generation || chr(31) || v_current_revision::TEXT
        );
    END IF;

    UPDATE system.async_consumer_inbox
       SET state='completed',
           executor_id=NULL,
           claim_expires_at=NULL,
           effect_result_id=v_result_id,
           effect_result_kind=v_result_kind,
           terminal_reason=NULL,
           updated_at=transaction_timestamp()
     WHERE consumer_contract=v_receipt.consumer_contract
       AND message_identity_scope=v_receipt.message_identity_scope
       AND message_id=v_receipt.message_id;

    RETURN jsonb_build_object(
        'receipt_state','completed',
        'effect_result_id',v_result_id,
        'effect_result_kind',v_result_kind
    );
END;
$$;

ALTER FUNCTION system.g6_admit_monitoring_alerting_message(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,
    TIMESTAMPTZ,TIMESTAMPTZ,TEXT,TIMESTAMPTZ,TIMESTAMPTZ,
    TEXT,TEXT,TEXT,TEXT,BYTEA
) OWNER TO jlmirror_g6_alerting_transport_executor;

ALTER FUNCTION system.g6_claim_monitoring_alerting_receipt(
    TEXT,TEXT,TEXT,INTEGER,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BIGINT
) OWNER TO jlmirror_g6_alerting_transport_executor;

ALTER FUNCTION system.g6_complete_monitoring_alerting_resync(
    TEXT,TEXT,TEXT,BIGINT
) OWNER TO jlmirror_g6_alerting_transport_executor;

REVOKE ALL ON FUNCTION system.g6_admit_monitoring_alerting_message(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,
    TIMESTAMPTZ,TIMESTAMPTZ,TEXT,TIMESTAMPTZ,TIMESTAMPTZ,
    TEXT,TEXT,TEXT,TEXT,BYTEA
) FROM PUBLIC;
REVOKE ALL ON FUNCTION system.g6_claim_monitoring_alerting_receipt(
    TEXT,TEXT,TEXT,INTEGER,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BIGINT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION system.g6_complete_monitoring_alerting_resync(
    TEXT,TEXT,TEXT,BIGINT
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION system.g6_admit_monitoring_alerting_message(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,
    TIMESTAMPTZ,TIMESTAMPTZ,TEXT,TIMESTAMPTZ,TIMESTAMPTZ,
    TEXT,TEXT,TEXT,TEXT,BYTEA
) TO jlmirror_g6_alerting_transport_invoker;
GRANT EXECUTE ON FUNCTION system.g6_claim_monitoring_alerting_receipt(
    TEXT,TEXT,TEXT,INTEGER,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BIGINT
) TO jlmirror_g6_alerting_transport_invoker;
GRANT EXECUTE ON FUNCTION system.g6_complete_monitoring_alerting_resync(
    TEXT,TEXT,TEXT,BIGINT
) TO jlmirror_g6_alerting_transport_invoker;

COMMIT;
