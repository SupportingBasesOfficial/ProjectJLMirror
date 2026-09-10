-- Wave 4 host-inventory persistence defense in depth.
-- PostgreSQL independently enforces bounded provider evidence and scope membership.

BEGIN;

CREATE FUNCTION monitoring.wave4_is_bounded_zabbix_host_evidence(p_evidence JSONB)
RETURNS BOOLEAN
LANGUAGE plpgsql IMMUTABLE STRICT
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    row JSONB;
    inventory_key TEXT;
    inventory_value TEXT;
BEGIN
    IF jsonb_typeof(p_evidence) <> 'object'
       OR p_evidence - ARRAY['technical_name','display_name','inventory','interfaces','groups','templates','tags']::TEXT[] <> '{}'::jsonb
       OR NOT (p_evidence ?& ARRAY['technical_name','display_name','inventory','interfaces','groups','templates','tags'])
       OR jsonb_typeof(p_evidence->'technical_name') <> 'string'
       OR jsonb_typeof(p_evidence->'display_name') <> 'string'
       OR p_evidence->>'technical_name' = '' OR length(p_evidence->>'technical_name') > 512
       OR p_evidence->>'display_name' = '' OR length(p_evidence->>'display_name') > 512
       OR p_evidence->>'technical_name' <> btrim(p_evidence->>'technical_name')
       OR p_evidence->>'display_name' <> btrim(p_evidence->>'display_name')
       OR p_evidence->>'technical_name' ~ '[[:cntrl:]]'
       OR p_evidence->>'display_name' ~ '[[:cntrl:]]'
       OR jsonb_typeof(p_evidence->'inventory') <> 'object'
       OR jsonb_typeof(p_evidence->'interfaces') <> 'array'
       OR jsonb_typeof(p_evidence->'groups') <> 'array'
       OR jsonb_typeof(p_evidence->'templates') <> 'array'
       OR jsonb_typeof(p_evidence->'tags') <> 'array'
       OR jsonb_array_length(p_evidence->'interfaces') > 32
       OR jsonb_array_length(p_evidence->'groups') > 256
       OR jsonb_array_length(p_evidence->'templates') > 256
       OR jsonb_array_length(p_evidence->'tags') > 128
       OR octet_length(p_evidence::text) > 65536 THEN
        RETURN FALSE;
    END IF;

    IF p_evidence->'inventory' - ARRAY[
        'device_type','device_type_full','os','os_full','vendor','model',
        'serial_primary','serial_secondary','asset_tag','hardware','software','location'
    ]::TEXT[] <> '{}'::jsonb THEN
        RETURN FALSE;
    END IF;
    FOR inventory_key IN SELECT jsonb_object_keys(p_evidence->'inventory') LOOP
        IF jsonb_typeof(p_evidence->'inventory'->inventory_key) <> 'string' THEN
            RETURN FALSE;
        END IF;
        inventory_value := p_evidence->'inventory'->>inventory_key;
        IF inventory_value = ''
           OR inventory_value <> btrim(inventory_value)
           OR inventory_value ~ '[[:cntrl:]]' THEN
            RETURN FALSE;
        END IF;
        IF inventory_key IN ('device_type_full','os_full','hardware','software') AND length(inventory_value) > 2048 THEN
            RETURN FALSE;
        ELSIF inventory_key = 'location' AND length(inventory_value) > 1024 THEN
            RETURN FALSE;
        ELSIF inventory_key NOT IN ('device_type_full','os_full','hardware','software','location') AND length(inventory_value) > 512 THEN
            RETURN FALSE;
        END IF;
    END LOOP;

    FOR row IN SELECT value FROM jsonb_array_elements(p_evidence->'interfaces') LOOP
        IF jsonb_typeof(row) <> 'object'
           OR row - ARRAY['interfaceid','interface_type','main','use_ip','ip','dns','port']::TEXT[] <> '{}'::jsonb
           OR NOT (row ?& ARRAY['interfaceid','interface_type','main','use_ip'])
           OR jsonb_typeof(row->'interfaceid') <> 'string'
           OR jsonb_typeof(row->'interface_type') <> 'string'
           OR jsonb_typeof(row->'main') <> 'boolean'
           OR jsonb_typeof(row->'use_ip') <> 'boolean'
           OR row->>'interfaceid' = '' OR length(row->>'interfaceid') > 256
           OR row->>'interface_type' NOT IN ('agent','snmp','ipmi','jmx','unknown') THEN
            RETURN FALSE;
        END IF;
        IF (row ? 'ip') AND (jsonb_typeof(row->'ip') <> 'string' OR row->>'ip' = '' OR length(row->>'ip') > 255 OR row->>'ip' ~ '[[:cntrl:]]') THEN RETURN FALSE; END IF;
        IF (row ? 'dns') AND (jsonb_typeof(row->'dns') <> 'string' OR row->>'dns' = '' OR length(row->>'dns') > 255 OR row->>'dns' ~ '[[:cntrl:]]') THEN RETURN FALSE; END IF;
        IF (row ? 'port') AND (jsonb_typeof(row->'port') <> 'string' OR row->>'port' = '' OR length(row->>'port') > 32 OR row->>'port' ~ '[[:cntrl:]]') THEN RETURN FALSE; END IF;
    END LOOP;

    FOR row IN SELECT value FROM jsonb_array_elements(p_evidence->'groups') LOOP
        IF jsonb_typeof(row) <> 'object'
           OR row - ARRAY['ref','name']::TEXT[] <> '{}'::jsonb
           OR NOT (row ? 'ref') OR jsonb_typeof(row->'ref') <> 'string'
           OR row->>'ref' = '' OR length(row->>'ref') > 256
           OR row->>'ref' <> btrim(row->>'ref') OR row->>'ref' ~ '[[:cntrl:]]'
           OR ((row ? 'name') AND (jsonb_typeof(row->'name') <> 'string' OR row->>'name' = '' OR length(row->>'name') > 512 OR row->>'name' <> btrim(row->>'name') OR row->>'name' ~ '[[:cntrl:]]')) THEN
            RETURN FALSE;
        END IF;
    END LOOP;
    IF (SELECT count(*) FROM jsonb_array_elements(p_evidence->'groups')) <> (SELECT count(DISTINCT value->>'ref') FROM jsonb_array_elements(p_evidence->'groups')) THEN RETURN FALSE; END IF;

    FOR row IN SELECT value FROM jsonb_array_elements(p_evidence->'templates') LOOP
        IF jsonb_typeof(row) <> 'object'
           OR row - ARRAY['ref','name']::TEXT[] <> '{}'::jsonb
           OR NOT (row ? 'ref') OR jsonb_typeof(row->'ref') <> 'string'
           OR row->>'ref' = '' OR length(row->>'ref') > 256
           OR row->>'ref' <> btrim(row->>'ref') OR row->>'ref' ~ '[[:cntrl:]]'
           OR ((row ? 'name') AND (jsonb_typeof(row->'name') <> 'string' OR row->>'name' = '' OR length(row->>'name') > 512 OR row->>'name' <> btrim(row->>'name') OR row->>'name' ~ '[[:cntrl:]]')) THEN
            RETURN FALSE;
        END IF;
    END LOOP;
    IF (SELECT count(*) FROM jsonb_array_elements(p_evidence->'templates')) <> (SELECT count(DISTINCT value->>'ref') FROM jsonb_array_elements(p_evidence->'templates')) THEN RETURN FALSE; END IF;

    FOR row IN SELECT value FROM jsonb_array_elements(p_evidence->'tags') LOOP
        IF jsonb_typeof(row) <> 'object'
           OR row - ARRAY['tag','value']::TEXT[] <> '{}'::jsonb
           OR NOT (row ?& ARRAY['tag','value'])
           OR jsonb_typeof(row->'tag') <> 'string' OR jsonb_typeof(row->'value') <> 'string'
           OR row->>'tag' = '' OR length(row->>'tag') > 255
           OR length(row->>'value') > 1024
           OR row->>'tag' ~ '[[:cntrl:]]' OR row->>'value' ~ '[[:cntrl:]]' THEN
            RETURN FALSE;
        END IF;
    END LOOP;
    IF (SELECT count(*) FROM jsonb_array_elements(p_evidence->'tags')) <> (SELECT count(DISTINCT (value->>'tag') || E'\x1f' || (value->>'value')) FROM jsonb_array_elements(p_evidence->'tags')) THEN RETURN FALSE; END IF;

    RETURN TRUE;
