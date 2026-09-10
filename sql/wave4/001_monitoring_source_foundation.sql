-- Wave 4 Monitoring source foundation.
-- Authority base: main@8e2265a4ee2810ea701166228e8f44ad3bc0d894
--
-- This migration materializes only the bounded Monitoring/Zabbix source-creation
-- capability authorized by wave4.monitoring-zabbix.vertical@1. It does not
-- authorize production numerics, provider write-back, browser realtime, Alerting,
-- ITSM or any other Product vertical.
--
-- Network-dependent Zabbix validation is deliberately absent. The source row and
-- the durable validation_and_initial_sync responsibility commit locally first;
-- provider/DNS/egress work happens later in runtime.worker@1.

BEGIN;

CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE monitoring.monitoring_source (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile = 'zabbix'),
    active_source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    display_name TEXT NOT NULL CHECK (display_name <> ''),
    provider_base_url TEXT NOT NULL CHECK (
        provider_base_url LIKE 'https://%'
        AND position('?' IN provider_base_url) = 0
        AND position('#' IN provider_base_url) = 0
    ),
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
    UNIQUE (tenant_id, monitoring_source_id, active_source_instance_generation),
    CHECK (tenant_id <> ''),
    CHECK (monitoring_source_id <> ''),
    CHECK (active_source_instance_generation <> ''),
    CHECK (last_sync_operation_id <> '')
);

COMMENT ON TABLE monitoring.monitoring_source IS
'Canonical tenant-scoped Monitoring source authority. Provider-native IDs and physical placement are not platform identity or tenant authority.';

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
        REFERENCES monitoring.monitoring_source(
            tenant_id, monitoring_source_id, active_source_instance_generation
        )
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (tenant_id <> ''),
    CHECK (monitoring_sync_operation_id <> ''),
    CHECK (monitoring_source_id <> ''),
    CHECK (source_instance_generation <> ''),
    CHECK (state <> 'running' OR started_at IS NOT NULL),
    CHECK (state NOT IN ('succeeded', 'failed_terminal') OR completed_at IS NOT NULL)
);

COMMENT ON TABLE monitoring.monitoring_sync_operation IS
'Durable bounded Monitoring work responsibility. Operation identity and URL possession are not bearer authority.';

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

COMMENT ON TABLE monitoring.monitoring_source_create_idempotency IS
'Durable create-source idempotency ownership. Uniqueness is tenant_id + idempotency_key; request fingerprint mismatch must be rejected by the owning application transaction.';

CREATE FUNCTION monitoring.wave4_guard_source_identity_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.provider_profile IS DISTINCT FROM OLD.provider_profile THEN
        RAISE EXCEPTION 'Monitoring source tenant/logical identity/provider profile is immutable';
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

COMMIT;
