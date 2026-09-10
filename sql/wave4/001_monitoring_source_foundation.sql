-- Wave 4 Monitoring source foundation, successor-compatible with ADR-022.
-- Implementation authority remains wave4.monitoring-zabbix.vertical@1.
--
-- MonitoringSource is tenant-scoped attachment authority. ProviderInstance is a
-- separate shared-provider identity referenced opaquely from source generations.
-- Multiple tenants MAY reference the same provider_instance_ref; that never
-- weakens tenant keys, source identity or provider-scope-to-tenant binding.

BEGIN;

CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE monitoring.monitoring_source (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    provider_scope_tenant_binding_id TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile = 'zabbix'),
    active_source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    display_name TEXT NOT NULL CHECK (display_name <> ''),
    credential_binding_ref TEXT NOT NULL CHECK (credential_binding_ref <> ''),
    configured_provider_scope JSONB NOT NULL CHECK (
        jsonb_typeof(configured_provider_scope) = 'object'
        AND configured_provider_scope ? 'host_group_refs'
        AND jsonb_typeof(configured_provider_scope->'host_group_refs') = 'array'
    ),
    operational_evidence_state TEXT NOT NULL CHECK (operational_evidence_state IN (
        'current', 'stale', 'incomplete', 'reconciliation_required', 'unavailable'
    )),
    replacement_candidate_ref TEXT NULL,
    last_successful_sync_at TIMESTAMPTZ NULL,
    last_attempt_at TIMESTAMPTZ NULL,
    last_sync_operation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id),
    UNIQUE (tenant_id, provider_scope_tenant_binding_id),
    CHECK (tenant_id <> ''),
    CHECK (monitoring_source_id <> ''),
    CHECK (provider_scope_tenant_binding_id <> ''),
    CHECK (active_source_instance_generation <> ''),
    CHECK (last_sync_operation_id <> '')
);

COMMENT ON TABLE monitoring.monitoring_source IS
'Tenant-scoped logical Monitoring attachment. provider_scope_tenant_binding_id identifies the explicit provider-scope-to-tenant binding. Credential/access and scope remain attachment configuration; physical provider installation identity is generation-bound by provider_instance_ref.';

CREATE TABLE monitoring.monitoring_source_generation (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile = 'zabbix'),
    provider_instance_ref TEXT NOT NULL CHECK (provider_instance_ref <> ''),
    provider_base_url TEXT NOT NULL CHECK (
        provider_base_url LIKE 'https://%'
        AND position('?' IN provider_base_url) = 0
        AND position('#' IN provider_base_url) = 0
        AND position('@' IN provider_base_url) = 0
        AND position(E'\\' IN provider_base_url) = 0
        AND provider_base_url !~ '[[:cntrl:][:space:]]'
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (source_instance_generation <> '')
);

COMMENT ON TABLE monitoring.monitoring_source_generation IS
'Immutable source-generation identity domain. provider_instance_ref identifies the external provider installation/control surface and may be shared by independent tenant-scoped Monitoring sources. source_instance_generation remains tenant/source historical fencing authority, not physical-provider ownership.';

