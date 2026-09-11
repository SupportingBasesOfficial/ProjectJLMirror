-- Wave 4 bounded Zabbix metric-history ingestion.
-- Authority: wave4.monitoring-metric-history@1.
-- Scope: durable accepted observation / bounded history.get -> immutable metric_observation
--        + independent per-stream checkpoint/reconciliation state.
-- Current State mutation, Problems/Triggers/Events, Health, provider write-back,
-- frontend and production storage specialization remain blocked.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_metric_history_executor') THEN
        CREATE ROLE jlmirror_wave4_metric_history_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_metric_history_invoker') THEN
        CREATE ROLE jlmirror_wave4_metric_history_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO jlmirror_wave4_metric_history_executor,
    jlmirror_wave4_metric_history_invoker;
REVOKE CREATE ON SCHEMA monitoring FROM jlmirror_wave4_metric_history_executor,
    jlmirror_wave4_metric_history_invoker;

ALTER TABLE monitoring.monitoring_sync_operation
    DROP CONSTRAINT monitoring_sync_operation_responsibility_kind_check;
ALTER TABLE monitoring.monitoring_sync_operation
    ADD CONSTRAINT monitoring_sync_operation_responsibility_kind_check
    CHECK (responsibility_kind IN (
        'validation_and_initial_sync', 'host_inventory_sync', 'metric_definition_sync',
        'metric_current_state_sync', 'metric_history_sync', 'metric_history_reconciliation',
        'manual_sync', 'scope_reconciliation', 'replacement_candidate_validation',
        'post_cutover_reconciliation'
    ));

CREATE TABLE monitoring.metric_observation (
    tenant_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile='zabbix'),
    provider_external_ref TEXT NOT NULL,
    provider_clock BIGINT NOT NULL CHECK (provider_clock > 0),
    provider_ns INTEGER NOT NULL CHECK (provider_ns BETWEEN 0 AND 999999999),
    observed_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    value_kind TEXT NOT NULL CHECK (value_kind IN ('number','integer','boolean','string','text','log')),
    canonical_value JSONB NOT NULL,
    PRIMARY KEY (tenant_id, observation_id),
    UNIQUE (
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_external_ref, provider_clock, provider_ns
    ),
    FOREIGN KEY (tenant_id, observation_id)
        REFERENCES monitoring.monitoring_metric_observation_acceptance(tenant_id, observation_id),
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

COMMENT ON TABLE monitoring.metric_observation IS
'Immutable canonical historical metric sample. It reuses the durable accepted observation identity and never acquires Metric Current State authority.';

CREATE TABLE monitoring.metric_history_stream_state (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    provider_external_ref TEXT NOT NULL,
    history_value_type INTEGER NOT NULL CHECK (history_value_type BETWEEN 0 AND 5),
    metric_definition_id TEXT NOT NULL,
    provisional_clock BIGINT NULL CHECK (provisional_clock IS NULL OR provisional_clock > 0),
    provisional_ns INTEGER NULL CHECK (provisional_ns IS NULL OR provisional_ns BETWEEN 0 AND 999999999),
    safe_clock BIGINT NULL CHECK (safe_clock IS NULL OR safe_clock > 0),
    safe_ns INTEGER NULL CHECK (safe_ns IS NULL OR safe_ns BETWEEN 0 AND 999999999),
    finalized_through_clock BIGINT NULL CHECK (finalized_through_clock IS NULL OR finalized_through_clock > 0),
    coverage_state TEXT NOT NULL DEFAULT 'open'
        CHECK (coverage_state IN ('open','reconciliation_required','gap','finalized')),
    last_reconciled_from BIGINT NULL CHECK (last_reconciled_from IS NULL OR last_reconciled_from > 0),
    last_reconciled_through BIGINT NULL CHECK (last_reconciled_through IS NULL OR last_reconciled_through > 0),
    checkpoint_revision BIGINT NOT NULL DEFAULT 1 CHECK (checkpoint_revision > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_external_ref, history_value_type
    ),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    CHECK (provider_external_ref <> '' AND length(provider_external_ref) <= 256),
    CHECK ((provisional_clock IS NULL) = (provisional_ns IS NULL)),
    CHECK ((safe_clock IS NULL) = (safe_ns IS NULL)),
    CHECK (last_reconciled_from IS NULL OR last_reconciled_through IS NULL OR last_reconciled_from <= last_reconciled_through)
);

COMMENT ON TABLE monitoring.metric_history_stream_state IS
'Independent logical History checkpoint/reconciliation authority per source generation, item and history value type. Provisional high-water mark is not completeness authority.';

