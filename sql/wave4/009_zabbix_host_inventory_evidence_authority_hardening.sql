-- Wave 4 host-inventory evidence-authority hardening.
-- Closes PR #135 review findings around operation binding, closed snapshot membership,
-- positive-presence authority, and cryptographic binding of fingerprints to evidence.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_python_canonical_jsonb(p_value JSONB)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
STRICT
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_type TEXT := jsonb_typeof(p_value);
    v_result TEXT;
BEGIN
    IF v_type = 'object' THEN
        SELECT '{' || COALESCE(string_agg(to_jsonb(key)::text || ':' || monitoring.wave4_python_canonical_jsonb(value), ',' ORDER BY key COLLATE "C"), '') || '}'
          INTO v_result
          FROM jsonb_each(p_value);
        RETURN v_result;
    ELSIF v_type = 'array' THEN
        SELECT '[' || COALESCE(string_agg(monitoring.wave4_python_canonical_jsonb(value), ',' ORDER BY ordinality), '') || ']'
          INTO v_result
          FROM jsonb_array_elements(p_value) WITH ORDINALITY AS a(value, ordinality);
        RETURN v_result;
    END IF;
    RETURN p_value::text;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_snapshot_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_sync_operation AS o
          JOIN monitoring.monitoring_source AS s
            ON s.tenant_id=o.tenant_id
           AND s.monitoring_source_id=o.monitoring_source_id
          JOIN monitoring.monitoring_source_generation AS g
            ON g.tenant_id=o.tenant_id
           AND g.monitoring_source_id=o.monitoring_source_id
           AND g.source_instance_generation=o.source_instance_generation
         WHERE o.tenant_id=NEW.tenant_id
           AND o.monitoring_sync_operation_id=NEW.monitoring_sync_operation_id
           AND o.responsibility_kind='host_inventory_sync'
           AND o.state='running'
           AND o.claim_token IS NOT NULL
           AND o.monitoring_source_id=NEW.monitoring_source_id
           AND o.source_instance_generation=NEW.source_instance_generation
           AND o.configuration_revision=NEW.configuration_revision
           AND o.scope_revision=NEW.scope_revision
           AND o.host_inventory_poll_generation=NEW.host_inventory_poll_generation
           AND s.active_source_instance_generation=NEW.source_instance_generation
           AND s.configuration_revision=NEW.configuration_revision
           AND s.scope_revision=NEW.scope_revision
           AND s.provider_scope_tenant_binding_id=NEW.provider_scope_tenant_binding_id
           AND g.provider_instance_ref=NEW.provider_instance_ref
    ) THEN
        RAISE EXCEPTION 'host inventory snapshot evidence is not bound to its claimed running operation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_inventory_snapshot_insert_authority ON monitoring.monitoring_host_inventory_snapshot_evidence;
CREATE TRIGGER wave4_host_inventory_snapshot_insert_authority
BEFORE INSERT ON monitoring.monitoring_host_inventory_snapshot_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_host_inventory_snapshot_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_provider_evidence_authority()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_expected_fingerprint TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_host_inventory_snapshot_evidence AS e
          JOIN monitoring.monitoring_sync_operation AS o
            ON o.tenant_id=e.tenant_id
           AND o.monitoring_sync_operation_id=e.monitoring_sync_operation_id
         WHERE e.tenant_id=NEW.tenant_id
           AND e.host_inventory_snapshot_evidence_id=NEW.host_inventory_snapshot_evidence_id
           AND e.monitoring_source_id=NEW.monitoring_source_id
           AND e.source_instance_generation=NEW.source_instance_generation
           AND e.observed_at=NEW.observed_at
           AND o.responsibility_kind='host_inventory_sync'
           AND o.state='running'
           AND o.claim_token IS NOT NULL
           AND o.monitoring_source_id=e.monitoring_source_id
           AND o.source_instance_generation=e.source_instance_generation
           AND o.configuration_revision=e.configuration_revision
           AND o.scope_revision=e.scope_revision
           AND o.host_inventory_poll_generation=e.host_inventory_poll_generation
    ) THEN
        RAISE EXCEPTION 'host provider evidence requires an open claimed snapshot operation';
    END IF;

    v_expected_fingerprint := encode(
        sha256(convert_to(monitoring.wave4_python_canonical_jsonb(NEW.normalized_evidence), 'UTF8')),
        'hex'
    );
    IF NEW.evidence_fingerprint IS DISTINCT FROM v_expected_fingerprint THEN
        RAISE EXCEPTION 'host provider evidence fingerprint does not match normalized evidence';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_provider_evidence_authority ON monitoring.monitoring_resource_provider_evidence;
