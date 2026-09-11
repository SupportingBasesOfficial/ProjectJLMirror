-- Wave 4 bounded Zabbix current-state ingestion.
-- Authority: wave4.monitoring-metric-current-state@1.
-- Scope: item.get current evidence -> durable acceptance envelope -> metric_current_state.
-- History materialization, history.get, problems, health, provider write-back and frontend remain blocked.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_metric_current_state_executor') THEN
        CREATE ROLE jlmirror_wave4_metric_current_state_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_metric_current_state_invoker') THEN
        CREATE ROLE jlmirror_wave4_metric_current_state_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO jlmirror_wave4_metric_current_state_executor,
    jlmirror_wave4_metric_current_state_invoker;
REVOKE CREATE ON SCHEMA monitoring FROM jlmirror_wave4_metric_current_state_executor,
    jlmirror_wave4_metric_current_state_invoker;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN current_state_poll_epoch BIGINT NOT NULL DEFAULT 1
        CHECK (current_state_poll_epoch > 0),
    ADD COLUMN current_state_poll_generation BIGINT NOT NULL DEFAULT 0
        CHECK (current_state_poll_generation >= 0);

ALTER TABLE monitoring.monitoring_sync_operation
    DROP CONSTRAINT monitoring_sync_operation_responsibility_kind_check;
ALTER TABLE monitoring.monitoring_sync_operation
    ADD CONSTRAINT monitoring_sync_operation_responsibility_kind_check
    CHECK (responsibility_kind IN (
        'validation_and_initial_sync', 'host_inventory_sync', 'metric_definition_sync',
        'metric_current_state_sync', 'manual_sync', 'scope_reconciliation',
        'replacement_candidate_validation', 'post_cutover_reconciliation'
    )),
    ADD COLUMN current_state_poll_epoch BIGINT NULL
        CHECK (current_state_poll_epoch IS NULL OR current_state_poll_epoch > 0),
    ADD COLUMN current_state_poll_generation BIGINT NULL
        CHECK (current_state_poll_generation IS NULL OR current_state_poll_generation > 0);

CREATE UNLOGGED TABLE monitoring.monitoring_metric_current_state_runtime_admission (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    current_state_poll_epoch BIGINT NOT NULL CHECK (current_state_poll_epoch > 0),
    placement_version TEXT NOT NULL CHECK (placement_version <> ''),
    recovery_generation TEXT NOT NULL CHECK (recovery_generation <> ''),
    recovery_admission_ref TEXT NOT NULL CHECK (recovery_admission_ref <> ''),
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE monitoring.monitoring_metric_current_state_runtime_admission IS
'Volatile fail-closed admission for Metric Current State. It is independent from Host Inventory and Metric Definition poll streams and must be re-established after recovery/relocation.';

CREATE TABLE monitoring.monitoring_metric_observation_acceptance (
    tenant_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile='zabbix'),
    provider_external_ref TEXT NOT NULL,
    provider_clock BIGINT NOT NULL CHECK (provider_clock > 0),
    provider_ns INTEGER NOT NULL CHECK (provider_ns BETWEEN 0 AND 999999999),
    observed_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    value_kind TEXT NOT NULL CHECK (value_kind IN ('number','integer','boolean','string','text','log')),
    canonical_value JSONB NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    current_state_poll_epoch BIGINT NOT NULL CHECK (current_state_poll_epoch > 0),
    current_state_poll_generation BIGINT NOT NULL CHECK (current_state_poll_generation > 0),
    history_projection_state TEXT NOT NULL DEFAULT 'pending'
        CHECK (history_projection_state IN ('pending','projected')),
    PRIMARY KEY (tenant_id, observation_id),
    UNIQUE (
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_external_ref, provider_clock, provider_ns
    ),
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id)
        REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    CHECK (observation_id <> '' AND length(observation_id) <= 512),
    CHECK (provider_external_ref <> '' AND length(provider_external_ref) <= 256),
    CHECK (octet_length(canonical_value::text) <= 131072)
);

