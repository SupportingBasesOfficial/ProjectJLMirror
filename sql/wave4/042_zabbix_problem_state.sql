-- Wave 4 bounded Zabbix Problem State persistence.
-- Authority: wave4.monitoring-problem-state@1.
-- Scope: problem.get + explicit event.get recovery evidence + bounded trigger association
--        -> canonical Monitoring problem state.
-- Health, Alerting, ITSM, provider write-back, frontend and production deployment remain blocked.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_problem_state_executor') THEN
        CREATE ROLE jlmirror_wave4_problem_state_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_problem_state_invoker') THEN
        CREATE ROLE jlmirror_wave4_problem_state_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO jlmirror_wave4_problem_state_executor,
    jlmirror_wave4_problem_state_invoker;
REVOKE CREATE ON SCHEMA monitoring FROM jlmirror_wave4_problem_state_executor,
    jlmirror_wave4_problem_state_invoker;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN problem_poll_epoch BIGINT NOT NULL DEFAULT 1
        CHECK (problem_poll_epoch > 0),
    ADD COLUMN problem_poll_generation BIGINT NOT NULL DEFAULT 0
        CHECK (problem_poll_generation >= 0);

ALTER TABLE monitoring.monitoring_sync_operation
    DROP CONSTRAINT monitoring_sync_operation_responsibility_kind_check;
ALTER TABLE monitoring.monitoring_sync_operation
    ADD CONSTRAINT monitoring_sync_operation_responsibility_kind_check
    CHECK (responsibility_kind IN (
        'validation_and_initial_sync', 'host_inventory_sync', 'metric_definition_sync',
        'metric_current_state_sync', 'metric_history_sync', 'metric_history_reconciliation',
        'problem_state_sync', 'problem_state_reconciliation',
        'manual_sync', 'scope_reconciliation', 'replacement_candidate_validation',
        'post_cutover_reconciliation'
    )),
    ADD COLUMN problem_poll_epoch BIGINT NULL
        CHECK (problem_poll_epoch IS NULL OR problem_poll_epoch > 0),
    ADD COLUMN problem_poll_generation BIGINT NULL
        CHECK (problem_poll_generation IS NULL OR problem_poll_generation > 0);

CREATE UNLOGGED TABLE monitoring.monitoring_problem_state_runtime_admission (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    problem_poll_epoch BIGINT NOT NULL CHECK (problem_poll_epoch > 0),
    placement_version TEXT NOT NULL CHECK (placement_version <> ''),
    recovery_generation TEXT NOT NULL CHECK (recovery_generation <> ''),
    recovery_admission_ref TEXT NOT NULL CHECK (recovery_admission_ref <> ''),
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE monitoring.monitoring_problem_state_runtime_admission IS
'Volatile fail-closed admission for Problem State. It is independent from Host Inventory, Metric Definitions, Current State and Metric History authority streams.';

CREATE TABLE monitoring.monitoring_problem_provider_binding (
    tenant_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile='zabbix'),
    provider_external_ref TEXT NOT NULL,
    provider_trigger_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, problem_id),
    UNIQUE (
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_profile, provider_external_ref
    ),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    CHECK (problem_id <> '' AND length(problem_id) <= 512),
    CHECK (provider_external_ref <> '' AND length(provider_external_ref) <= 256),
    CHECK (provider_trigger_ref <> '' AND length(provider_trigger_ref) <= 256)
);

COMMENT ON TABLE monitoring.monitoring_problem_provider_binding IS
'Stable canonical problem identity binding. Provider eventid is scoped external evidence and never becomes canonical problem identity.';

CREATE TABLE monitoring.monitoring_problem (
    tenant_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    problem_state TEXT NOT NULL CHECK (problem_state IN ('active','resolved')),
    severity_class TEXT NOT NULL CHECK (severity_class IN ('unknown','informational','warning','degraded','critical')),
    summary TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ NULL,
    last_confirmed_at TIMESTAMPTZ NOT NULL,
    evidence_state TEXT NOT NULL CHECK (evidence_state IN ('current','stale','incomplete','reconciliation_required','unavailable')),
    projection_revision BIGINT NOT NULL CHECK (projection_revision > 0),
    problem_poll_epoch BIGINT NOT NULL CHECK (problem_poll_epoch > 0),
    problem_poll_generation BIGINT NOT NULL CHECK (problem_poll_generation > 0),
    provider_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    provider_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, problem_id),
    FOREIGN KEY (tenant_id, problem_id)
        REFERENCES monitoring.monitoring_problem_provider_binding(tenant_id, problem_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    CHECK (summary <> '' AND length(summary) <= 8192),
    CHECK (octet_length(provider_metadata::text) <= 131072),
    CHECK (
        (problem_state='active' AND resolved_at IS NULL)
        OR (problem_state='resolved' AND resolved_at IS NOT NULL)
    )
);

COMMENT ON TABLE monitoring.monitoring_problem IS
'Canonical Monitoring problem projection. Provider acknowledgement is metadata only and has no platform acknowledgement, Alerting or ITSM authority.';