CREATE TABLE monitoring.metric_history_gap_evidence (
    tenant_id TEXT NOT NULL,
    history_gap_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    provider_external_ref TEXT NOT NULL,
    history_value_type INTEGER NOT NULL CHECK (history_value_type BETWEEN 0 AND 5),
    metric_definition_id TEXT NOT NULL,
    gap_from_clock BIGINT NOT NULL CHECK (gap_from_clock > 0),
    gap_through_clock BIGINT NOT NULL CHECK (gap_through_clock >= gap_from_clock),
    reason TEXT NOT NULL CHECK (reason IN ('provider_retention_loss','provider_visibility_uncertain','truncated_window','recovery_gap')),
    evidence_ref TEXT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, history_gap_id),
    FOREIGN KEY (
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_external_ref, history_value_type
    ) REFERENCES monitoring.metric_history_stream_state(
        tenant_id, monitoring_source_id, source_instance_generation,
        provider_external_ref, history_value_type
    ),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    CHECK (history_gap_id <> '' AND length(history_gap_id) <= 512),
    CHECK (evidence_ref IS NULL OR (evidence_ref <> '' AND length(evidence_ref) <= 512))
);

ALTER TABLE monitoring.metric_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_observation FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_history_stream_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_history_stream_state FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_history_gap_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_history_gap_evidence FORCE ROW LEVEL SECURITY;

CREATE POLICY metric_observation_tenant_policy ON monitoring.metric_observation
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_history_stream_state_tenant_policy ON monitoring.metric_history_stream_state
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_history_gap_evidence_tenant_policy ON monitoring.metric_history_gap_evidence
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

REVOKE ALL ON monitoring.metric_observation,
    monitoring.metric_history_stream_state,
    monitoring.metric_history_gap_evidence FROM PUBLIC;

GRANT SELECT ON monitoring.monitoring_source,
    monitoring.monitoring_source_generation,
    monitoring.monitoring_resource,
    monitoring.metric_definition,
    monitoring.metric_definition_provider_binding,
    monitoring.monitoring_metric_observation_acceptance,
    monitoring.metric_observation,
    monitoring.metric_history_stream_state,
    monitoring.metric_history_gap_evidence
TO jlmirror_wave4_metric_history_executor;

GRANT INSERT ON monitoring.metric_observation,
    monitoring.metric_history_gap_evidence
TO jlmirror_wave4_metric_history_executor;
GRANT INSERT, UPDATE ON monitoring.metric_history_stream_state
TO jlmirror_wave4_metric_history_executor;
GRANT UPDATE (history_projection_state) ON monitoring.monitoring_metric_observation_acceptance
TO jlmirror_wave4_metric_history_executor;

CREATE OR REPLACE FUNCTION monitoring.wave4_metric_history_executor_is_current_user()
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
    SELECT current_user='jlmirror_wave4_metric_history_executor'
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_reject_metric_history_immutable_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    RAISE EXCEPTION 'Metric History immutable evidence cannot be updated or deleted';
END;
$$;
CREATE TRIGGER metric_observation_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.metric_observation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_metric_history_immutable_mutation();
CREATE TRIGGER metric_history_gap_evidence_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.metric_history_gap_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_metric_history_immutable_mutation();