ALTER TABLE monitoring.monitoring_source
    ADD CONSTRAINT monitoring_source_active_generation_fk
    FOREIGN KEY (tenant_id, monitoring_source_id, active_source_instance_generation)
    REFERENCES monitoring.monitoring_source_generation(
        tenant_id, monitoring_source_id, source_instance_generation
    )
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE monitoring.monitoring_sync_operation (
    tenant_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    responsibility_kind TEXT NOT NULL CHECK (responsibility_kind IN (
        'validation_and_initial_sync', 'manual_sync', 'scope_reconciliation',
        'replacement_candidate_validation', 'post_cutover_reconciliation'
    )),
    state TEXT NOT NULL CHECK (state IN (
        'pending', 'running', 'succeeded', 'reconciliation_required', 'failed_terminal'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    last_error_class TEXT NULL,
    PRIMARY KEY (tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(
            tenant_id, monitoring_source_id, source_instance_generation
        )
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (tenant_id <> ''),
    CHECK (monitoring_sync_operation_id <> ''),
    CHECK (monitoring_source_id <> ''),
    CHECK (source_instance_generation <> ''),
    CHECK (state <> 'running' OR started_at IS NOT NULL),
    CHECK (state NOT IN ('succeeded', 'failed_terminal') OR completed_at IS NOT NULL)
);

ALTER TABLE monitoring.monitoring_source
    ADD CONSTRAINT monitoring_source_last_sync_operation_fk
    FOREIGN KEY (tenant_id, last_sync_operation_id)
    REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE monitoring.monitoring_source_create_idempotency (
    tenant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('in_progress', 'completed', 'reconciliation_required')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    completed_at TIMESTAMPTZ NULL,
    PRIMARY KEY (tenant_id, idempotency_key),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id)
        REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (tenant_id <> ''),
    CHECK (idempotency_key <> ''),
    CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (state <> 'completed' OR completed_at IS NOT NULL)
);

CREATE FUNCTION monitoring.wave4_guard_source_identity_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.provider_scope_tenant_binding_id IS DISTINCT FROM OLD.provider_scope_tenant_binding_id
       OR NEW.provider_profile IS DISTINCT FROM OLD.provider_profile THEN
        RAISE EXCEPTION 'Monitoring source tenant/logical/binding identity/provider profile is immutable';
    END IF;
    IF NEW.configuration_revision < OLD.configuration_revision
       OR NEW.scope_revision < OLD.scope_revision THEN
        RAISE EXCEPTION 'Monitoring source revisions cannot regress';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_monitoring_source_identity_guard
BEFORE UPDATE ON monitoring.monitoring_source
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_source_identity_update();

CREATE FUNCTION monitoring.wave4_reject_generation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    RAISE EXCEPTION 'Monitoring source generation records are immutable';
END;
$$;

CREATE TRIGGER wave4_monitoring_source_generation_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_source_generation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_generation_update();

CREATE FUNCTION monitoring.create_zabbix_source(
    p_tenant_id TEXT,
    p_idempotency_key TEXT,
    p_request_fingerprint TEXT,
    p_monitoring_source_id TEXT,
    p_source_instance_generation TEXT,
    p_provider_scope_tenant_binding_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_display_name TEXT,
    p_provider_instance_ref TEXT,
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
       OR p_provider_scope_tenant_binding_id IS NULL OR p_provider_scope_tenant_binding_id = '' OR length(p_provider_scope_tenant_binding_id) > 512
       OR p_provider_scope_tenant_binding_id ~ '[[:cntrl:]]' OR p_provider_scope_tenant_binding_id <> btrim(p_provider_scope_tenant_binding_id)
       OR p_monitoring_sync_operation_id IS NULL OR p_monitoring_sync_operation_id = '' OR length(p_monitoring_sync_operation_id) > 512
       OR p_monitoring_sync_operation_id ~ '[[:cntrl:]]' OR p_monitoring_sync_operation_id <> btrim(p_monitoring_sync_operation_id)
       OR p_display_name IS NULL OR p_display_name = '' OR length(p_display_name) > 512
       OR p_display_name ~ '[[:cntrl:]]' OR p_display_name <> btrim(p_display_name)
       OR p_provider_instance_ref IS NULL OR p_provider_instance_ref = '' OR length(p_provider_instance_ref) > 512
       OR p_provider_instance_ref ~ '[[:cntrl:]]' OR p_provider_instance_ref <> btrim(p_provider_instance_ref)
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
        monitoring_source_id, monitoring_sync_operation_id, state
    ) VALUES (
        p_tenant_id, p_idempotency_key, p_request_fingerprint,
        p_monitoring_source_id, p_monitoring_sync_operation_id, 'in_progress'
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
        tenant_id, monitoring_source_id, provider_scope_tenant_binding_id, provider_profile,
        active_source_instance_generation, configuration_revision, scope_revision,
        display_name, credential_binding_ref, configured_provider_scope,
        operational_evidence_state, last_sync_operation_id
    ) VALUES (
        p_tenant_id, p_monitoring_source_id, p_provider_scope_tenant_binding_id, 'zabbix',
        p_source_instance_generation, 1, 1,
        p_display_name, p_credential_binding_ref, p_configured_provider_scope,
        'reconciliation_required', p_monitoring_sync_operation_id
    );

    INSERT INTO monitoring.monitoring_source_generation(
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_profile, provider_instance_ref, provider_base_url
    ) VALUES (
        p_tenant_id, p_monitoring_source_id, p_source_instance_generation,
        'zabbix', p_provider_instance_ref, p_provider_base_url
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

    UPDATE monitoring.monitoring_source_create_idempotency AS i
       SET state = 'completed', completed_at = transaction_timestamp()
     WHERE i.tenant_id = p_tenant_id AND i.idempotency_key = p_idempotency_key;

    RETURN QUERY SELECT p_monitoring_source_id, p_monitoring_sync_operation_id, 'completed'::TEXT, FALSE;
END;
$$;

COMMENT ON FUNCTION monitoring.create_zabbix_source(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB) IS
'Atomic local create-or-observe transaction. provider_instance_ref is external shared-provider lineage; tenant/source/binding keys remain the platform ownership boundary. No provider network call occurs here.';

COMMIT;
