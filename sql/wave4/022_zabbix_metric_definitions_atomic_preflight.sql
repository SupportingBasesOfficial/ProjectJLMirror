-- Wave 4 metric-definition atomic preflight hardening.
-- A successful item snapshot is validated in full before any canonical definition or
-- binding mutation occurs. Type drift or invalid host association therefore fails
-- closed without partially applying earlier items from the same snapshot.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_metric_definitions(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_metric_definition_snapshot_evidence_id TEXT,
    p_operational_evidence_state TEXT,
    p_operation_state TEXT,
    p_failure_class TEXT,
    p_egress_decision_ref TEXT,
    p_credential_generation_ref TEXT,
    p_snapshot_complete BOOLEAN,
    p_items JSONB
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_epoch BIGINT;
    v_poll_generation BIGINT;
    v_source_epoch BIGINT;
    v_source_poll BIGINT;
    v_item JSONB;
    v_resource_id TEXT;
    v_metric_id TEXT;
    v_existing_kind TEXT;
    v_kind TEXT;
    v_native_type TEXT;
    v_itemid TEXT;
    v_hostid TEXT;
    v_name TEXT;
    v_key TEXT;
    v_unit TEXT;
    v_provider_state TEXT;
    v_seen TEXT[] := ARRAY[]::TEXT[];
BEGIN
    IF jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) > 200000 THEN
        RAISE EXCEPTION 'monitoring.metric_definition_invalid_item_payload';
    END IF;
    IF (p_operation_state='succeeded') IS DISTINCT FROM p_snapshot_complete
       OR (p_operation_state='succeeded') IS DISTINCT FROM (p_operational_evidence_state='current')
       OR (p_operation_state='succeeded') IS DISTINCT FROM (p_failure_class IS NULL) THEN
        RAISE EXCEPTION 'monitoring.metric_definition_invalid_completion_shape';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision,
           o.item_definition_poll_epoch,o.item_definition_poll_generation,
           s.item_definition_poll_epoch,s.item_definition_poll_generation
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision,
           v_poll_epoch,v_poll_generation,v_source_epoch,v_source_poll
      FROM monitoring.monitoring_sync_operation o
      JOIN monitoring.monitoring_source s
        ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_definition_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE OF o,s;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_completion_not_claimed';
    END IF;

    IF v_source_epoch IS DISTINCT FROM v_poll_epoch OR v_source_poll IS DISTINCT FROM v_poll_generation THEN
        p_operation_state := 'reconciliation_required';
        p_operational_evidence_state := 'reconciliation_required';
        p_failure_class := 'execution.superseded_item_poll_authority';
        p_snapshot_complete := FALSE;
    END IF;

    -- PRECHECK: parse/validate the whole successful snapshot, resolve every host and
    -- detect any existing binding whose native type would change canonical value_kind.
    IF p_operation_state='succeeded' THEN
        FOR v_item IN SELECT value FROM jsonb_array_elements(p_items)
        LOOP
            v_itemid := v_item->>'itemid';
            v_hostid := v_item->>'hostid';
            v_name := v_item->>'name';
            v_key := v_item->>'key';
            v_unit := COALESCE(v_item->>'unit','');
            v_native_type := v_item->>'native_value_type';
            v_provider_state := v_item->>'operational_state';

            IF v_itemid IS NULL OR v_itemid='' OR length(v_itemid)>256
               OR v_hostid IS NULL OR v_hostid='' OR length(v_hostid)>256
               OR v_name IS NULL OR v_name='' OR length(v_name)>1024
               OR v_key IS NULL OR v_key='' OR length(v_key)>2048
               OR length(v_unit)>255
               OR v_native_type NOT IN ('float','unsigned','character','text','log')
               OR v_provider_state NOT IN ('enabled','disabled','unsupported') THEN
                RAISE EXCEPTION 'monitoring.metric_definition_invalid_item_evidence';
            END IF;
            IF v_itemid=ANY(v_seen) THEN
                RAISE EXCEPTION 'monitoring.metric_definition_duplicate_itemid';
            END IF;
            v_seen := array_append(v_seen,v_itemid);

            SELECT r.monitoring_resource_id INTO v_resource_id
              FROM monitoring.monitoring_resource r
             WHERE r.tenant_id=p_tenant_id
               AND r.monitoring_source_id=v_source_id
               AND r.source_instance_generation=v_generation
               AND r.provider_external_ref=v_hostid
               AND r.resource_kind='host'
               AND r.presence_state='present'
               AND r.presence_evidence_state='current'
               AND r.scope_state='in_scope'
               AND r.scope_evidence_state='current'
               AND r.scope_projection_revision=v_scope_revision;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'monitoring.metric_definition_host_association_invalid';
            END IF;

            v_kind := CASE v_native_type
                WHEN 'float' THEN 'number'
                WHEN 'unsigned' THEN 'integer'
                WHEN 'character' THEN 'string'
                WHEN 'text' THEN 'text'
                WHEN 'log' THEN 'log'
            END;

            SELECT d.value_kind INTO v_existing_kind
              FROM monitoring.metric_definition_provider_binding b
              JOIN monitoring.metric_definition d
                ON d.tenant_id=b.tenant_id AND d.metric_definition_id=b.metric_definition_id
             WHERE b.tenant_id=p_tenant_id
               AND b.monitoring_source_id=v_source_id
               AND b.source_instance_generation=v_generation
               AND b.provider_external_ref=v_itemid;
            IF FOUND AND v_existing_kind IS DISTINCT FROM v_kind THEN
                p_operation_state := 'reconciliation_required';
                p_operational_evidence_state := 'reconciliation_required';
                p_failure_class := 'provider.value_kind_drift';
                p_snapshot_complete := FALSE;
                EXIT;
            END IF;
        END LOOP;
    END IF;

    -- If preflight degraded the snapshot, persist only operation/snapshot evidence.
    -- No definition/binding/provider-evidence mutation from this snapshot is accepted.
    IF p_operation_state='succeeded' THEN
        v_seen := ARRAY[]::TEXT[];
        FOR v_item IN SELECT value FROM jsonb_array_elements(p_items)
        LOOP
            v_itemid := v_item->>'itemid';
            v_hostid := v_item->>'hostid';
            v_name := v_item->>'name';
            v_key := v_item->>'key';
            v_unit := COALESCE(v_item->>'unit','');
            v_native_type := v_item->>'native_value_type';
            v_provider_state := v_item->>'operational_state';
            v_seen := array_append(v_seen,v_itemid);

            SELECT r.monitoring_resource_id INTO STRICT v_resource_id
              FROM monitoring.monitoring_resource r
             WHERE r.tenant_id=p_tenant_id
               AND r.monitoring_source_id=v_source_id
               AND r.source_instance_generation=v_generation
               AND r.provider_external_ref=v_hostid
               AND r.resource_kind='host'
               AND r.presence_state='present'
               AND r.presence_evidence_state='current'
               AND r.scope_state='in_scope'
               AND r.scope_evidence_state='current'
               AND r.scope_projection_revision=v_scope_revision;

            v_kind := CASE v_native_type
                WHEN 'float' THEN 'number'
                WHEN 'unsigned' THEN 'integer'
                WHEN 'character' THEN 'string'
                WHEN 'text' THEN 'text'
                WHEN 'log' THEN 'log'
            END;

            SELECT b.metric_definition_id INTO v_metric_id
              FROM monitoring.metric_definition_provider_binding b
             WHERE b.tenant_id=p_tenant_id
               AND b.monitoring_source_id=v_source_id
               AND b.source_instance_generation=v_generation
               AND b.provider_external_ref=v_itemid;

            IF NOT FOUND THEN
                v_metric_id := 'mon-metric-' || encode(sha256(convert_to(
                    p_tenant_id || ':' || v_source_id || ':' || v_generation || ':' || v_itemid,'UTF8'
                )),'hex');
                INSERT INTO monitoring.metric_definition(
                    tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,
                    source_instance_generation,name,value_kind,unit,scope_state,
                    scope_projection_revision,scope_evidence_state,definition_state,
                    definition_evidence_state,last_confirmed_present_poll_epoch,
                    last_confirmed_present_poll_generation
                ) VALUES (
                    p_tenant_id,v_metric_id,v_resource_id,v_source_id,v_generation,v_name,v_kind,v_unit,
                    'in_scope',v_scope_revision,'current','active','current',v_poll_epoch,v_poll_generation
                );
                INSERT INTO monitoring.metric_definition_provider_binding(
                    tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,
                    source_instance_generation,provider_profile,provider_object_kind,provider_external_ref,
                    provider_host_ref,provider_key,native_value_type,provider_operational_state,evidence_state
                ) VALUES (
                    p_tenant_id,v_metric_id,v_resource_id,v_source_id,v_generation,'zabbix','zabbix_item',
                    v_itemid,v_hostid,v_key,v_native_type,v_provider_state,'current'
                );
            ELSE
                UPDATE monitoring.metric_definition
                   SET name=v_name,unit=v_unit,scope_state='in_scope',
                       scope_projection_revision=v_scope_revision,scope_evidence_state='current',
                       definition_state='active',definition_evidence_state='current',
                       retired_poll_epoch=NULL,retired_poll_generation=NULL,
                       last_confirmed_present_poll_epoch=v_poll_epoch,
                       last_confirmed_present_poll_generation=v_poll_generation,
                       updated_at=transaction_timestamp()
                 WHERE tenant_id=p_tenant_id AND metric_definition_id=v_metric_id;
                UPDATE monitoring.metric_definition_provider_binding
                   SET provider_key=v_key,provider_operational_state=v_provider_state,
                       evidence_state='current',updated_at=transaction_timestamp()
                 WHERE tenant_id=p_tenant_id AND metric_definition_id=v_metric_id;
            END IF;

            INSERT INTO monitoring.monitoring_metric_definition_provider_evidence(
                tenant_id,provider_evidence_id,metric_definition_snapshot_evidence_id,
                metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
                provider_external_ref,provider_host_ref,evidence_fingerprint,normalized_evidence
            ) VALUES (
                p_tenant_id,
                p_metric_definition_snapshot_evidence_id || ':' || v_itemid,
                p_metric_definition_snapshot_evidence_id,v_metric_id,v_resource_id,v_source_id,v_generation,
                v_itemid,v_hostid,encode(sha256(convert_to(v_item::text,'UTF8')),'hex'),v_item
            );
        END LOOP;
    END IF;

    INSERT INTO monitoring.monitoring_metric_definition_snapshot_evidence(
        tenant_id,metric_definition_snapshot_evidence_id,monitoring_sync_operation_id,
        monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,
        item_definition_poll_epoch,item_definition_poll_generation,snapshot_complete,item_count,
        operational_evidence_state,operation_state,failure_class,egress_decision_ref,credential_generation_ref
    ) VALUES (
        p_tenant_id,p_metric_definition_snapshot_evidence_id,p_monitoring_sync_operation_id,
        v_source_id,v_generation,v_configuration_revision,v_scope_revision,v_poll_epoch,v_poll_generation,
        p_snapshot_complete,jsonb_array_length(p_items),p_operational_evidence_state,p_operation_state,
        p_failure_class,p_egress_decision_ref,p_credential_generation_ref
    );

    IF p_operation_state='succeeded' THEN
        PERFORM monitoring.wave4_retire_missing_metric_definitions(
            p_tenant_id,v_source_id,v_generation,v_scope_revision,v_poll_epoch,v_poll_generation,v_seen
        );
    END IF;

    UPDATE monitoring.monitoring_sync_operation
       SET state=p_operation_state,completed_at=transaction_timestamp(),last_error_class=p_failure_class,
           metric_definition_snapshot_evidence_id=p_metric_definition_snapshot_evidence_id,
           claim_token=NULL
     WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN p_operation_state;
END;
$$;
ALTER FUNCTION monitoring.complete_zabbix_metric_definitions(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB)
    OWNER TO jlmirror_wave4_metric_definition_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB)
    TO jlmirror_wave4_metric_definition_invoker;

COMMIT;