DROP TRIGGER metric_observation_acceptance_immutable_guard
ON monitoring.monitoring_metric_observation_acceptance;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_observation_acceptance_history_projection()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'Accepted metric observation is immutable';
    END IF;
    IF current_user <> 'jlmirror_wave4_metric_history_executor' THEN
        RAISE EXCEPTION 'Accepted metric observation mutation requires guarded History executor authority';
    END IF;
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.observation_id IS DISTINCT FROM OLD.observation_id
       OR NEW.monitoring_sync_operation_id IS DISTINCT FROM OLD.monitoring_sync_operation_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
       OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
       OR NEW.metric_definition_id IS DISTINCT FROM OLD.metric_definition_id
       OR NEW.provider_profile IS DISTINCT FROM OLD.provider_profile
       OR NEW.provider_external_ref IS DISTINCT FROM OLD.provider_external_ref
       OR NEW.provider_clock IS DISTINCT FROM OLD.provider_clock
       OR NEW.provider_ns IS DISTINCT FROM OLD.provider_ns
       OR NEW.observed_at IS DISTINCT FROM OLD.observed_at
       OR NEW.accepted_at IS DISTINCT FROM OLD.accepted_at
       OR NEW.value_kind IS DISTINCT FROM OLD.value_kind
       OR NEW.canonical_value IS DISTINCT FROM OLD.canonical_value
       OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
       OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
       OR NEW.current_state_poll_epoch IS DISTINCT FROM OLD.current_state_poll_epoch
       OR NEW.current_state_poll_generation IS DISTINCT FROM OLD.current_state_poll_generation THEN
        RAISE EXCEPTION 'Accepted metric observation payload and ownership are immutable';
    END IF;
    IF OLD.history_projection_state <> 'pending' OR NEW.history_projection_state <> 'projected' THEN
        RAISE EXCEPTION 'History projection state permits only pending to projected';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM monitoring.metric_observation AS h
        WHERE h.tenant_id=OLD.tenant_id
          AND h.observation_id=OLD.observation_id
          AND h.monitoring_source_id=OLD.monitoring_source_id
          AND h.source_instance_generation=OLD.source_instance_generation
          AND h.monitoring_resource_id=OLD.monitoring_resource_id
          AND h.metric_definition_id=OLD.metric_definition_id
          AND h.provider_external_ref=OLD.provider_external_ref
          AND h.provider_clock=OLD.provider_clock
          AND h.provider_ns=OLD.provider_ns
          AND h.value_kind=OLD.value_kind
          AND h.canonical_value=OLD.canonical_value
    ) THEN
        RAISE EXCEPTION 'History projection cannot be acknowledged before compatible durable projection exists';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER metric_observation_acceptance_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.monitoring_metric_observation_acceptance
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_observation_acceptance_history_projection();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_history_projection_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    accepted monitoring.monitoring_metric_observation_acceptance%ROWTYPE;
BEGIN
    IF NOT monitoring.wave4_metric_history_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric History projection requires guarded executor authority';
    END IF;
    SELECT * INTO accepted
      FROM monitoring.monitoring_metric_observation_acceptance AS a
     WHERE a.tenant_id=NEW.tenant_id AND a.observation_id=NEW.observation_id
     FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Metric History projection requires durable accepted observation';
    END IF;
    IF ROW(
        NEW.monitoring_source_id, NEW.source_instance_generation, NEW.monitoring_resource_id,
        NEW.metric_definition_id, NEW.provider_profile, NEW.provider_external_ref,
        NEW.provider_clock, NEW.provider_ns, NEW.observed_at, NEW.accepted_at,
        NEW.value_kind, NEW.canonical_value
    ) IS DISTINCT FROM ROW(
        accepted.monitoring_source_id, accepted.source_instance_generation,
        accepted.monitoring_resource_id, accepted.metric_definition_id,
        accepted.provider_profile, accepted.provider_external_ref,
        accepted.provider_clock, accepted.provider_ns, accepted.observed_at,
        accepted.accepted_at, accepted.value_kind, accepted.canonical_value
    ) THEN
        RAISE EXCEPTION 'Metric History projection must exactly match durable accepted observation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER metric_history_projection_insert_guard
BEFORE INSERT ON monitoring.metric_observation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_history_projection_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_history_stream_state()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_metric_history_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric History checkpoint mutation requires guarded executor authority';
    END IF;
    IF TG_OP='UPDATE' THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.provider_external_ref IS DISTINCT FROM OLD.provider_external_ref
           OR NEW.history_value_type IS DISTINCT FROM OLD.history_value_type
           OR NEW.metric_definition_id IS DISTINCT FROM OLD.metric_definition_id THEN
            RAISE EXCEPTION 'Metric History stream identity is immutable';
        END IF;
        IF NEW.checkpoint_revision <> OLD.checkpoint_revision + 1 THEN
            RAISE EXCEPTION 'Metric History checkpoint revision must advance exactly once';
        END IF;
        IF OLD.safe_clock IS NOT NULL AND NEW.safe_clock IS NOT NULL
           AND ROW(NEW.safe_clock,NEW.safe_ns) < ROW(OLD.safe_clock,OLD.safe_ns) THEN
            RAISE EXCEPTION 'Metric History safe checkpoint cannot rewind';
        END IF;
        IF OLD.finalized_through_clock IS NOT NULL
           AND (NEW.finalized_through_clock IS NULL OR NEW.finalized_through_clock < OLD.finalized_through_clock) THEN
            RAISE EXCEPTION 'Metric History finalization cannot rewind';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER metric_history_stream_state_guard
BEFORE INSERT OR UPDATE ON monitoring.metric_history_stream_state
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_history_stream_state();

COMMIT;
