-- Wave 4 host-inventory claim qualification hardening.
-- PL/pgSQL RETURNS TABLE output names are variables; qualify table columns explicitly.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.claim_zabbix_host_inventory(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    provider_scope_tenant_binding_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    provider_instance_ref TEXT,
    provider_base_url TEXT,
    credential_binding_ref TEXT,
    configured_provider_scope JSONB
)
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
BEGIN
    IF p_claim_token IS NULL
       OR p_claim_token = ''
       OR length(p_claim_token) > 512
       OR p_claim_token <> btrim(p_claim_token)
       OR p_claim_token ~ '[[:cntrl:]]' THEN
        RAISE EXCEPTION 'invalid host inventory claim token';
    END IF;

    SELECT o.monitoring_source_id,
           o.source_instance_generation,
           o.configuration_revision,
           o.scope_revision
      INTO v_source_id,
           v_generation,
           v_configuration_revision,
           v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id
       AND o.responsibility_kind = 'host_inventory_sync'
       AND o.state = 'pending'
       AND o.claim_token IS NULL
     FOR UPDATE OF o;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_not_claimable';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_source AS s
         WHERE s.tenant_id = p_tenant_id
           AND s.monitoring_source_id = v_source_id
           AND s.active_source_instance_generation = v_generation
           AND s.configuration_revision = v_configuration_revision
           AND s.scope_revision = v_scope_revision
           AND EXISTS (
               SELECT 1
                 FROM monitoring.monitoring_source_validation_evidence AS v
                WHERE v.tenant_id = s.tenant_id
                  AND v.monitoring_source_id = s.monitoring_source_id
                  AND v.source_instance_generation = v_generation
                  AND v.configuration_revision = v_configuration_revision
                  AND v.scope_revision = v_scope_revision
                  AND v.operation_state = 'succeeded'
                  AND v.operational_evidence_state = 'current'
           )
    ) THEN
        RAISE EXCEPTION 'monitoring.host_inventory_stale_authority';
    END IF;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state = 'running',
           claim_token = p_claim_token,
           attempt_count = o.attempt_count + 1,
           started_at = transaction_timestamp()
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id;

    UPDATE monitoring.monitoring_source AS s
       SET last_attempt_at = transaction_timestamp(),
           updated_at = transaction_timestamp()
     WHERE s.tenant_id = p_tenant_id
       AND s.monitoring_source_id = v_source_id;

    RETURN QUERY
    SELECT s.monitoring_source_id,
           s.provider_scope_tenant_binding_id,
           o.source_instance_generation,
           o.configuration_revision,
           o.scope_revision,
           g.provider_instance_ref,
           g.provider_base_url,
           s.credential_binding_ref,
           s.configured_provider_scope
      FROM monitoring.monitoring_sync_operation AS o
      JOIN monitoring.monitoring_source AS s
        ON s.tenant_id = o.tenant_id
       AND s.monitoring_source_id = o.monitoring_source_id
      JOIN monitoring.monitoring_source_generation AS g
        ON g.tenant_id = o.tenant_id
       AND g.monitoring_source_id = o.monitoring_source_id
       AND g.source_instance_generation = o.source_instance_generation
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id;
END;
$$;

COMMIT;
