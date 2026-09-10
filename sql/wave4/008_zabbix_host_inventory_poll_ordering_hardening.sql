-- Wave 4 host-inventory poll ordering hardening.
-- Closes out-of-order completion and stale-negative evidence races found in PR #135 review.

BEGIN;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN host_inventory_poll_generation BIGINT NOT NULL DEFAULT 0
    CHECK (host_inventory_poll_generation >= 0);

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN host_inventory_poll_generation BIGINT NULL
    CHECK (host_inventory_poll_generation IS NULL OR host_inventory_poll_generation > 0);

ALTER FUNCTION monitoring.complete_zabbix_host_inventory(
    TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT
) RENAME TO wave4_complete_zabbix_host_inventory_pre_poll_fence;

CREATE OR REPLACE FUNCTION monitoring.claim_zabbix_host_inventory(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT, provider_scope_tenant_binding_id TEXT,
    source_instance_generation TEXT, configuration_revision BIGINT,
    scope_revision BIGINT, provider_instance_ref TEXT, provider_base_url TEXT,
    credential_binding_ref TEXT, configured_provider_scope JSONB
)
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_generation BIGINT;
BEGIN
    IF p_claim_token IS NULL OR p_claim_token='' OR length(p_claim_token)>512
       OR p_claim_token<>btrim(p_claim_token) OR p_claim_token~'[[:cntrl:]]' THEN
        RAISE EXCEPTION 'invalid host inventory claim token';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='host_inventory_sync'
       AND o.state='pending'
       AND o.claim_token IS NULL
       AND o.host_inventory_poll_generation IS NULL
     FOR UPDATE OF o;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_not_claimable';
    END IF;

    PERFORM 1
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
       AND s.active_source_instance_generation=v_generation
       AND s.configuration_revision=v_configuration_revision
       AND s.scope_revision=v_scope_revision
       AND EXISTS (
           SELECT 1
             FROM monitoring.monitoring_source_validation_evidence AS v
            WHERE v.tenant_id=s.tenant_id
              AND v.monitoring_source_id=s.monitoring_source_id
              AND v.source_instance_generation=v_generation
              AND v.configuration_revision=v_configuration_revision
              AND v.scope_revision=v_scope_revision
              AND v.operation_state='succeeded'
              AND v.operational_evidence_state='current'
       )
     FOR UPDATE OF s;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_stale_authority';
    END IF;

    UPDATE monitoring.monitoring_source AS s
       SET host_inventory_poll_generation=s.host_inventory_poll_generation+1,
           last_attempt_at=transaction_timestamp(),
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
     RETURNING s.host_inventory_poll_generation INTO v_poll_generation;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='running',
           claim_token=p_claim_token,
           host_inventory_poll_generation=v_poll_generation,
           attempt_count=o.attempt_count+1,
           started_at=transaction_timestamp()
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN QUERY
    SELECT s.monitoring_source_id,s.provider_scope_tenant_binding_id,
           o.source_instance_generation,o.configuration_revision,o.scope_revision,
           g.provider_instance_ref,g.provider_base_url,s.credential_binding_ref,s.configured_provider_scope
      FROM monitoring.monitoring_sync_operation AS o
      JOIN monitoring.monitoring_source AS s
        ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id
      JOIN monitoring.monitoring_source_generation AS g
        ON g.tenant_id=o.tenant_id
       AND g.monitoring_source_id=o.monitoring_source_id
       AND g.source_instance_generation=o.source_instance_generation
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
END;
$$;

CREATE FUNCTION monitoring.complete_zabbix_host_inventory(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_snapshot_evidence_id TEXT,
    p_provider_scope_tenant_binding_id TEXT,
    p_provider_instance_ref TEXT,
    p_operational_evidence_state TEXT,
    p_operation_state TEXT,
    p_failure_class TEXT,
    p_snapshot_complete BOOLEAN,
    p_hosts JSONB,
    p_egress_decision_ref TEXT,
    p_credential_generation_ref TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
DECLARE
    v_poll_generation BIGINT;
    v_current_poll_generation BIGINT;
BEGIN
    SELECT o.host_inventory_poll_generation,s.host_inventory_poll_generation
      INTO v_poll_generation,v_current_poll_generation
      FROM monitoring.monitoring_sync_operation AS o
      JOIN monitoring.monitoring_source AS s
        ON s.tenant_id=o.tenant_id
       AND s.monitoring_source_id=o.monitoring_source_id
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='host_inventory_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE OF s,o;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_claim_lost';
    END IF;

    IF v_poll_generation IS NULL OR v_poll_generation <> v_current_poll_generation THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',
               completed_at=transaction_timestamp(),
               last_error_class='execution.superseded_poll_authority',
               claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN;
    END IF;

    PERFORM monitoring.wave4_complete_zabbix_host_inventory_pre_poll_fence(
        p_tenant_id,
        p_monitoring_sync_operation_id,
        p_claim_token,
        p_snapshot_evidence_id,
        p_provider_scope_tenant_binding_id,
        p_provider_instance_ref,
        p_operational_evidence_state,
        p_operation_state,
        p_failure_class,
        p_snapshot_complete,
        p_hosts,
        p_egress_decision_ref,
        p_credential_generation_ref
    );
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_monitoring_resource_update()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
       OR NEW.resource_kind IS DISTINCT FROM OLD.resource_kind
       OR NEW.provider_object_kind IS DISTINCT FROM OLD.provider_object_kind
       OR NEW.provider_external_ref IS DISTINCT FROM OLD.provider_external_ref THEN
        RAISE EXCEPTION 'Monitoring resource canonical/provider identity is immutable';
    END IF;
    IF NEW.scope_projection_revision < OLD.scope_projection_revision THEN
        RAISE EXCEPTION 'Monitoring resource scope projection revision cannot regress';
    END IF;
    IF NEW.last_observed_at < OLD.last_observed_at
       OR NEW.last_confirmed_present_at < OLD.last_confirmed_present_at THEN
        RAISE EXCEPTION 'Monitoring resource observation timestamps cannot regress';
    END IF;
    IF OLD.presence_state <> 'removed' AND NEW.presence_state = 'removed' THEN
        IF NOT EXISTS (
            SELECT 1
              FROM monitoring.monitoring_host_inventory_snapshot_evidence AS e
             WHERE e.tenant_id=OLD.tenant_id
               AND e.monitoring_source_id=OLD.monitoring_source_id
               AND e.source_instance_generation=OLD.source_instance_generation
               AND e.scope_revision=OLD.scope_projection_revision
               AND e.snapshot_complete
               AND e.operation_state='succeeded'
               AND e.observed_at=NEW.removed_at
               AND e.observed_at > OLD.last_confirmed_present_at
               AND NOT EXISTS (
                   SELECT 1
                     FROM monitoring.monitoring_resource_provider_evidence AS pe
                    WHERE pe.tenant_id=e.tenant_id
                      AND pe.host_inventory_snapshot_evidence_id=e.host_inventory_snapshot_evidence_id
                      AND pe.provider_external_ref=OLD.provider_external_ref
               )
        ) THEN
            RAISE EXCEPTION 'Monitoring resource removal requires newer complete authoritative negative snapshot evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;