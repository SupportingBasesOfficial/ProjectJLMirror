-- Wave 4 host-inventory superseded-epoch retirement hardening.
-- A pre-recovery running poll must retire cleanly after recovery establishes a
-- successor epoch; it must not reach snapshot insertion and fail transactionally.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_host_inventory(
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
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_generation BIGINT;
    v_current_poll_generation BIGINT;
    v_poll_epoch BIGINT;
    v_current_poll_epoch BIGINT;
    v_observed_at TIMESTAMPTZ := transaction_timestamp();
    v_host JSONB;
    v_resource_id TEXT;
    v_provider_evidence_id TEXT;
    v_hostid TEXT;
    v_display_name TEXT;
    v_fingerprint TEXT;
    v_evidence JSONB;
    v_host_count BIGINT;
BEGIN
    IF jsonb_typeof(p_hosts) <> 'array' OR jsonb_array_length(p_hosts) > 50000 THEN
        RAISE EXCEPTION 'invalid bounded host inventory payload';
    END IF;
    IF p_operation_state NOT IN ('succeeded','reconciliation_required')
       OR p_operational_evidence_state NOT IN ('current','incomplete','unavailable')
       OR (p_operation_state='succeeded') <> p_snapshot_complete
       OR (p_operation_state='succeeded') <> (p_operational_evidence_state='current')
       OR (p_operation_state='succeeded') <> (p_failure_class IS NULL) THEN
        RAISE EXCEPTION 'invalid host inventory completion state';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,
           o.configuration_revision,o.scope_revision,o.host_inventory_poll_generation,
           s.host_inventory_poll_generation,o.host_inventory_poll_epoch,s.host_inventory_poll_epoch
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision,
           v_poll_generation,v_current_poll_generation,v_poll_epoch,v_current_poll_epoch
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

    -- Recovery/placement epoch is the outer authority fence. Retire stale work
    -- before any snapshot/evidence write so the retirement itself can commit.
    IF v_poll_epoch IS NULL
       OR v_poll_epoch <> v_current_poll_epoch
       OR NOT EXISTS (
           SELECT 1
             FROM monitoring.monitoring_host_inventory_runtime_admission AS a
            WHERE a.tenant_id=p_tenant_id
              AND a.monitoring_source_id=v_source_id
              AND a.host_inventory_poll_epoch=v_current_poll_epoch
       ) THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',
               completed_at=v_observed_at,
               last_error_class='execution.superseded_poll_epoch_authority',
               claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN;
    END IF;

    IF v_poll_generation IS NULL OR v_poll_generation <> v_current_poll_generation THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',
               completed_at=v_observed_at,
               last_error_class='execution.superseded_poll_authority',
               claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
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
           AND s.provider_scope_tenant_binding_id=p_provider_scope_tenant_binding_id
           AND g.provider_instance_ref=p_provider_instance_ref
    ) THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',
               completed_at=v_observed_at,
               last_error_class='execution.stale_authority',
               claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN;
    END IF;

    v_host_count := jsonb_array_length(p_hosts);
    INSERT INTO monitoring.monitoring_host_inventory_snapshot_evidence(
        tenant_id,host_inventory_snapshot_evidence_id,monitoring_sync_operation_id,
        monitoring_source_id,provider_scope_tenant_binding_id,source_instance_generation,
        configuration_revision,scope_revision,provider_instance_ref,
        snapshot_complete,host_count,operational_evidence_state,operation_state,
        failure_class,egress_decision_ref,credential_generation_ref,observed_at,
        host_inventory_poll_generation
    ) VALUES (
        p_tenant_id,p_snapshot_evidence_id,p_monitoring_sync_operation_id,
        v_source_id,p_provider_scope_tenant_binding_id,v_generation,
        v_configuration_revision,v_scope_revision,p_provider_instance_ref,
        p_snapshot_complete,v_host_count,p_operational_evidence_state,p_operation_state,
        p_failure_class,p_egress_decision_ref,p_credential_generation_ref,v_observed_at,
        v_poll_generation
    );

    FOR v_host IN SELECT value FROM jsonb_array_elements(p_hosts) LOOP
        IF jsonb_typeof(v_host) <> 'object'
           OR (v_host - ARRAY['monitoring_resource_id','provider_evidence_id','hostid','display_name','evidence_fingerprint','normalized_evidence']::TEXT[]) <> '{}'::jsonb
           OR NOT (v_host ?& ARRAY['monitoring_resource_id','provider_evidence_id','hostid','display_name','evidence_fingerprint','normalized_evidence']) THEN
            RAISE EXCEPTION 'invalid normalized host evidence shape';
        END IF;
        v_resource_id := v_host->>'monitoring_resource_id';
        v_provider_evidence_id := v_host->>'provider_evidence_id';
        v_hostid := v_host->>'hostid';
        v_display_name := v_host->>'display_name';
        v_fingerprint := v_host->>'evidence_fingerprint';
        v_evidence := v_host->'normalized_evidence';
        IF v_resource_id IS NULL OR v_resource_id='' OR length(v_resource_id)>512
           OR v_provider_evidence_id IS NULL OR v_provider_evidence_id='' OR length(v_provider_evidence_id)>512
           OR v_hostid IS NULL OR v_hostid='' OR length(v_hostid)>256
           OR v_display_name IS NULL OR v_display_name='' OR length(v_display_name)>512
           OR v_fingerprint !~ '^[0-9a-f]{64}$'
           OR jsonb_typeof(v_evidence) <> 'object'
           OR octet_length(v_evidence::text) > 65536 THEN
            RAISE EXCEPTION 'invalid bounded normalized host evidence';
        END IF;

        INSERT INTO monitoring.monitoring_resource(
            tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
            resource_kind,provider_object_kind,provider_external_ref,display_name,
            scope_state,scope_projection_revision,scope_evidence_state,
            presence_state,presence_evidence_state,last_observed_at,
            last_confirmed_present_at,removed_at,last_confirmed_present_poll_generation,
            removed_poll_generation
        ) VALUES (
            p_tenant_id,v_resource_id,v_source_id,v_generation,
            'host','zabbix_host',v_hostid,v_display_name,
            'in_scope',v_scope_revision,'current',
            'present',CASE WHEN p_snapshot_complete THEN 'current' ELSE 'incomplete' END,
            v_observed_at,v_observed_at,NULL,v_poll_generation,NULL
        )
        ON CONFLICT (tenant_id,monitoring_source_id,source_instance_generation,provider_external_ref)
        DO UPDATE SET
            display_name=EXCLUDED.display_name,
            scope_state='in_scope',
            scope_projection_revision=v_scope_revision,
            scope_evidence_state='current',
            presence_state='present',
            presence_evidence_state=CASE WHEN p_snapshot_complete THEN 'current' ELSE 'incomplete' END,
            last_observed_at=v_observed_at,
            last_confirmed_present_at=v_observed_at,
            last_confirmed_present_poll_generation=v_poll_generation,
            removed_at=NULL,
            removed_poll_generation=NULL,
            updated_at=v_observed_at
        RETURNING monitoring_resource_id INTO v_resource_id;

        INSERT INTO monitoring.monitoring_resource_provider_evidence(
            tenant_id,provider_evidence_id,host_inventory_snapshot_evidence_id,
            monitoring_resource_id,monitoring_source_id,source_instance_generation,
            provider_object_kind,provider_external_ref,evidence_fingerprint,
            normalized_evidence,observed_at
        ) VALUES (
            p_tenant_id,v_provider_evidence_id,p_snapshot_evidence_id,
            v_resource_id,v_source_id,v_generation,
            'zabbix_host',v_hostid,v_fingerprint,v_evidence,v_observed_at
        );

        UPDATE monitoring.monitoring_resource AS r
           SET latest_provider_evidence_id=v_provider_evidence_id
         WHERE r.tenant_id=p_tenant_id
           AND r.monitoring_resource_id=v_resource_id;
    END LOOP;

    IF p_snapshot_complete THEN
        UPDATE monitoring.monitoring_resource AS r
           SET presence_state='removed',
               presence_evidence_state='current',
               removed_at=v_observed_at,
               removed_poll_generation=v_poll_generation,
               updated_at=v_observed_at
         WHERE r.tenant_id=p_tenant_id
           AND r.monitoring_source_id=v_source_id
           AND r.source_instance_generation=v_generation
           AND r.scope_state='in_scope'
           AND r.scope_projection_revision=v_scope_revision
           AND r.presence_state='present'
           AND r.last_confirmed_present_poll_generation < v_poll_generation
           AND NOT EXISTS (
               SELECT 1
                 FROM jsonb_array_elements(p_hosts) AS h
                WHERE h->>'hostid'=r.provider_external_ref
           );
    ELSE
        UPDATE monitoring.monitoring_resource AS r
           SET presence_evidence_state=p_operational_evidence_state,
               updated_at=v_observed_at
         WHERE r.tenant_id=p_tenant_id
           AND r.monitoring_source_id=v_source_id
           AND r.source_instance_generation=v_generation
           AND r.presence_state='present';
    END IF;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state=p_operation_state,
           completed_at=v_observed_at,
           last_error_class=p_failure_class,
           host_inventory_snapshot_evidence_id=p_snapshot_evidence_id
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    UPDATE monitoring.monitoring_source AS s
       SET operational_evidence_state=p_operational_evidence_state,
           last_successful_sync_at=CASE WHEN p_snapshot_complete THEN v_observed_at ELSE s.last_successful_sync_at END,
           updated_at=v_observed_at
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id;
END;
$$;

ALTER FUNCTION monitoring.complete_zabbix_host_inventory(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT)
OWNER TO jlmirror_wave4_host_inventory_executor;

COMMIT;