CREATE TABLE monitoring.monitoring_problem_transition (
    tenant_id TEXT NOT NULL,
    problem_transition_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    from_problem_state TEXT NULL CHECK (from_problem_state IS NULL OR from_problem_state IN ('active','resolved')),
    to_problem_state TEXT NOT NULL CHECK (to_problem_state IN ('active','resolved')),
    from_severity_class TEXT NULL CHECK (from_severity_class IS NULL OR from_severity_class IN ('unknown','informational','warning','degraded','critical')),
    to_severity_class TEXT NOT NULL CHECK (to_severity_class IN ('unknown','informational','warning','degraded','critical')),
    transition_reason TEXT NOT NULL CHECK (transition_reason IN ('provider_positive','provider_recovery','authoritative_negative','severity_change')),
    provider_evidence_ref TEXT NOT NULL,
    projection_revision BIGINT NOT NULL CHECK (projection_revision > 0),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, problem_transition_id),
    UNIQUE (tenant_id, problem_id, projection_revision),
    FOREIGN KEY (tenant_id, problem_id)
        REFERENCES monitoring.monitoring_problem_provider_binding(tenant_id, problem_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    CHECK (problem_transition_id <> '' AND length(problem_transition_id) <= 512),
    CHECK (provider_evidence_ref <> '' AND length(provider_evidence_ref) <= 512)
);

ALTER TABLE monitoring.monitoring_problem_state_runtime_admission ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem_state_runtime_admission FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem_provider_binding ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem_provider_binding FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem_transition FORCE ROW LEVEL SECURITY;

CREATE POLICY problem_state_runtime_admission_tenant_policy
ON monitoring.monitoring_problem_state_runtime_admission
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY problem_provider_binding_tenant_policy
ON monitoring.monitoring_problem_provider_binding
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY problem_tenant_policy
ON monitoring.monitoring_problem
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY problem_transition_tenant_policy
ON monitoring.monitoring_problem_transition
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

REVOKE ALL ON monitoring.monitoring_problem_state_runtime_admission,
    monitoring.monitoring_problem_provider_binding,
    monitoring.monitoring_problem,
    monitoring.monitoring_problem_transition FROM PUBLIC;

GRANT SELECT ON monitoring.monitoring_source,
    monitoring.monitoring_source_generation,
    monitoring.monitoring_resource,
    monitoring.monitoring_problem_state_runtime_admission,
    monitoring.monitoring_problem_provider_binding,
    monitoring.monitoring_problem
TO jlmirror_wave4_problem_state_executor;

GRANT SELECT, INSERT, UPDATE ON monitoring.monitoring_sync_operation,
    monitoring.monitoring_source,
    monitoring.monitoring_problem
TO jlmirror_wave4_problem_state_executor;
GRANT SELECT, INSERT ON monitoring.monitoring_problem_provider_binding,
    monitoring.monitoring_problem_transition
TO jlmirror_wave4_problem_state_executor;

GRANT SELECT, INSERT, UPDATE, DELETE ON monitoring.monitoring_problem_state_runtime_admission
TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.wave4_problem_state_executor_is_current_user()
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
    SELECT current_user='jlmirror_wave4_problem_state_executor'
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_problem_binding_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_problem_state_executor_is_current_user() THEN
        RAISE EXCEPTION 'Problem provider binding requires guarded Problem State executor authority';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER problem_binding_insert_guard
BEFORE INSERT ON monitoring.monitoring_problem_provider_binding
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_problem_binding_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_reject_problem_immutable_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    RAISE EXCEPTION 'Problem identity/transition evidence is immutable';
END;
$$;
CREATE TRIGGER problem_binding_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.monitoring_problem_provider_binding
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_problem_immutable_mutation();
CREATE TRIGGER problem_transition_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.monitoring_problem_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_problem_immutable_mutation();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_problem_projection_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_problem_state_executor_is_current_user() THEN
        RAISE EXCEPTION 'Problem projection mutation requires guarded Problem State executor authority';
    END IF;
    IF TG_OP='UPDATE' AND (
        NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
        OR NEW.problem_id IS DISTINCT FROM OLD.problem_id
        OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
        OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
        OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
    ) THEN
        RAISE EXCEPTION 'Problem projection ownership and canonical identity are immutable';
    END IF;
    IF TG_OP='UPDATE' AND NEW.projection_revision <> OLD.projection_revision + 1 THEN
        RAISE EXCEPTION 'Problem projection revision must advance exactly once';
    END IF;
    IF TG_OP='UPDATE' AND OLD.problem_state='resolved' AND NEW.problem_state='active' THEN
        RAISE EXCEPTION 'Resolved problem cannot be reopened under the same canonical provider event identity';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER problem_projection_guard
BEFORE INSERT OR UPDATE ON monitoring.monitoring_problem
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_problem_projection_mutation();

COMMIT;