CREATE TRIGGER wave4_host_provider_evidence_authority
BEFORE INSERT ON monitoring.monitoring_resource_provider_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_host_provider_evidence_authority();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_monitoring_resource_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
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
       OR NEW.last_confirmed_present_at < OLD.last_confirmed_present_at
       OR NEW.last_confirmed_present_poll_generation < OLD.last_confirmed_present_poll_generation THEN
        RAISE EXCEPTION 'Monitoring resource observation authority cannot regress';
    END IF;
    IF OLD.presence_state='removed' AND NEW.presence_state='present'
       AND NEW.last_confirmed_present_poll_generation <= OLD.removed_poll_generation THEN
        RAISE EXCEPTION 'Monitoring resource positive presence requires a poll newer than removal authority';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_deferred_monitoring_resource_presence_authority()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_resource monitoring.monitoring_resource%ROWTYPE;
BEGIN
    SELECT * INTO v_resource
      FROM monitoring.monitoring_resource AS r
     WHERE r.tenant_id=NEW.tenant_id
       AND r.monitoring_resource_id=NEW.monitoring_resource_id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF v_resource.presence_state='present' THEN
        IF v_resource.latest_provider_evidence_id IS NULL OR NOT EXISTS (
            SELECT 1
              FROM monitoring.monitoring_resource_provider_evidence AS pe
              JOIN monitoring.monitoring_host_inventory_snapshot_evidence AS e
                ON e.tenant_id=pe.tenant_id
               AND e.host_inventory_snapshot_evidence_id=pe.host_inventory_snapshot_evidence_id
              JOIN monitoring.monitoring_sync_operation AS o
                ON o.tenant_id=e.tenant_id
               AND o.monitoring_sync_operation_id=e.monitoring_sync_operation_id
             WHERE pe.tenant_id=v_resource.tenant_id
               AND pe.provider_evidence_id=v_resource.latest_provider_evidence_id
               AND pe.monitoring_resource_id=v_resource.monitoring_resource_id
               AND pe.monitoring_source_id=v_resource.monitoring_source_id
               AND pe.source_instance_generation=v_resource.source_instance_generation
               AND pe.provider_external_ref=v_resource.provider_external_ref
               AND pe.observed_at=v_resource.last_confirmed_present_at
               AND e.monitoring_source_id=v_resource.monitoring_source_id
               AND e.source_instance_generation=v_resource.source_instance_generation
               AND e.scope_revision=v_resource.scope_projection_revision
               AND e.host_inventory_poll_generation=v_resource.last_confirmed_present_poll_generation
               AND o.responsibility_kind='host_inventory_sync'
               AND o.state=e.operation_state
               AND o.host_inventory_snapshot_evidence_id=e.host_inventory_snapshot_evidence_id
               AND o.host_inventory_poll_generation=e.host_inventory_poll_generation
               AND o.monitoring_source_id=e.monitoring_source_id
               AND o.source_instance_generation=e.source_instance_generation
               AND o.configuration_revision=e.configuration_revision
               AND o.scope_revision=e.scope_revision
        ) THEN
            RAISE EXCEPTION 'Monitoring resource positive presence requires accepted provider snapshot authority';
        END IF;
    ELSE
        IF NOT EXISTS (
            SELECT 1
              FROM monitoring.monitoring_host_inventory_snapshot_evidence AS e
              JOIN monitoring.monitoring_sync_operation AS o
                ON o.tenant_id=e.tenant_id
               AND o.monitoring_sync_operation_id=e.monitoring_sync_operation_id
             WHERE e.tenant_id=v_resource.tenant_id
               AND e.monitoring_source_id=v_resource.monitoring_source_id
               AND e.source_instance_generation=v_resource.source_instance_generation
               AND e.scope_revision=v_resource.scope_projection_revision
               AND e.snapshot_complete
               AND e.operation_state='succeeded'
               AND e.operational_evidence_state='current'
               AND e.host_inventory_poll_generation=v_resource.removed_poll_generation
               AND e.host_inventory_poll_generation > v_resource.last_confirmed_present_poll_generation
               AND e.observed_at=v_resource.removed_at
               AND o.responsibility_kind='host_inventory_sync'
               AND o.state='succeeded'
               AND o.host_inventory_snapshot_evidence_id=e.host_inventory_snapshot_evidence_id
               AND o.host_inventory_poll_generation=e.host_inventory_poll_generation
               AND o.monitoring_source_id=e.monitoring_source_id
               AND o.source_instance_generation=e.source_instance_generation
               AND o.configuration_revision=e.configuration_revision
               AND o.scope_revision=e.scope_revision
               AND NOT EXISTS (
                   SELECT 1
                     FROM monitoring.monitoring_resource_provider_evidence AS pe
                    WHERE pe.tenant_id=e.tenant_id
                      AND pe.host_inventory_snapshot_evidence_id=e.host_inventory_snapshot_evidence_id
                      AND pe.provider_external_ref=v_resource.provider_external_ref
               )
        ) THEN
            RAISE EXCEPTION 'Monitoring resource removal requires completed newer authoritative negative poll evidence';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS wave4_monitoring_resource_presence_authority_deferred ON monitoring.monitoring_resource;
CREATE CONSTRAINT TRIGGER wave4_monitoring_resource_presence_authority_deferred
AFTER INSERT OR UPDATE ON monitoring.monitoring_resource
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_deferred_monitoring_resource_presence_authority();

COMMIT;
