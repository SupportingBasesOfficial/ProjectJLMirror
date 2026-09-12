-- Wave 4 Health Projection defense-in-depth: current evidence must bind the
-- exact currently authoritative Problem State poll, not merely matching scope/config revisions.

BEGIN;

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

    IF NEW.evidence_state='current' THEN
        IF NEW.problem_snapshot_evidence_id IS NULL OR NOT EXISTS (
            SELECT 1
              FROM monitoring.monitoring_problem_snapshot_evidence AS e
              JOIN monitoring.monitoring_source AS s
                ON s.tenant_id=e.tenant_id
               AND s.monitoring_source_id=e.monitoring_source_id
              JOIN monitoring.monitoring_resource AS r
                ON r.tenant_id=NEW.tenant_id
               AND r.monitoring_resource_id=NEW.monitoring_resource_id
             WHERE e.tenant_id=NEW.tenant_id
               AND e.problem_snapshot_evidence_id=NEW.problem_snapshot_evidence_id
               AND e.monitoring_source_id=NEW.monitoring_source_id
               AND e.source_instance_generation=NEW.source_instance_generation
               AND e.snapshot_complete
               AND e.operation_state='succeeded'
               AND e.operational_evidence_state='current'
               AND s.active_source_instance_generation=NEW.source_instance_generation
               AND s.configuration_revision=e.configuration_revision
               AND s.scope_revision=e.scope_revision
               AND s.problem_poll_epoch=e.problem_poll_epoch
               AND s.problem_poll_generation=e.problem_poll_generation
               AND s.operational_evidence_state='current'
               AND r.monitoring_source_id=NEW.monitoring_source_id
               AND r.source_instance_generation=NEW.source_instance_generation
               AND r.presence_state='present'
               AND r.presence_evidence_state='current'
               AND r.scope_state='in_scope'
               AND r.scope_evidence_state='current'
               AND r.scope_projection_revision=e.scope_revision
        ) THEN
            RAISE EXCEPTION 'Current Health requires exact current Problem State poll and current source/resource/scope authority';
        END IF;
    END IF;

    IF NEW.health_class='healthy' THEN
        IF NEW.evidence_state <> 'current' THEN
            RAISE EXCEPTION 'Healthy cannot be projected from non-current evidence';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM monitoring.monitoring_problem AS p
             WHERE p.tenant_id=NEW.tenant_id
               AND p.monitoring_source_id=NEW.monitoring_source_id
               AND p.source_instance_generation=NEW.source_instance_generation
               AND p.monitoring_resource_id=NEW.monitoring_resource_id
               AND p.problem_state='active'
               AND p.severity_class IN ('unknown','warning','degraded','critical')
        ) THEN
            RAISE EXCEPTION 'Healthy cannot coexist with an active health-affecting canonical problem';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