END;
$$;

ALTER TABLE monitoring.monitoring_resource_provider_evidence
    ADD CONSTRAINT monitoring_resource_provider_evidence_bounded_shape
    CHECK (monitoring.wave4_is_bounded_zabbix_host_evidence(normalized_evidence));

CREATE FUNCTION monitoring.wave4_guard_host_provider_evidence_insert()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_scope JSONB;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_resource r
          JOIN monitoring.monitoring_host_inventory_snapshot_evidence e
            ON e.tenant_id=NEW.tenant_id
           AND e.host_inventory_snapshot_evidence_id=NEW.host_inventory_snapshot_evidence_id
         WHERE r.tenant_id=NEW.tenant_id
           AND r.monitoring_resource_id=NEW.monitoring_resource_id
           AND r.monitoring_source_id=NEW.monitoring_source_id
           AND r.source_instance_generation=NEW.source_instance_generation
           AND r.provider_external_ref=NEW.provider_external_ref
           AND e.monitoring_source_id=NEW.monitoring_source_id
           AND e.source_instance_generation=NEW.source_instance_generation
    ) THEN
        RAISE EXCEPTION 'host provider evidence lineage mismatch';
    END IF;

    SELECT s.configured_provider_scope INTO v_scope
      FROM monitoring.monitoring_source s
      JOIN monitoring.monitoring_host_inventory_snapshot_evidence e
        ON e.tenant_id=s.tenant_id
       AND e.monitoring_source_id=s.monitoring_source_id
       AND e.host_inventory_snapshot_evidence_id=NEW.host_inventory_snapshot_evidence_id
     WHERE s.tenant_id=NEW.tenant_id
       AND s.monitoring_source_id=NEW.monitoring_source_id
       AND s.active_source_instance_generation=NEW.source_instance_generation
       AND s.scope_revision=e.scope_revision;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'host provider evidence stale scope authority';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM jsonb_array_elements(NEW.normalized_evidence->'groups') g
          JOIN jsonb_array_elements(v_scope->'host_group_refs') configured
            ON g->>'ref'=configured #>> '{}'
    ) THEN
        RAISE EXCEPTION 'host provider evidence lacks configured-scope membership';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_host_provider_evidence_insert_guard
