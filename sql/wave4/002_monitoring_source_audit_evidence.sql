-- Wave 4 Monitoring privileged source-creation audit evidence.
--
-- This migration replaces the foundation-only create function with the final
-- bounded signature for this slice. A committed createSource mutation cannot
-- exist without immutable local accountability evidence in the same transaction.

BEGIN;

DROP FUNCTION monitoring.create_zabbix_source(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB
);

CREATE TABLE monitoring.monitoring_source_audit_evidence (
    tenant_id TEXT NOT NULL,
    audit_evidence_id TEXT NOT NULL,
    actor_principal_id TEXT NOT NULL,
    actor_principal_kind TEXT NOT NULL CHECK (actor_principal_kind IN (
        'human_browser_session',
        'machine_api_principal',
        'internal_service_principal',
        'platform_admin_principal',
        'scheduled/system_process'
    )),
    actor_credential_generation TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action = 'monitoring.source.manage'),
    audit_class TEXT NOT NULL CHECK (audit_class = 'privileged'),
    resource_type TEXT NOT NULL CHECK (resource_type = 'monitoring_source'),
    monitoring_source_id TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome = 'local_creation_committed'),
    authorization_decision_ref TEXT NOT NULL,
    request_correlation_id TEXT NOT NULL,
    safe_summary JSONB NOT NULL CHECK (
        safe_summary = '{"mutation":"create","provider_profile":"zabbix"}'::jsonb
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, audit_evidence_id),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (tenant_id <> ''),
    CHECK (audit_evidence_id <> ''),
    CHECK (actor_principal_id <> ''),
    CHECK (actor_credential_generation <> ''),
    CHECK (authorization_decision_ref <> ''),
    CHECK (request_correlation_id <> '')
);

COMMENT ON TABLE monitoring.monitoring_source_audit_evidence IS
'Append-only local accountability evidence for privileged Monitoring source mutations. It is source-domain origin evidence, not a mutable delivery queue and not the Compliance projection itself.';

ALTER TABLE monitoring.monitoring_source_create_idempotency
    ADD COLUMN audit_evidence_id TEXT NOT NULL;

