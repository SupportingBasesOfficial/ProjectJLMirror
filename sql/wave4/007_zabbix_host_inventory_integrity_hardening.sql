-- Wave 4 host-inventory identity/evidence integrity hardening.
-- Keeps canonical resource identity immutable and binds evidence pointers to their owner.

BEGIN;

CREATE FUNCTION monitoring.wave4_is_canonical_zabbix_host_evidence_details(p_evidence JSONB)
RETURNS BOOLEAN
LANGUAGE plpgsql IMMUTABLE STRICT
SET search_path = pg_catalog, monitoring
AS $$
DECLARE row JSONB;
BEGIN
    FOR row IN SELECT value FROM jsonb_array_elements(p_evidence->'interfaces') LOOP
        IF row->>'interfaceid' <> btrim(row->>'interfaceid')
           OR row->>'interfaceid' ~ '[[:cntrl:]]'
           OR ((row ? 'ip') AND row->>'ip' <> btrim(row->>'ip'))
           OR ((row ? 'dns') AND row->>'dns' <> btrim(row->>'dns'))
           OR ((row ? 'port') AND row->>'port' <> btrim(row->>'port')) THEN
            RETURN FALSE;
        END IF;
    END LOOP;
    FOR row IN SELECT value FROM jsonb_array_elements(p_evidence->'tags') LOOP
        IF row->>'tag' <> btrim(row->>'tag') THEN
            RETURN FALSE;
        END IF;
    END LOOP;
    RETURN TRUE;
EXCEPTION WHEN OTHERS THEN
    RETURN FALSE;
END;
$$;

ALTER TABLE monitoring.monitoring_resource_provider_evidence
    ADD CONSTRAINT monitoring_resource_provider_evidence_canonical_details
    CHECK (monitoring.wave4_is_canonical_zabbix_host_evidence_details(normalized_evidence));

ALTER TABLE monitoring.monitoring_resource
    ADD CONSTRAINT monitoring_resource_canonical_identity_text CHECK (
        monitoring_resource_id=btrim(monitoring_resource_id)
        AND monitoring_resource_id !~ '[[:cntrl:]]'
        AND provider_external_ref=btrim(provider_external_ref)
        AND provider_external_ref !~ '[[:cntrl:]]'
        AND display_name=btrim(display_name)
        AND display_name !~ '[[:cntrl:]]'
    );

ALTER TABLE monitoring.monitoring_host_inventory_snapshot_evidence
    ADD CONSTRAINT monitoring_host_inventory_snapshot_identity_text CHECK (
        host_inventory_snapshot_evidence_id<>''
        AND length(host_inventory_snapshot_evidence_id)<=512
        AND host_inventory_snapshot_evidence_id=btrim(host_inventory_snapshot_evidence_id)
        AND host_inventory_snapshot_evidence_id !~ '[[:cntrl:]]'
        AND provider_scope_tenant_binding_id<>''
        AND provider_instance_ref<>''
    ),
    ADD CONSTRAINT monitoring_host_inventory_snapshot_owner_unique
    UNIQUE (tenant_id, monitoring_sync_operation_id, host_inventory_snapshot_evidence_id);

ALTER TABLE monitoring.monitoring_resource_provider_evidence
    ADD CONSTRAINT monitoring_resource_provider_evidence_identity_text CHECK (
        provider_evidence_id<>''
        AND length(provider_evidence_id)<=512
        AND provider_evidence_id=btrim(provider_evidence_id)
        AND provider_evidence_id !~ '[[:cntrl:]]'
        AND provider_external_ref=btrim(provider_external_ref)
        AND provider_external_ref !~ '[[:cntrl:]]'
    ),
    ADD CONSTRAINT monitoring_resource_provider_evidence_owner_unique
    UNIQUE (tenant_id, monitoring_resource_id, provider_evidence_id);

ALTER TABLE monitoring.monitoring_sync_operation
    ADD CONSTRAINT monitoring_sync_operation_host_inventory_snapshot_owner_fk
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id, host_inventory_snapshot_evidence_id)
    REFERENCES monitoring.monitoring_host_inventory_snapshot_evidence(
        tenant_id, monitoring_sync_operation_id, host_inventory_snapshot_evidence_id
    ) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE monitoring.monitoring_resource
    DROP CONSTRAINT monitoring_resource_latest_provider_evidence_fk;
ALTER TABLE monitoring.monitoring_resource
    ADD CONSTRAINT monitoring_resource_latest_provider_evidence_owner_fk
    FOREIGN KEY (tenant_id, monitoring_resource_id, latest_provider_evidence_id)
    REFERENCES monitoring.monitoring_resource_provider_evidence(
        tenant_id, monitoring_resource_id, provider_evidence_id
    ) DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION monitoring.wave4_guard_monitoring_resource_update()
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
              FROM monitoring.monitoring_host_inventory_snapshot_evidence e
             WHERE e.tenant_id=OLD.tenant_id
               AND e.monitoring_source_id=OLD.monitoring_source_id
               AND e.source_instance_generation=OLD.source_instance_generation
               AND e.scope_revision=OLD.scope_projection_revision
               AND e.snapshot_complete
               AND e.operation_state='succeeded'
               AND e.observed_at=NEW.removed_at
               AND NOT EXISTS (
                   SELECT 1
                     FROM monitoring.monitoring_resource_provider_evidence pe
                    WHERE pe.tenant_id=e.tenant_id
                      AND pe.host_inventory_snapshot_evidence_id=e.host_inventory_snapshot_evidence_id
                      AND pe.provider_external_ref=OLD.provider_external_ref
               )
        ) THEN
            RAISE EXCEPTION 'Monitoring resource removal requires complete authoritative negative snapshot evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_monitoring_resource_update_guard
BEFORE UPDATE ON monitoring.monitoring_resource
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_monitoring_resource_update();

COMMIT;
