-- Wave 4 bounded Zabbix host-inventory ingestion.
-- Authority: wave4.monitoring-host-inventory@1 as made canonical by PR #134.
-- No metrics/problems/health/write-back/frontend behavior is introduced here.

BEGIN;

ALTER TABLE monitoring.monitoring_sync_operation
    DROP CONSTRAINT monitoring_sync_operation_responsibility_kind_check;
ALTER TABLE monitoring.monitoring_sync_operation
    ADD CONSTRAINT monitoring_sync_operation_responsibility_kind_check
    CHECK (responsibility_kind IN (
        'validation_and_initial_sync', 'host_inventory_sync', 'manual_sync',
        'scope_reconciliation', 'replacement_candidate_validation',
        'post_cutover_reconciliation'
    ));

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN host_inventory_snapshot_evidence_id TEXT NULL;

CREATE TABLE monitoring.monitoring_resource (
    tenant_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    resource_kind TEXT NOT NULL CHECK (resource_kind = 'host'),
    provider_object_kind TEXT NOT NULL CHECK (provider_object_kind = 'zabbix_host'),
    provider_external_ref TEXT NOT NULL,
    display_name TEXT NOT NULL,
    scope_state TEXT NOT NULL CHECK (scope_state IN ('in_scope','out_of_scope')),
    scope_projection_revision BIGINT NOT NULL CHECK (scope_projection_revision > 0),
    scope_evidence_state TEXT NOT NULL CHECK (scope_evidence_state IN ('current','reconciliation_required')),
    presence_state TEXT NOT NULL CHECK (presence_state IN ('present','removed')),
    presence_evidence_state TEXT NOT NULL CHECK (presence_evidence_state IN ('current','incomplete','unavailable','reconciliation_required')),
    last_observed_at TIMESTAMPTZ NOT NULL,
    last_confirmed_present_at TIMESTAMPTZ NOT NULL,
    removed_at TIMESTAMPTZ NULL,
    latest_provider_evidence_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_resource_id),
    UNIQUE (tenant_id, monitoring_source_id, source_instance_generation, provider_external_ref),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK (monitoring_resource_id <> '' AND length(monitoring_resource_id) <= 512),
    CHECK (provider_external_ref <> '' AND length(provider_external_ref) <= 256),
    CHECK (display_name <> '' AND length(display_name) <= 512),
    CHECK ((presence_state = 'removed') = (removed_at IS NOT NULL))
);

CREATE TABLE monitoring.monitoring_host_inventory_snapshot_evidence (
    tenant_id TEXT NOT NULL,
    host_inventory_snapshot_evidence_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    provider_scope_tenant_binding_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    provider_instance_ref TEXT NOT NULL,
    snapshot_complete BOOLEAN NOT NULL,
    host_count BIGINT NOT NULL CHECK (host_count >= 0 AND host_count <= 50000),
    operational_evidence_state TEXT NOT NULL CHECK (operational_evidence_state IN ('current','incomplete','unavailable')),
    operation_state TEXT NOT NULL CHECK (operation_state IN ('succeeded','reconciliation_required')),
    failure_class TEXT NULL,
    egress_decision_ref TEXT NULL,
    credential_generation_ref TEXT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, host_inventory_snapshot_evidence_id),
    UNIQUE (tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id)
        REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK ((operation_state = 'succeeded') = snapshot_complete),
    CHECK ((operation_state = 'succeeded') = (operational_evidence_state = 'current')),
    CHECK ((operation_state = 'succeeded') = (failure_class IS NULL))
);

CREATE TABLE monitoring.monitoring_resource_provider_evidence (
    tenant_id TEXT NOT NULL,
    provider_evidence_id TEXT NOT NULL,
    host_inventory_snapshot_evidence_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    provider_object_kind TEXT NOT NULL CHECK (provider_object_kind = 'zabbix_host'),
    provider_external_ref TEXT NOT NULL,
    evidence_fingerprint TEXT NOT NULL CHECK (evidence_fingerprint ~ '^[0-9a-f]{64}$'),
    normalized_evidence JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, provider_evidence_id),
    UNIQUE (tenant_id, host_inventory_snapshot_evidence_id, provider_external_ref),
    FOREIGN KEY (tenant_id, host_inventory_snapshot_evidence_id)
        REFERENCES monitoring.monitoring_host_inventory_snapshot_evidence(tenant_id, host_inventory_snapshot_evidence_id),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    CHECK (provider_external_ref <> '' AND length(provider_external_ref) <= 256),
    CHECK (jsonb_typeof(normalized_evidence) = 'object'),
    CHECK (octet_length(normalized_evidence::text) <= 65536)
);

