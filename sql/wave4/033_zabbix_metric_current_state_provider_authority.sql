-- Bind Metric Current State claim to the active provider-generation and source-owned credential authority.

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
        SELECT 1
          FROM monitoring.monitoring_metric_current_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_source_id
           AND a.current_state_poll_epoch=v_poll_epoch
    ) THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_recovery_admission_required';
    END IF;

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

COMMIT;
