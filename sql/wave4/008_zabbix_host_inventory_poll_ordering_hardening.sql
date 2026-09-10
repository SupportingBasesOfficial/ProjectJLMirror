-- Wave 4 host-inventory poll ordering hardening.
-- Closes out-of-order completion and stale-negative evidence races found in PR #135 review.
-- The public completion function is replaced in place; no unfenced helper remains callable.
-- Poll generation, not wall-clock time, is the authoritative presence ordering field.

BEGIN;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN host_inventory_poll_generation BIGINT NOT NULL DEFAULT 0
    CHECK (host_inventory_poll_generation >= 0);

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN host_inventory_poll_generation BIGINT NULL
    CHECK (host_inventory_poll_generation IS NULL OR host_inventory_poll_generation > 0);

ALTER TABLE monitoring.monitoring_host_inventory_snapshot_evidence
    ADD COLUMN host_inventory_poll_generation BIGINT NULL
    CHECK (host_inventory_poll_generation IS NULL OR host_inventory_poll_generation > 0);

ALTER TABLE monitoring.monitoring_resource
    ADD COLUMN last_confirmed_present_poll_generation BIGINT NOT NULL DEFAULT 0
        CHECK (last_confirmed_present_poll_generation >= 0),
    ADD COLUMN removed_poll_generation BIGINT NULL
        CHECK (removed_poll_generation IS NULL OR removed_poll_generation > 0),
    ADD CONSTRAINT monitoring_resource_removed_poll_generation_state
        CHECK ((presence_state = 'removed') = (removed_poll_generation IS NOT NULL));

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
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_generation BIGINT;
    v_current_poll_generation BIGINT;
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
           s.host_inventory_poll_generation
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision,
           v_poll_generation,v_current_poll_generation
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

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_monitoring_resource_update()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
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
       OR NEW.last_confirmed_present_at < OLD.last_confirmed_present_at
       OR NEW.last_confirmed_present_poll_generation < OLD.last_confirmed_present_poll_generation THEN
        RAISE EXCEPTION 'Monitoring resource observation authority cannot regress';
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
               AND e.host_inventory_poll_generation=NEW.removed_poll_generation
               AND e.host_inventory_poll_generation > OLD.last_confirmed_present_poll_generation
               AND e.observed_at=NEW.removed_at
               AND NOT EXISTS (
                   SELECT 1
                     FROM monitoring.monitoring_resource_provider_evidence AS pe
                    WHERE pe.tenant_id=e.tenant_id
                      AND pe.host_inventory_snapshot_evidence_id=e.host_inventory_snapshot_evidence_id
                      AND pe.provider_external_ref=OLD.provider_external_ref
               )
        ) THEN
            RAISE EXCEPTION 'Monitoring resource removal requires newer complete authoritative negative poll evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