COMMENT ON TABLE monitoring.monitoring_metric_observation_acceptance IS
'Durable acceptance envelope for newly accepted metric observations. This is not metric_observation history materialization; history_projection_state preserves the mandatory later History projection obligation.';

CREATE TABLE monitoring.metric_current_state (
    tenant_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    current_observation_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    value_kind TEXT NOT NULL CHECK (value_kind IN ('number','integer','boolean','string','text','log')),
    canonical_value JSONB NOT NULL,
    evidence_state TEXT NOT NULL CHECK (evidence_state IN ('current','stale','incomplete','reconciliation_required','unavailable')),
    projection_revision BIGINT NOT NULL CHECK (projection_revision > 0),
    current_state_poll_epoch BIGINT NOT NULL CHECK (current_state_poll_epoch > 0),
    current_state_poll_generation BIGINT NOT NULL CHECK (current_state_poll_generation > 0),
    last_changed_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, metric_definition_id),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    FOREIGN KEY (tenant_id, current_observation_id)
        REFERENCES monitoring.monitoring_metric_observation_acceptance(tenant_id, observation_id),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK (octet_length(canonical_value::text) <= 131072)
);

CREATE TABLE monitoring.monitoring_metric_current_state_transition (
    tenant_id TEXT NOT NULL,
    current_state_transition_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    from_observation_id TEXT NULL,
    to_observation_id TEXT NOT NULL,
    projection_revision BIGINT NOT NULL CHECK (projection_revision > 0),
    evidence_state TEXT NOT NULL CHECK (evidence_state IN ('current','stale','incomplete','reconciliation_required','unavailable')),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, current_state_transition_id),
    UNIQUE (tenant_id, metric_definition_id, to_observation_id),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    FOREIGN KEY (tenant_id, to_observation_id)
        REFERENCES monitoring.monitoring_metric_observation_acceptance(tenant_id, observation_id),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK (current_state_transition_id <> '' AND length(current_state_transition_id) <= 512)
);

COMMENT ON TABLE monitoring.monitoring_metric_current_state_transition IS
'Immutable owner-domain transition evidence. Publication attempt state belongs only to the canonical Wave 2 system.async_outbox_* substrate.';

ALTER TABLE monitoring.monitoring_metric_current_state_runtime_admission ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_current_state_runtime_admission FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_observation_acceptance ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_observation_acceptance FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_current_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_current_state FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_current_state_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_current_state_transition FORCE ROW LEVEL SECURITY;

CREATE POLICY metric_current_state_runtime_admission_tenant_policy
ON monitoring.monitoring_metric_current_state_runtime_admission
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_observation_acceptance_tenant_policy
ON monitoring.monitoring_metric_observation_acceptance
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_current_state_tenant_policy
ON monitoring.metric_current_state
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_current_state_transition_tenant_policy
ON monitoring.monitoring_metric_current_state_transition
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

REVOKE ALL ON monitoring.monitoring_metric_current_state_runtime_admission,
    monitoring.monitoring_metric_observation_acceptance,
    monitoring.metric_current_state,
    monitoring.monitoring_metric_current_state_transition FROM PUBLIC;

GRANT SELECT ON monitoring.monitoring_source,
    monitoring.monitoring_source_generation,
    monitoring.monitoring_resource,
    monitoring.metric_definition,
    monitoring.metric_definition_provider_binding,
    monitoring.monitoring_metric_current_state_runtime_admission
TO jlmirror_wave4_metric_current_state_executor;

GRANT SELECT, INSERT, UPDATE ON monitoring.monitoring_sync_operation,
    monitoring.monitoring_source,
    monitoring.metric_current_state
TO jlmirror_wave4_metric_current_state_executor;
GRANT SELECT, INSERT ON monitoring.monitoring_metric_observation_acceptance,
    monitoring.monitoring_metric_current_state_transition
TO jlmirror_wave4_metric_current_state_executor;

