-- Wave 4 Zabbix initial validation worker persistence.
-- Bounded to validation_and_initial_sync + hostgroup.get evidence only.
-- No host/item/problem ingestion, no retry scheduler, no provider secret storage.

BEGIN;

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN claim_token TEXT NULL,
    ADD COLUMN attempt_count BIGINT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    ADD COLUMN validation_evidence_id TEXT NULL;

CREATE TABLE monitoring.monitoring_source_validation_evidence (
    tenant_id TEXT NOT NULL,
    validation_evidence_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    provider_scope_tenant_binding_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    provider_instance_ref TEXT NOT NULL,
    operational_evidence_state TEXT NOT NULL CHECK (operational_evidence_state IN ('current','incomplete','unavailable')),
    operation_state TEXT NOT NULL CHECK (operation_state IN ('succeeded','reconciliation_required')),
    failure_class TEXT NULL,
    visible_host_group_refs JSONB NOT NULL,
    missing_host_group_refs JSONB NOT NULL,
    egress_decision_ref TEXT NULL,
    credential_generation_ref TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, validation_evidence_id),
    UNIQUE (tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id)
        REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK (tenant_id <> ''),
    CHECK (validation_evidence_id <> ''),
    CHECK (provider_scope_tenant_binding_id <> ''),
    CHECK (provider_instance_ref <> ''),
    CHECK (jsonb_typeof(visible_host_group_refs) = 'array'),
    CHECK (jsonb_typeof(missing_host_group_refs) = 'array'),
    CHECK ((operation_state = 'succeeded') = (operational_evidence_state = 'current')),
    CHECK ((operation_state = 'succeeded') = (failure_class IS NULL))
);

CREATE FUNCTION monitoring.wave4_reject_validation_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    RAISE EXCEPTION 'Monitoring source validation evidence is immutable';
END;
$$;

CREATE TRIGGER wave4_monitoring_source_validation_evidence_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_source_validation_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_validation_evidence_mutation();

CREATE FUNCTION monitoring.claim_zabbix_initial_validation(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
)
RETURNS TABLE (
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
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id = '' OR p_monitoring_sync_operation_id IS NULL OR p_monitoring_sync_operation_id = ''
       OR p_claim_token IS NULL OR p_claim_token = '' OR length(p_claim_token) > 512
       OR p_claim_token <> btrim(p_claim_token) OR p_claim_token ~ '[[:cntrl:]]' THEN
        RAISE EXCEPTION 'invalid initial-validation claim input';
    END IF;

    SELECT o.monitoring_source_id, o.source_instance_generation
      INTO v_source_id, v_generation
      FROM monitoring.monitoring_sync_operation o
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.sync_operation_not_found';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_sync_operation o
         WHERE o.tenant_id = p_tenant_id
           AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id
           AND o.responsibility_kind = 'validation_and_initial_sync'
           AND o.state = 'pending'
           AND o.claim_token IS NULL
           AND o.attempt_count = 0
    ) THEN
        RAISE EXCEPTION 'monitoring.initial_validation_not_claimable';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_source s
         WHERE s.tenant_id = p_tenant_id
           AND s.monitoring_source_id = v_source_id
           AND s.active_source_instance_generation = v_generation
    ) THEN
        RAISE EXCEPTION 'monitoring.initial_validation_stale_generation';
    END IF;

    UPDATE monitoring.monitoring_sync_operation
       SET state = 'running',
           started_at = transaction_timestamp(),
           claim_token = p_claim_token,
           attempt_count = 1
     WHERE tenant_id = p_tenant_id
       AND monitoring_sync_operation_id = p_monitoring_sync_operation_id;

    UPDATE monitoring.monitoring_source s
       SET last_attempt_at = transaction_timestamp(),
           updated_at = transaction_timestamp()
     WHERE s.tenant_id = p_tenant_id AND s.monitoring_source_id = v_source_id;

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
      FROM monitoring.monitoring_sync_operation o
      JOIN monitoring.monitoring_source s
        ON s.tenant_id = o.tenant_id AND s.monitoring_source_id = o.monitoring_source_id
      JOIN monitoring.monitoring_source_generation g
        ON g.tenant_id = o.tenant_id
       AND g.monitoring_source_id = o.monitoring_source_id
       AND g.source_instance_generation = o.source_instance_generation
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id;
END;
$$;

