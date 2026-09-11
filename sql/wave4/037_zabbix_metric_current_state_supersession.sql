-- Supersede older in-flight Current polls immediately and fence target enumeration.

BEGIN;

DROP FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT);

CREATE FUNCTION monitoring.claim_zabbix_metric_current_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    current_state_poll_epoch BIGINT,
    current_state_poll_generation BIGINT,
    provider_instance_ref TEXT,
    provider_base_url TEXT,
    credential_binding_ref TEXT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_epoch BIGINT;
    v_poll_generation BIGINT;
BEGIN
    IF p_claim_token IS NULL OR p_claim_token='' OR length(p_claim_token)>512
       OR p_claim_token<>btrim(p_claim_token) OR p_claim_token~'[[:cntrl:]]' THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_claim_token';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='pending'
       AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_not_claimable';
    END IF;

    SELECT s.current_state_poll_epoch,s.current_state_poll_generation+1
      INTO v_poll_epoch,v_poll_generation
      FROM monitoring.monitoring_source AS s
      JOIN monitoring.monitoring_source_generation AS g
        ON g.tenant_id=s.tenant_id
       AND g.monitoring_source_id=s.monitoring_source_id
       AND g.source_instance_generation=s.active_source_instance_generation
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
       AND s.active_source_instance_generation=v_generation
       AND s.configuration_revision=v_configuration_revision
       AND s.scope_revision=v_scope_revision
       AND s.operational_evidence_state='current'
       AND g.source_instance_generation=v_generation
     FOR UPDATE OF s;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_stale_authority';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_metric_current_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_source_id
           AND a.current_state_poll_epoch=v_poll_epoch
    ) THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_recovery_admission_required';
    END IF;

    -- The new generation is the single current writer. Older in-flight work is terminalized
    -- before the source fence advances so it cannot remain indefinitely running.
    UPDATE monitoring.monitoring_sync_operation AS old_o
       SET state='reconciliation_required',completed_at=transaction_timestamp(),
           last_error_class='execution.superseded_current_state_poll_authority',claim_token=NULL
     WHERE old_o.tenant_id=p_tenant_id
       AND old_o.monitoring_source_id=v_source_id
       AND old_o.responsibility_kind='metric_current_state_sync'
       AND old_o.state='running'
       AND old_o.current_state_poll_epoch=v_poll_epoch
       AND old_o.current_state_poll_generation<v_poll_generation;

    UPDATE monitoring.monitoring_source AS s
       SET current_state_poll_generation=v_poll_generation,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=v_source_id;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='running',claim_token=p_claim_token,started_at=transaction_timestamp(),
           attempt_count=o.attempt_count+1,current_state_poll_epoch=v_poll_epoch,
           current_state_poll_generation=v_poll_generation
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN QUERY
    SELECT s.monitoring_source_id,s.active_source_instance_generation,
           s.configuration_revision,s.scope_revision,
           s.current_state_poll_epoch,s.current_state_poll_generation,
           g.provider_instance_ref,g.provider_base_url,s.credential_binding_ref
      FROM monitoring.monitoring_source AS s
      JOIN monitoring.monitoring_source_generation AS g
        ON g.tenant_id=s.tenant_id
       AND g.monitoring_source_id=s.monitoring_source_id
       AND g.source_instance_generation=s.active_source_instance_generation
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=v_source_id;
END;
$$;
ALTER FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_current_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.list_zabbix_metric_current_targets(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_after_metric_definition_id TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
) RETURNS TABLE (
    metric_definition_id TEXT,
    monitoring_resource_id TEXT,
    provider_external_ref TEXT,
    value_kind TEXT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_operation monitoring.monitoring_sync_operation%ROWTYPE;
BEGIN
    IF p_limit<1 OR p_limit>5000 THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_target_page_limit';
    END IF;

    SELECT o.* INTO v_operation
      FROM monitoring.monitoring_sync_operation AS o
      JOIN monitoring.monitoring_source AS s
        ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
       AND s.active_source_instance_generation=o.source_instance_generation
       AND s.configuration_revision=o.configuration_revision
       AND s.scope_revision=o.scope_revision
       AND s.current_state_poll_epoch=o.current_state_poll_epoch
       AND s.current_state_poll_generation=o.current_state_poll_generation
       AND s.operational_evidence_state='current'
       AND EXISTS (
           SELECT 1 FROM monitoring.monitoring_metric_current_state_runtime_admission AS a
            WHERE a.tenant_id=o.tenant_id
              AND a.monitoring_source_id=o.monitoring_source_id
              AND a.current_state_poll_epoch=o.current_state_poll_epoch
       );
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_claim_not_current';
    END IF;

    RETURN QUERY
    SELECT d.metric_definition_id,d.monitoring_resource_id,b.provider_external_ref,d.value_kind
      FROM monitoring.metric_definition AS d
      JOIN monitoring.metric_definition_provider_binding AS b
        ON b.tenant_id=d.tenant_id
       AND b.metric_definition_id=d.metric_definition_id
       AND b.monitoring_source_id=d.monitoring_source_id
       AND b.source_instance_generation=d.source_instance_generation
       AND b.monitoring_resource_id=d.monitoring_resource_id
     WHERE d.tenant_id=p_tenant_id
       AND d.monitoring_source_id=v_operation.monitoring_source_id
       AND d.source_instance_generation=v_operation.source_instance_generation
       AND d.definition_state='active'
       AND d.definition_evidence_state='current'
       AND d.scope_state='in_scope'
       AND d.scope_evidence_state='current'
       AND d.scope_projection_revision=v_operation.scope_revision
       AND b.evidence_state='current'
       AND b.provider_operational_state='enabled'
       AND (p_after_metric_definition_id IS NULL OR d.metric_definition_id>p_after_metric_definition_id)
     ORDER BY d.metric_definition_id
     LIMIT p_limit;
END;
$$;
ALTER FUNCTION monitoring.list_zabbix_metric_current_targets(TEXT,TEXT,TEXT,TEXT,INTEGER)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.list_zabbix_metric_current_targets(TEXT,TEXT,TEXT,TEXT,INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.list_zabbix_metric_current_targets(TEXT,TEXT,TEXT,TEXT,INTEGER)
    TO jlmirror_wave4_metric_current_state_invoker;

COMMIT;