GRANT SELECT, INSERT, UPDATE, DELETE ON monitoring.monitoring_metric_current_state_runtime_admission
TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.wave4_metric_current_state_executor_is_current_user()
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
    SELECT current_user='jlmirror_wave4_metric_current_state_executor'
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_current_state_acceptance_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric observation acceptance requires guarded Current executor authority';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER metric_observation_acceptance_executor_guard
BEFORE INSERT ON monitoring.monitoring_metric_observation_acceptance
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_current_state_acceptance_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_reject_metric_current_state_immutable_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    RAISE EXCEPTION 'Metric Current State immutable evidence cannot be updated or deleted by this slice';
END;
$$;
CREATE TRIGGER metric_observation_acceptance_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.monitoring_metric_observation_acceptance
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_metric_current_state_immutable_mutation();
CREATE TRIGGER metric_current_state_transition_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.monitoring_metric_current_state_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_metric_current_state_immutable_mutation();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_current_state_projection_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric Current State projection mutation requires guarded executor authority';
    END IF;
    IF TG_OP='UPDATE' AND (
        NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
        OR NEW.metric_definition_id IS DISTINCT FROM OLD.metric_definition_id
        OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
        OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
        OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
        OR NEW.value_kind IS DISTINCT FROM OLD.value_kind
    ) THEN
        RAISE EXCEPTION 'Metric Current State projection ownership/value kind is immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER metric_current_state_projection_guard
BEFORE INSERT OR UPDATE ON monitoring.metric_current_state
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_current_state_projection_mutation();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_current_state_transition_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric Current State transition creation requires guarded executor authority';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER metric_current_state_transition_insert_guard
BEFORE INSERT ON monitoring.monitoring_metric_current_state_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_current_state_transition_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_current_state_source_poll_authority()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NEW.current_state_poll_epoch IS DISTINCT FROM OLD.current_state_poll_epoch
       OR NEW.current_state_poll_generation IS DISTINCT FROM OLD.current_state_poll_generation THEN
        IF current_user NOT IN ('jlmirror_wave4_metric_current_state_executor','jlmirror_wave4_recovery_authority') THEN
            RAISE EXCEPTION 'Metric Current State poll authority requires guarded authority';
        END IF;
    END IF;
    IF NEW.current_state_poll_epoch < OLD.current_state_poll_epoch THEN
        RAISE EXCEPTION 'Metric Current State poll epoch cannot rewind';
    END IF;
    IF NEW.current_state_poll_epoch = OLD.current_state_poll_epoch THEN
        IF NEW.current_state_poll_generation < OLD.current_state_poll_generation THEN
            RAISE EXCEPTION 'Metric Current State poll generation cannot rewind';
        END IF;
        IF NEW.current_state_poll_generation > OLD.current_state_poll_generation + 1 THEN
            RAISE EXCEPTION 'Metric Current State poll generation may advance only one generation at a time';
        END IF;
        IF NEW.current_state_poll_generation > OLD.current_state_poll_generation
           AND NOT EXISTS (
               SELECT 1
                 FROM monitoring.monitoring_metric_current_state_runtime_admission AS a
                WHERE a.tenant_id=NEW.tenant_id
                  AND a.monitoring_source_id=NEW.monitoring_source_id
                  AND a.current_state_poll_epoch=NEW.current_state_poll_epoch
           ) THEN
            RAISE EXCEPTION 'Metric Current State polling requires current recovery/placement admission';
        END IF;
    ELSE
        IF current_user <> 'jlmirror_wave4_recovery_authority' THEN
            RAISE EXCEPTION 'Metric Current State poll epoch may advance only through recovery authority';
        END IF;
        IF NEW.current_state_poll_generation IS DISTINCT FROM OLD.current_state_poll_generation THEN
            RAISE EXCEPTION 'Metric Current State recovery epoch transition must preserve local generation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER metric_current_state_source_poll_authority_guard
BEFORE UPDATE OF current_state_poll_epoch,current_state_poll_generation
ON monitoring.monitoring_source
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_current_state_source_poll_authority();

COMMIT;
