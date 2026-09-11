-- Wave 4 bounded Monitoring Health Projection foundation.
-- Authority: wave4.monitoring-health-projection@1.
-- Health is derived from canonical Monitoring state only; it introduces no provider polling authority.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_health_projection_executor') THEN
        CREATE ROLE jlmirror_wave4_health_projection_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_health_projection_invoker') THEN
        CREATE ROLE jlmirror_wave4_health_projection_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO
    jlmirror_wave4_health_projection_executor,
    jlmirror_wave4_health_projection_invoker;
REVOKE CREATE ON SCHEMA monitoring FROM
    jlmirror_wave4_health_projection_executor,
    jlmirror_wave4_health_projection_invoker;

CREATE TABLE monitoring.health_projection (
    tenant_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    health_class TEXT NOT NULL
        CHECK (health_class IN ('unknown','healthy','degraded','unhealthy')),
    evidence_state TEXT NOT NULL
        CHECK (evidence_state IN ('current','stale','incomplete','reconciliation_required','unavailable')),
    projection_revision BIGINT NOT NULL CHECK (projection_revision > 0),
    last_changed_at TIMESTAMPTZ NOT NULL,
    last_evidence_at TIMESTAMPTZ NOT NULL,
    problem_snapshot_evidence_id TEXT NULL,
    reason_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_resource_id, source_instance_generation),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    FOREIGN KEY (tenant_id, problem_snapshot_evidence_id)
        REFERENCES monitoring.monitoring_problem_snapshot_evidence(tenant_id, problem_snapshot_evidence_id),
    CHECK (jsonb_typeof(reason_refs)='array'),
    CHECK (jsonb_array_length(reason_refs) <= 64),
    CHECK (octet_length(reason_refs::text) <= 65536),
    CHECK (last_evidence_at >= last_changed_at OR health_class IS NOT NULL)
);

COMMENT ON TABLE monitoring.health_projection IS
'Canonical Monitoring-owned derived Health Projection. It is not provider state, Alerting state, ITSM state or AIOps authority.';

CREATE TABLE monitoring.health_projection_transition (
    tenant_id TEXT NOT NULL,
    health_transition_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    from_health_class TEXT NULL
        CHECK (from_health_class IS NULL OR from_health_class IN ('unknown','healthy','degraded','unhealthy')),
    to_health_class TEXT NOT NULL
        CHECK (to_health_class IN ('unknown','healthy','degraded','unhealthy')),
    from_evidence_state TEXT NULL
        CHECK (from_evidence_state IS NULL OR from_evidence_state IN ('current','stale','incomplete','reconciliation_required','unavailable')),
    to_evidence_state TEXT NOT NULL
        CHECK (to_evidence_state IN ('current','stale','incomplete','reconciliation_required','unavailable')),
    projection_revision BIGINT NOT NULL CHECK (projection_revision > 0),
    problem_snapshot_evidence_id TEXT NULL,
    reason_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, health_transition_id),
    UNIQUE (tenant_id, monitoring_resource_id, source_instance_generation, projection_revision),
    FOREIGN KEY (tenant_id, monitoring_resource_id, source_instance_generation)
        REFERENCES monitoring.health_projection(tenant_id, monitoring_resource_id, source_instance_generation),
    FOREIGN KEY (tenant_id, problem_snapshot_evidence_id)
        REFERENCES monitoring.monitoring_problem_snapshot_evidence(tenant_id, problem_snapshot_evidence_id),
    CHECK (health_transition_id <> '' AND length(health_transition_id) <= 512),
    CHECK (jsonb_typeof(reason_refs)='array'),
    CHECK (jsonb_array_length(reason_refs) <= 64),
    CHECK (octet_length(reason_refs::text) <= 65536)
);

ALTER TABLE monitoring.health_projection ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.health_projection FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.health_projection_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.health_projection_transition FORCE ROW LEVEL SECURITY;

CREATE POLICY health_projection_tenant_policy
ON monitoring.health_projection
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

CREATE POLICY health_projection_transition_tenant_policy
ON monitoring.health_projection_transition
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

REVOKE ALL ON monitoring.health_projection,
    monitoring.health_projection_transition FROM PUBLIC;

GRANT SELECT ON monitoring.monitoring_source,
    monitoring.monitoring_source_generation,
    monitoring.monitoring_resource,
    monitoring.monitoring_problem,
    monitoring.monitoring_problem_snapshot_evidence,
    monitoring.health_projection
TO jlmirror_wave4_health_projection_executor;

GRANT SELECT, INSERT, UPDATE ON monitoring.health_projection
TO jlmirror_wave4_health_projection_executor;
GRANT SELECT, INSERT ON monitoring.health_projection_transition
TO jlmirror_wave4_health_projection_executor;

CREATE OR REPLACE FUNCTION monitoring.wave4_health_projection_executor_is_current_user()
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
    SELECT current_user='jlmirror_wave4_health_projection_executor'
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_health_projection_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT monitoring.wave4_health_projection_executor_is_current_user() THEN
        RAISE EXCEPTION 'Health projection mutation requires guarded Health executor authority';
    END IF;

    IF TG_OP='UPDATE' AND (
        NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
        OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
        OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
        OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
    ) THEN
        RAISE EXCEPTION 'Health projection ownership and canonical identity are immutable';
    END IF;

    IF TG_OP='UPDATE' AND NEW.projection_revision <> OLD.projection_revision + 1 THEN
        RAISE EXCEPTION 'Health projection revision must advance exactly once';
    END IF;

    IF NEW.health_class='healthy' THEN
        IF NEW.evidence_state <> 'current' OR NEW.problem_snapshot_evidence_id IS NULL THEN
            RAISE EXCEPTION 'Healthy requires current evidence and durable Problem State completeness evidence';
        END IF;
        IF NOT EXISTS (
            SELECT 1
              FROM monitoring.monitoring_problem_snapshot_evidence AS e
             WHERE e.tenant_id=NEW.tenant_id
               AND e.problem_snapshot_evidence_id=NEW.problem_snapshot_evidence_id
               AND e.monitoring_source_id=NEW.monitoring_source_id
               AND e.source_instance_generation=NEW.source_instance_generation
               AND e.snapshot_complete
               AND e.operation_state='succeeded'
               AND e.operational_evidence_state='current'
        ) THEN
            RAISE EXCEPTION 'Healthy Problem State completeness evidence is not authoritative';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER health_projection_guard
BEFORE INSERT OR UPDATE ON monitoring.health_projection
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_health_projection_mutation();

CREATE OR REPLACE FUNCTION monitoring.wave4_reject_health_transition_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    RAISE EXCEPTION 'Health projection transition evidence is immutable';
END;
$$;

CREATE TRIGGER health_projection_transition_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.health_projection_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_health_transition_mutation();

COMMIT;