BEFORE INSERT ON monitoring.monitoring_resource_provider_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_host_provider_evidence_insert();

CREATE OR REPLACE FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(
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
    SELECT s.active_source_instance_generation, s.configuration_revision, s.scope_revision
      INTO v_generation, v_configuration_revision, v_scope_revision
      FROM monitoring.monitoring_source s
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=p_monitoring_source_id
       AND EXISTS (
           SELECT 1 FROM monitoring.monitoring_source_validation_evidence v
            WHERE v.tenant_id=s.tenant_id
              AND v.monitoring_source_id=s.monitoring_source_id
              AND v.source_instance_generation=s.active_source_instance_generation
              AND v.configuration_revision=s.configuration_revision
              AND v.scope_revision=s.scope_revision
              AND v.operation_state='succeeded'
              AND v.operational_evidence_state='current'
       )
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.host_inventory_source_not_validated_current'; END IF;
    INSERT INTO monitoring.monitoring_sync_operation(
        tenant_id, monitoring_sync_operation_id, monitoring_source_id,
        source_instance_generation, configuration_revision, scope_revision,
        responsibility_kind, state
    ) VALUES (p_tenant_id,p_monitoring_sync_operation_id,p_monitoring_source_id,
              v_generation,v_configuration_revision,v_scope_revision,'host_inventory_sync','pending');
    UPDATE monitoring.monitoring_source SET last_sync_operation_id=p_monitoring_sync_operation_id,
           updated_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=p_monitoring_source_id;
END;
$$;

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
DECLARE v_source_id TEXT; v_generation TEXT; v_configuration_revision BIGINT; v_scope_revision BIGINT;
BEGIN
    IF p_claim_token IS NULL OR p_claim_token='' OR length(p_claim_token)>512 OR p_claim_token<>btrim(p_claim_token) OR p_claim_token~'[[:cntrl:]]' THEN
        RAISE EXCEPTION 'invalid host inventory claim token';
    END IF;
    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation o
     WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='host_inventory_sync' AND o.state='pending' AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.host_inventory_not_claimable'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_source s
         WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=v_source_id
           AND s.active_source_instance_generation=v_generation
           AND s.configuration_revision=v_configuration_revision AND s.scope_revision=v_scope_revision
           AND EXISTS (
               SELECT 1 FROM monitoring.monitoring_source_validation_evidence v
                WHERE v.tenant_id=s.tenant_id AND v.monitoring_source_id=s.monitoring_source_id
                  AND v.source_instance_generation=v_generation
                  AND v.configuration_revision=v_configuration_revision AND v.scope_revision=v_scope_revision
                  AND v.operation_state='succeeded' AND v.operational_evidence_state='current'
           )
    ) THEN RAISE EXCEPTION 'monitoring.host_inventory_stale_authority'; END IF;
    UPDATE monitoring.monitoring_sync_operation SET state='running',claim_token=p_claim_token,
           attempt_count=attempt_count+1,started_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;
    UPDATE monitoring.monitoring_source SET last_attempt_at=transaction_timestamp(),updated_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=v_source_id;
    RETURN QUERY SELECT s.monitoring_source_id,s.provider_scope_tenant_binding_id,
           o.source_instance_generation,o.configuration_revision,o.scope_revision,
           g.provider_instance_ref,g.provider_base_url,s.credential_binding_ref,s.configured_provider_scope
      FROM monitoring.monitoring_sync_operation o
      JOIN monitoring.monitoring_source s ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id
      JOIN monitoring.monitoring_source_generation g ON g.tenant_id=o.tenant_id AND g.monitoring_source_id=o.monitoring_source_id AND g.source_instance_generation=o.source_instance_generation
     WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
END;
$$;

COMMIT;
