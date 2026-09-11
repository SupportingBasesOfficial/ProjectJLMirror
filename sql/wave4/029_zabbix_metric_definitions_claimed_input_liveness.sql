-- Wave 4 metric-definition claimed-input liveness hardening.
-- A legitimately claimed operation must never remain running merely because the
-- completion payload is NULL, not an array, above the bounded cardinality, the
-- caller supplied an incoherent completion shape, or the caller omitted its snapshot
-- evidence id. Resolve authority first, persist a degraded snapshot, and retire the
-- claim. The v028 implementation remains an executor-only helper for structurally
-- valid completion requests.

BEGIN;

ALTER FUNCTION monitoring.complete_zabbix_metric_definitions(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB
) RENAME TO complete_zabbix_metric_definitions_v028;

REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions_v028(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB
) FROM PUBLIC,jlmirror_wave4_metric_definition_invoker;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions_v028(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB
) TO jlmirror_wave4_metric_definition_executor;

CREATE FUNCTION monitoring.complete_zabbix_metric_definitions(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_metric_definition_snapshot_evidence_id TEXT,
    p_operational_evidence_state TEXT,
    p_operation_state TEXT,
    p_failure_class TEXT,
    p_egress_decision_ref TEXT,
    p_credential_generation_ref TEXT,
    p_snapshot_complete BOOLEAN,
    p_items JSONB
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_epoch BIGINT;
    v_poll_generation BIGINT;
    v_item_count BIGINT := 0;
    v_input_failure TEXT := NULL;
    v_snapshot_id TEXT;
BEGIN
    SELECT o.monitoring_source_id,
           o.source_instance_generation,
           o.configuration_revision,
           o.scope_revision,
           o.item_definition_poll_epoch,
           o.item_definition_poll_generation
      INTO v_source_id,
           v_generation,
           v_configuration_revision,
           v_scope_revision,
           v_poll_epoch,
           v_poll_generation
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_definition_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_completion_not_claimed';
    END IF;

    -- Once claim authority is proven, every remaining invocation/input fault is a
    -- durable operation outcome. Never rely on SQL boolean-expression evaluation
    -- order around jsonb_array_length.
    IF p_items IS NULL OR jsonb_typeof(p_items) IS DISTINCT FROM 'array' THEN
        v_input_failure := 'provider.protocol_invalid';
    ELSE
        v_item_count := jsonb_array_length(p_items);
        IF v_item_count > 200000 THEN
            v_input_failure := 'provider.protocol_invalid';
        END IF;
    END IF;

    IF v_input_failure IS NULL AND (
        (p_operation_state='succeeded') IS DISTINCT FROM p_snapshot_complete
        OR (p_operation_state='succeeded') IS DISTINCT FROM (p_operational_evidence_state='current')
        OR (p_operation_state='succeeded') IS DISTINCT FROM (p_failure_class IS NULL)
    ) THEN
        v_input_failure := 'execution.invalid_completion_shape';
    END IF;

    IF p_metric_definition_snapshot_evidence_id IS NULL
       OR p_metric_definition_snapshot_evidence_id='' THEN
        v_input_failure := COALESCE(v_input_failure,'execution.invalid_completion_shape');
        v_snapshot_id := 'metric-reconciliation-' || encode(sha256(convert_to(
            p_tenant_id || ':' || p_monitoring_sync_operation_id || ':' || COALESCE(p_claim_token,''),
            'UTF8'
        )),'hex');
    ELSE
        v_snapshot_id := p_metric_definition_snapshot_evidence_id;
    END IF;

    IF v_input_failure IS NOT NULL THEN
        INSERT INTO monitoring.monitoring_metric_definition_snapshot_evidence(
            tenant_id,metric_definition_snapshot_evidence_id,monitoring_sync_operation_id,
            monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,
            item_definition_poll_epoch,item_definition_poll_generation,snapshot_complete,item_count,
            operational_evidence_state,operation_state,failure_class,egress_decision_ref,credential_generation_ref
        ) VALUES (
            p_tenant_id,v_snapshot_id,p_monitoring_sync_operation_id,
            v_source_id,v_generation,v_configuration_revision,v_scope_revision,v_poll_epoch,v_poll_generation,
            FALSE,v_item_count,'reconciliation_required','reconciliation_required',v_input_failure,
            p_egress_decision_ref,p_credential_generation_ref
        );

        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',
               completed_at=transaction_timestamp(),
               last_error_class=v_input_failure,
               metric_definition_snapshot_evidence_id=v_snapshot_id,
               claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

        RETURN 'reconciliation_required';
    END IF;

    RETURN monitoring.complete_zabbix_metric_definitions_v028(
        p_tenant_id,
        p_monitoring_sync_operation_id,
        p_claim_token,
        v_snapshot_id,
        p_operational_evidence_state,
        p_operation_state,
        p_failure_class,
        p_egress_decision_ref,
        p_credential_generation_ref,
        p_snapshot_complete,
        p_items
    );
END;
$$;

ALTER FUNCTION monitoring.complete_zabbix_metric_definitions(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB
) OWNER TO jlmirror_wave4_metric_definition_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB
) TO jlmirror_wave4_metric_definition_invoker;

COMMIT;
