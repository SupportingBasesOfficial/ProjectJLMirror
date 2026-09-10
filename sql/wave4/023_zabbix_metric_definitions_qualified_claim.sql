-- Wave 4 metric-definition claim identifier hardening.
-- RETURNS TABLE output names are PL/pgSQL variables; every table column in the
-- claim mutation path is explicitly qualified to prevent name-resolution ambiguity.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.claim_zabbix_metric_definitions(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    provider_scope_tenant_binding_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    item_definition_poll_epoch BIGINT,
    item_definition_poll_generation BIGINT,
    provider_instance_ref TEXT,
    provider_base_url TEXT,
    credential_binding_ref TEXT,
    configured_provider_scope JSONB
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
    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_definition_sync'
       AND o.state='pending'
       AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_not_claimable';
    END IF;

    SELECT s.item_definition_poll_epoch,s.item_definition_poll_generation+1
      INTO v_poll_epoch,v_poll_generation
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
       AND s.active_source_instance_generation=v_generation
       AND s.configuration_revision=v_configuration_revision
       AND s.scope_revision=v_scope_revision
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_stale_authority';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_metric_definition_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_source_id
           AND a.item_definition_poll_epoch=v_poll_epoch
    ) THEN
        RAISE EXCEPTION 'monitoring.metric_definition_recovery_admission_required';
    END IF;

    UPDATE monitoring.monitoring_source AS s
       SET item_definition_poll_generation=v_poll_generation,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='running',
           claim_token=p_claim_token,
           started_at=transaction_timestamp(),
           attempt_count=o.attempt_count+1,
           item_definition_poll_epoch=v_poll_epoch,
           item_definition_poll_generation=v_poll_generation
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN QUERY
    SELECT s.monitoring_source_id,
           s.provider_scope_tenant_binding_id,
           s.active_source_instance_generation,
           s.configuration_revision,
           s.scope_revision,
           s.item_definition_poll_epoch,
           s.item_definition_poll_generation,
           g.provider_instance_ref,
           s.provider_base_url,
           s.credential_binding_ref,
           s.configured_provider_scope
      FROM monitoring.monitoring_source AS s
      JOIN monitoring.monitoring_source_generation AS g
        ON g.tenant_id=s.tenant_id
       AND g.monitoring_source_id=s.monitoring_source_id
       AND g.source_instance_generation=s.active_source_instance_generation
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id;
END;
$$;

ALTER FUNCTION monitoring.claim_zabbix_metric_definitions(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_definition_executor;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_definitions(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_definitions(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_definition_invoker;

COMMIT;