ALTER TABLE monitoring.monitoring_source_create_idempotency
    ADD CONSTRAINT monitoring_source_create_audit_evidence_fk
    FOREIGN KEY (tenant_id, audit_evidence_id)
    REFERENCES monitoring.monitoring_source_audit_evidence(tenant_id, audit_evidence_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION monitoring.wave4_reject_audit_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    RAISE EXCEPTION 'Monitoring source audit evidence is immutable';
END;
$$;

CREATE TRIGGER wave4_monitoring_source_audit_evidence_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_source_audit_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_audit_evidence_mutation();

CREATE FUNCTION monitoring.create_zabbix_source(
    p_tenant_id TEXT,
    p_idempotency_key TEXT,
    p_request_fingerprint TEXT,
    p_monitoring_source_id TEXT,
    p_source_instance_generation TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_audit_evidence_id TEXT,
    p_actor_principal_id TEXT,
    p_actor_principal_kind TEXT,
    p_actor_credential_generation TEXT,
    p_authorization_decision_ref TEXT,
    p_request_correlation_id TEXT,
    p_display_name TEXT,
    p_provider_base_url TEXT,
    p_credential_binding_ref TEXT,
    p_configured_provider_scope JSONB
)
RETURNS TABLE (
    monitoring_source_id TEXT,
    monitoring_sync_operation_id TEXT,
    idempotency_state TEXT,
    replayed BOOLEAN
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    existing_fingerprint TEXT;
    existing_source_id TEXT;
    existing_operation_id TEXT;
    existing_state TEXT;
    inserted_count BIGINT := 0;
    scope_count BIGINT;
    scope_distinct_count BIGINT;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id = '' OR length(p_tenant_id) > 256
       OR p_tenant_id ~ '[[:cntrl:]]' OR p_tenant_id <> btrim(p_tenant_id)
       OR p_idempotency_key IS NULL OR p_idempotency_key = '' OR length(p_idempotency_key) > 512
       OR p_idempotency_key ~ '[[:cntrl:]]' OR p_idempotency_key <> btrim(p_idempotency_key)
       OR p_request_fingerprint IS NULL OR p_request_fingerprint !~ '^[0-9a-f]{64}$'
       OR p_monitoring_source_id IS NULL OR p_monitoring_source_id = '' OR length(p_monitoring_source_id) > 512
       OR p_monitoring_source_id ~ '[[:cntrl:]]' OR p_monitoring_source_id <> btrim(p_monitoring_source_id)
       OR p_source_instance_generation IS NULL OR p_source_instance_generation = '' OR length(p_source_instance_generation) > 512
       OR p_source_instance_generation ~ '[[:cntrl:]]' OR p_source_instance_generation <> btrim(p_source_instance_generation)
       OR p_monitoring_sync_operation_id IS NULL OR p_monitoring_sync_operation_id = '' OR length(p_monitoring_sync_operation_id) > 512
       OR p_monitoring_sync_operation_id ~ '[[:cntrl:]]' OR p_monitoring_sync_operation_id <> btrim(p_monitoring_sync_operation_id)
       OR p_audit_evidence_id IS NULL OR p_audit_evidence_id = '' OR length(p_audit_evidence_id) > 512
       OR p_audit_evidence_id ~ '[[:cntrl:]]' OR p_audit_evidence_id <> btrim(p_audit_evidence_id)
       OR p_actor_principal_id IS NULL OR p_actor_principal_id = '' OR length(p_actor_principal_id) > 256
       OR p_actor_principal_id ~ '[[:cntrl:]]' OR p_actor_principal_id <> btrim(p_actor_principal_id)
       OR p_actor_principal_kind NOT IN (
            'human_browser_session', 'machine_api_principal', 'internal_service_principal',
            'platform_admin_principal', 'scheduled/system_process'
       )
       OR p_actor_credential_generation IS NULL OR p_actor_credential_generation = '' OR length(p_actor_credential_generation) > 256
       OR p_actor_credential_generation ~ '[[:cntrl:]]' OR p_actor_credential_generation <> btrim(p_actor_credential_generation)
       OR p_authorization_decision_ref IS NULL OR p_authorization_decision_ref = '' OR length(p_authorization_decision_ref) > 512
       OR p_authorization_decision_ref ~ '[[:cntrl:]]' OR p_authorization_decision_ref <> btrim(p_authorization_decision_ref)
       OR p_request_correlation_id IS NULL OR p_request_correlation_id = '' OR length(p_request_correlation_id) > 512
       OR p_request_correlation_id ~ '[[:cntrl:]]' OR p_request_correlation_id <> btrim(p_request_correlation_id)
       OR p_display_name IS NULL OR p_display_name = '' OR length(p_display_name) > 512
       OR p_display_name ~ '[[:cntrl:]]' OR p_display_name <> btrim(p_display_name)
       OR p_credential_binding_ref IS NULL OR p_credential_binding_ref = '' OR length(p_credential_binding_ref) > 512
       OR p_credential_binding_ref ~ '[[:cntrl:]]' OR p_credential_binding_ref <> btrim(p_credential_binding_ref)
       OR p_provider_base_url IS NULL OR p_provider_base_url = '' OR length(p_provider_base_url) > 2048
       OR p_provider_base_url NOT LIKE 'https://%'
       OR position('?' IN p_provider_base_url) > 0
       OR position('#' IN p_provider_base_url) > 0
       OR position('@' IN p_provider_base_url) > 0
       OR position(E'\\' IN p_provider_base_url) > 0
       OR p_provider_base_url ~ '[[:cntrl:][:space:]]'
       OR p_configured_provider_scope IS NULL
       OR jsonb_typeof(p_configured_provider_scope) <> 'object'
       OR NOT (p_configured_provider_scope ? 'host_group_refs')
       OR p_configured_provider_scope - 'host_group_refs' <> '{}'::jsonb
       OR jsonb_typeof(p_configured_provider_scope->'host_group_refs') <> 'array' THEN
        RAISE EXCEPTION 'invalid bounded create-source input';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements(p_configured_provider_scope->'host_group_refs') AS element(value)
         WHERE jsonb_typeof(value) <> 'string'
            OR value #>> '{}' = ''
            OR length(value #>> '{}') > 256
            OR value #>> '{}' <> btrim(value #>> '{}')
            OR value #>> '{}' ~ '[[:cntrl:]]'
    ) THEN
        RAISE EXCEPTION 'invalid configured provider scope';
    END IF;

    SELECT count(*), count(DISTINCT value #>> '{}')
      INTO scope_count, scope_distinct_count
      FROM jsonb_array_elements(p_configured_provider_scope->'host_group_refs') AS element(value);
    IF scope_count > 256 OR scope_count <> scope_distinct_count THEN
        RAISE EXCEPTION 'invalid configured provider scope';
    END IF;

    INSERT INTO monitoring.monitoring_source_create_idempotency(
        tenant_id, idempotency_key, request_fingerprint,
        monitoring_source_id, monitoring_sync_operation_id, audit_evidence_id, state
    ) VALUES (
        p_tenant_id, p_idempotency_key, p_request_fingerprint,
        p_monitoring_source_id, p_monitoring_sync_operation_id, p_audit_evidence_id, 'in_progress'
    )
    ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;

    IF inserted_count = 0 THEN
        SELECT i.request_fingerprint, i.monitoring_source_id,
               i.monitoring_sync_operation_id, i.state
          INTO existing_fingerprint, existing_source_id,
               existing_operation_id, existing_state
          FROM monitoring.monitoring_source_create_idempotency AS i
         WHERE i.tenant_id = p_tenant_id AND i.idempotency_key = p_idempotency_key
         FOR UPDATE;

        IF existing_fingerprint IS DISTINCT FROM p_request_fingerprint THEN
            RAISE EXCEPTION 'idempotency.key_reused';
        END IF;

        RETURN QUERY SELECT existing_source_id, existing_operation_id, existing_state, TRUE;
        RETURN;
    END IF;

    INSERT INTO monitoring.monitoring_source(
        tenant_id, monitoring_source_id, provider_profile,
        active_source_instance_generation, configuration_revision, scope_revision,
        display_name, credential_binding_ref, configured_provider_scope,
        operational_evidence_state, last_sync_operation_id
    ) VALUES (
        p_tenant_id, p_monitoring_source_id, 'zabbix',
        p_source_instance_generation, 1, 1,
        p_display_name, p_credential_binding_ref, p_configured_provider_scope,
        'reconciliation_required', p_monitoring_sync_operation_id
    );

    INSERT INTO monitoring.monitoring_source_generation(
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_profile, provider_base_url
    ) VALUES (
        p_tenant_id, p_monitoring_source_id, p_source_instance_generation,
        'zabbix', p_provider_base_url
    );

    INSERT INTO monitoring.monitoring_sync_operation(
        tenant_id, monitoring_sync_operation_id, monitoring_source_id,
        source_instance_generation, configuration_revision, scope_revision,
        responsibility_kind, state
    ) VALUES (
        p_tenant_id, p_monitoring_sync_operation_id, p_monitoring_source_id,
        p_source_instance_generation, 1, 1,
        'validation_and_initial_sync', 'pending'
    );

    INSERT INTO monitoring.monitoring_source_audit_evidence(
        tenant_id, audit_evidence_id, actor_principal_id, actor_principal_kind,
        actor_credential_generation, action, audit_class, resource_type,
        monitoring_source_id, outcome, authorization_decision_ref,
        request_correlation_id, safe_summary
    ) VALUES (
        p_tenant_id, p_audit_evidence_id, p_actor_principal_id, p_actor_principal_kind,
        p_actor_credential_generation, 'monitoring.source.manage', 'privileged',
        'monitoring_source', p_monitoring_source_id, 'local_creation_committed',
        p_authorization_decision_ref, p_request_correlation_id,
        '{"mutation":"create","provider_profile":"zabbix"}'::jsonb
    );

    UPDATE monitoring.monitoring_source_create_idempotency AS i
       SET state = 'completed', completed_at = transaction_timestamp()
     WHERE i.tenant_id = p_tenant_id AND i.idempotency_key = p_idempotency_key;

    RETURN QUERY SELECT p_monitoring_source_id, p_monitoring_sync_operation_id, 'completed'::TEXT, FALSE;
END;
$$;

COMMENT ON FUNCTION monitoring.create_zabbix_source(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB
) IS
'Atomic create-or-observe transaction for monitoring.createSource. A new logical mutation commits source, generation, idempotency, durable sync responsibility and immutable privileged audit evidence together. It performs no provider network call.';

COMMIT;