CREATE FUNCTION monitoring.complete_zabbix_initial_validation(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_validation_evidence_id TEXT,
    p_provider_scope_tenant_binding_id TEXT,
    p_provider_instance_ref TEXT,
    p_operational_evidence_state TEXT,
    p_operation_state TEXT,
    p_failure_class TEXT,
    p_visible_host_group_refs JSONB,
    p_missing_host_group_refs JSONB,
    p_egress_decision_ref TEXT,
    p_credential_generation_ref TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
BEGIN
    SELECT o.monitoring_source_id, o.source_instance_generation, o.configuration_revision, o.scope_revision
      INTO v_source_id, v_generation, v_configuration_revision, v_scope_revision
      FROM monitoring.monitoring_sync_operation o
     WHERE o.tenant_id = p_tenant_id
       AND o.monitoring_sync_operation_id = p_monitoring_sync_operation_id
       AND o.state = 'running'
       AND o.claim_token = p_claim_token
       AND o.attempt_count = 1
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.initial_validation_claim_lost';
    END IF;

    IF p_operation_state NOT IN ('succeeded','reconciliation_required')
       OR p_operational_evidence_state NOT IN ('current','incomplete','unavailable')
       OR (p_operation_state = 'succeeded') <> (p_operational_evidence_state = 'current')
       OR (p_operation_state = 'succeeded') <> (p_failure_class IS NULL)
       OR jsonb_typeof(p_visible_host_group_refs) <> 'array'
       OR jsonb_typeof(p_missing_host_group_refs) <> 'array' THEN
        RAISE EXCEPTION 'invalid initial-validation completion input';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_source s
          JOIN monitoring.monitoring_source_generation g
            ON g.tenant_id = s.tenant_id
           AND g.monitoring_source_id = s.monitoring_source_id
           AND g.source_instance_generation = s.active_source_instance_generation
         WHERE s.tenant_id = p_tenant_id
           AND s.monitoring_source_id = v_source_id
           AND s.active_source_instance_generation = v_generation
           AND s.configuration_revision = v_configuration_revision
           AND s.scope_revision = v_scope_revision
           AND s.provider_scope_tenant_binding_id = p_provider_scope_tenant_binding_id
           AND g.provider_instance_ref = p_provider_instance_ref
    ) THEN
        UPDATE monitoring.monitoring_sync_operation
           SET state = 'reconciliation_required',
               completed_at = transaction_timestamp(),
               last_error_class = 'execution.stale_authority',
               validation_evidence_id = NULL
         WHERE tenant_id = p_tenant_id
           AND monitoring_sync_operation_id = p_monitoring_sync_operation_id;
        RETURN;
    END IF;

    INSERT INTO monitoring.monitoring_source_validation_evidence(
        tenant_id, validation_evidence_id, monitoring_sync_operation_id, monitoring_source_id,
        provider_scope_tenant_binding_id, source_instance_generation, configuration_revision,
        scope_revision, provider_instance_ref, operational_evidence_state, operation_state,
        failure_class, visible_host_group_refs, missing_host_group_refs, egress_decision_ref,
        credential_generation_ref
    ) VALUES (
        p_tenant_id, p_validation_evidence_id, p_monitoring_sync_operation_id, v_source_id,
        p_provider_scope_tenant_binding_id, v_generation, v_configuration_revision,
        v_scope_revision, p_provider_instance_ref, p_operational_evidence_state, p_operation_state,
        p_failure_class, p_visible_host_group_refs, p_missing_host_group_refs, p_egress_decision_ref,
        p_credential_generation_ref
    );

    UPDATE monitoring.monitoring_sync_operation
       SET state = p_operation_state,
           completed_at = transaction_timestamp(),
           last_error_class = p_failure_class,
           validation_evidence_id = p_validation_evidence_id
     WHERE tenant_id = p_tenant_id
       AND monitoring_sync_operation_id = p_monitoring_sync_operation_id;

    UPDATE monitoring.monitoring_source
       SET operational_evidence_state = p_operational_evidence_state,
           last_successful_sync_at = CASE WHEN p_operation_state = 'succeeded' THEN transaction_timestamp() ELSE last_successful_sync_at END,
           updated_at = transaction_timestamp()
     WHERE tenant_id = p_tenant_id AND monitoring_source_id = v_source_id;
END;
$$;

COMMENT ON FUNCTION monitoring.claim_zabbix_initial_validation(TEXT, TEXT, TEXT) IS
'Claims the single initial validation operation only while its source generation remains current. This slice does not define retry cadence.';

COMMENT ON FUNCTION monitoring.complete_zabbix_initial_validation(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB, TEXT, TEXT) IS
'Commits hostgroup.get validation evidence only while generation/configuration/scope/binding/provider lineage authority still matches the claim. Stale authority retires its own operation as reconciliation_required without mutating source evidence. Secrets and raw provider payload are excluded.';

COMMIT;