ALTER TABLE monitoring.monitoring_resource
    ADD CONSTRAINT monitoring_resource_latest_provider_evidence_fk
    FOREIGN KEY (tenant_id, latest_provider_evidence_id)
    REFERENCES monitoring.monitoring_resource_provider_evidence(tenant_id, provider_evidence_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION monitoring.wave4_reject_host_inventory_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
BEGIN
    RAISE EXCEPTION 'Monitoring host inventory evidence is immutable';
END;
$$;

CREATE TRIGGER wave4_host_inventory_snapshot_evidence_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_host_inventory_snapshot_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_host_inventory_evidence_mutation();

CREATE TRIGGER wave4_resource_provider_evidence_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_resource_provider_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_host_inventory_evidence_mutation();

ALTER TABLE monitoring.monitoring_resource ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_resource FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_resource_tenant_policy ON monitoring.monitoring_resource
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

ALTER TABLE monitoring.monitoring_host_inventory_snapshot_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_host_inventory_snapshot_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_host_inventory_snapshot_evidence_tenant_policy ON monitoring.monitoring_host_inventory_snapshot_evidence
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

ALTER TABLE monitoring.monitoring_resource_provider_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_resource_provider_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_resource_provider_evidence_tenant_policy ON monitoring.monitoring_resource_provider_evidence
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

CREATE FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_monitoring_sync_operation_id TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring AS $$
DECLARE
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
BEGIN
    SELECT active_source_instance_generation, configuration_revision, scope_revision
      INTO v_generation, v_configuration_revision, v_scope_revision
      FROM monitoring.monitoring_source
     WHERE tenant_id = p_tenant_id
       AND monitoring_source_id = p_monitoring_source_id
       AND operational_evidence_state = 'current'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_source_not_current';
    END IF;
    INSERT INTO monitoring.monitoring_sync_operation(
        tenant_id, monitoring_sync_operation_id, monitoring_source_id,
        source_instance_generation, configuration_revision, scope_revision,
        responsibility_kind, state
    ) VALUES (
        p_tenant_id, p_monitoring_sync_operation_id, p_monitoring_source_id,
        v_generation, v_configuration_revision, v_scope_revision,
        'host_inventory_sync', 'pending'
    );
    UPDATE monitoring.monitoring_source
       SET last_sync_operation_id = p_monitoring_sync_operation_id,
           updated_at = transaction_timestamp()
     WHERE tenant_id = p_tenant_id AND monitoring_source_id = p_monitoring_source_id;
END;
$$;

CREATE FUNCTION monitoring.claim_zabbix_host_inventory(
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
BEGIN
    SELECT o.monitoring_source_id, o.source_instance_generation
      INTO v_source_id, v_generation
      FROM monitoring.monitoring_sync_operation o
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id
       AND o.responsibility_kind = 'host_inventory_sync'
       AND o.state = 'pending'
       AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_not_claimable';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_source s
         WHERE s.tenant_id = p_tenant_id
           AND s.monitoring_source_id = v_source_id
           AND s.active_source_instance_generation = v_generation
           AND s.operational_evidence_state = 'current'
    ) THEN
        RAISE EXCEPTION 'monitoring.host_inventory_stale_authority';
    END IF;

    UPDATE monitoring.monitoring_sync_operation
       SET state='running', claim_token=p_claim_token,
           attempt_count=attempt_count+1, started_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    UPDATE monitoring.monitoring_source
       SET last_attempt_at=transaction_timestamp(), updated_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=v_source_id;

    RETURN QUERY
    SELECT s.monitoring_source_id, s.provider_scope_tenant_binding_id,
           o.source_instance_generation, o.configuration_revision, o.scope_revision,
           g.provider_instance_ref, g.provider_base_url, s.credential_binding_ref,
           s.configured_provider_scope
      FROM monitoring.monitoring_sync_operation o
      JOIN monitoring.monitoring_source s
        ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id
      JOIN monitoring.monitoring_source_generation g
        ON g.tenant_id=o.tenant_id AND g.monitoring_source_id=o.monitoring_source_id
       AND g.source_instance_generation=o.source_instance_generation
     WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
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
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
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

    SELECT o.monitoring_source_id, o.source_instance_generation,
           o.configuration_revision, o.scope_revision
      INTO v_source_id, v_generation, v_configuration_revision, v_scope_revision
      FROM monitoring.monitoring_sync_operation o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='host_inventory_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.host_inventory_claim_lost';
    END IF;

    PERFORM 1
      FROM monitoring.monitoring_source s
      JOIN monitoring.monitoring_source_generation g
        ON g.tenant_id=s.tenant_id AND g.monitoring_source_id=s.monitoring_source_id
       AND g.source_instance_generation=s.active_source_instance_generation
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
       AND s.active_source_instance_generation=v_generation
       AND s.configuration_revision=v_configuration_revision
       AND s.scope_revision=v_scope_revision
       AND s.provider_scope_tenant_binding_id=p_provider_scope_tenant_binding_id
       AND g.provider_instance_ref=p_provider_instance_ref
     FOR UPDATE OF s;
    IF NOT FOUND THEN
        UPDATE monitoring.monitoring_sync_operation
           SET state='reconciliation_required', completed_at=transaction_timestamp(),
               last_error_class='execution.stale_authority', claim_token=NULL
         WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN;
    END IF;

    v_host_count := jsonb_array_length(p_hosts);
    INSERT INTO monitoring.monitoring_host_inventory_snapshot_evidence(
        tenant_id, host_inventory_snapshot_evidence_id, monitoring_sync_operation_id,
        monitoring_source_id, provider_scope_tenant_binding_id, source_instance_generation,
        configuration_revision, scope_revision, provider_instance_ref,
        snapshot_complete, host_count, operational_evidence_state, operation_state,
        failure_class, egress_decision_ref, credential_generation_ref, observed_at
    ) VALUES (
        p_tenant_id, p_snapshot_evidence_id, p_monitoring_sync_operation_id,
        v_source_id, p_provider_scope_tenant_binding_id, v_generation,
        v_configuration_revision, v_scope_revision, p_provider_instance_ref,
        p_snapshot_complete, v_host_count, p_operational_evidence_state, p_operation_state,
        p_failure_class, p_egress_decision_ref, p_credential_generation_ref, v_observed_at
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
            tenant_id, monitoring_resource_id, monitoring_source_id, source_instance_generation,
            resource_kind, provider_object_kind, provider_external_ref, display_name,
            scope_state, scope_projection_revision, scope_evidence_state,
            presence_state, presence_evidence_state, last_observed_at,
            last_confirmed_present_at, removed_at
        ) VALUES (
            p_tenant_id, v_resource_id, v_source_id, v_generation,
            'host', 'zabbix_host', v_hostid, v_display_name,
            'in_scope', v_scope_revision, 'current',
            'present', CASE WHEN p_snapshot_complete THEN 'current' ELSE 'incomplete' END,
            v_observed_at, v_observed_at, NULL
        )
        ON CONFLICT (tenant_id, monitoring_source_id, source_instance_generation, provider_external_ref)
        DO UPDATE SET
            display_name=EXCLUDED.display_name,
            scope_state='in_scope',
            scope_projection_revision=v_scope_revision,
            scope_evidence_state='current',
            presence_state='present',
            presence_evidence_state=CASE WHEN p_snapshot_complete THEN 'current' ELSE 'incomplete' END,
            last_observed_at=v_observed_at,
            last_confirmed_present_at=v_observed_at,
            removed_at=NULL,
            updated_at=v_observed_at
        RETURNING monitoring_resource_id INTO v_resource_id;

        INSERT INTO monitoring.monitoring_resource_provider_evidence(
            tenant_id, provider_evidence_id, host_inventory_snapshot_evidence_id,
            monitoring_resource_id, monitoring_source_id, source_instance_generation,
            provider_object_kind, provider_external_ref, evidence_fingerprint,
            normalized_evidence, observed_at
        ) VALUES (
            p_tenant_id, v_provider_evidence_id, p_snapshot_evidence_id,
            v_resource_id, v_source_id, v_generation,
            'zabbix_host', v_hostid, v_fingerprint, v_evidence, v_observed_at
        );

        UPDATE monitoring.monitoring_resource
           SET latest_provider_evidence_id=v_provider_evidence_id
         WHERE tenant_id=p_tenant_id AND monitoring_resource_id=v_resource_id;
    END LOOP;

    IF p_snapshot_complete THEN
        UPDATE monitoring.monitoring_resource r
           SET presence_state='removed', presence_evidence_state='current',
               removed_at=v_observed_at, updated_at=v_observed_at
         WHERE r.tenant_id=p_tenant_id
           AND r.monitoring_source_id=v_source_id
           AND r.source_instance_generation=v_generation
           AND r.scope_state='in_scope'
           AND r.scope_projection_revision=v_scope_revision
           AND r.presence_state='present'
           AND NOT EXISTS (
               SELECT 1 FROM jsonb_array_elements(p_hosts) h
                WHERE h->>'hostid'=r.provider_external_ref
           );
    ELSE
        UPDATE monitoring.monitoring_resource r
           SET presence_evidence_state=p_operational_evidence_state,
               updated_at=v_observed_at
         WHERE r.tenant_id=p_tenant_id
           AND r.monitoring_source_id=v_source_id
           AND r.source_instance_generation=v_generation
           AND r.presence_state='present';
    END IF;

    UPDATE monitoring.monitoring_sync_operation
       SET state=p_operation_state, completed_at=v_observed_at,
           last_error_class=p_failure_class,
           host_inventory_snapshot_evidence_id=p_snapshot_evidence_id
     WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    UPDATE monitoring.monitoring_source
       SET operational_evidence_state=p_operational_evidence_state,
           last_successful_sync_at=CASE WHEN p_snapshot_complete THEN v_observed_at ELSE last_successful_sync_at END,
           updated_at=v_observed_at
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=v_source_id;
END;
$$;

COMMIT;
