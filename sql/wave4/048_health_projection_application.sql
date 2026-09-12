-- Wave 4 Health Projection transactional recomputation.
-- Caller supplies only canonical subject + transition identity; health class is derived in PostgreSQL.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.recompute_health_projection(
    p_tenant_id TEXT,
    p_monitoring_resource_id TEXT,
    p_health_transition_id TEXT
) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_active_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_source_evidence TEXT;
    v_problem_poll_epoch BIGINT;
    v_problem_poll_generation BIGINT;
    v_presence_state TEXT;
    v_presence_evidence TEXT;
    v_scope_state TEXT;
    v_scope_evidence TEXT;
    v_scope_projection_revision BIGINT;
    v_snapshot_id TEXT;
    v_snapshot_count BIGINT;
    v_snapshot_complete BOOLEAN := FALSE;
    v_snapshot_state TEXT;
    v_health TEXT;
    v_evidence TEXT;
    v_reason_refs JSONB := '[]'::jsonb;
    v_existing monitoring.health_projection%ROWTYPE;
    v_revision BIGINT;
    v_now TIMESTAMPTZ := transaction_timestamp();
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR p_monitoring_resource_id IS NULL OR p_monitoring_resource_id=''
       OR p_health_transition_id IS NULL OR p_health_transition_id='' OR length(p_health_transition_id)>512 THEN
        RAISE EXCEPTION 'monitoring.health_projection_invalid_input';
    END IF;

    PERFORM set_config('jlmirror.tenant_id', p_tenant_id, true);

    SELECT r.monitoring_source_id, r.source_instance_generation,
           s.active_source_instance_generation, s.configuration_revision, s.scope_revision,
           s.operational_evidence_state, s.problem_poll_epoch, s.problem_poll_generation,
           r.presence_state, r.presence_evidence_state, r.scope_state,
           r.scope_evidence_state, r.scope_projection_revision
      INTO v_source_id, v_generation, v_active_generation,
           v_configuration_revision, v_scope_revision, v_source_evidence,
           v_problem_poll_epoch, v_problem_poll_generation,
           v_presence_state, v_presence_evidence, v_scope_state,
           v_scope_evidence, v_scope_projection_revision
      FROM monitoring.monitoring_resource AS r
      JOIN monitoring.monitoring_source AS s
        ON s.tenant_id=r.tenant_id
       AND s.monitoring_source_id=r.monitoring_source_id
     WHERE r.tenant_id=p_tenant_id
       AND r.monitoring_resource_id=p_monitoring_resource_id
     FOR UPDATE OF r,s;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.health_projection_resource_not_found';
    END IF;

    -- Historical generations preserve their retained last-known projection. A later
    -- recomputation cannot make them current again.
    IF v_generation <> v_active_generation THEN
        RAISE EXCEPTION 'monitoring.health_projection_historical_generation';
    END IF;

    SELECT count(*), min(e.problem_snapshot_evidence_id), bool_and(e.snapshot_complete), min(e.operational_evidence_state)
      INTO v_snapshot_count, v_snapshot_id, v_snapshot_complete, v_snapshot_state
      FROM monitoring.monitoring_problem_snapshot_evidence AS e
     WHERE e.tenant_id=p_tenant_id
       AND e.monitoring_source_id=v_source_id
       AND e.source_instance_generation=v_generation
       AND e.configuration_revision=v_configuration_revision
       AND e.scope_revision=v_scope_revision
       AND e.problem_poll_epoch=v_problem_poll_epoch
       AND e.problem_poll_generation=v_problem_poll_generation;

    IF v_snapshot_count > 1 THEN
        RAISE EXCEPTION 'monitoring.health_projection_ambiguous_problem_completeness';
    END IF;

    SELECT COALESCE(jsonb_agg(x.problem_id ORDER BY x.problem_id), '[]'::jsonb)
      INTO v_reason_refs
      FROM (
        SELECT p.problem_id
          FROM monitoring.monitoring_problem AS p
         WHERE p.tenant_id=p_tenant_id
           AND p.monitoring_source_id=v_source_id
           AND p.source_instance_generation=v_generation
           AND p.monitoring_resource_id=p_monitoring_resource_id
           AND p.problem_state='active'
           AND p.severity_class IN ('unknown','warning','degraded','critical')
         ORDER BY p.problem_id
         LIMIT 64
      ) AS x;

    IF EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem AS p
         WHERE p.tenant_id=p_tenant_id
           AND p.monitoring_source_id=v_source_id
           AND p.source_instance_generation=v_generation
           AND p.monitoring_resource_id=p_monitoring_resource_id
           AND p.problem_state='active'
           AND p.severity_class='critical'
    ) THEN
        v_health := 'unhealthy';
    ELSIF EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem AS p
         WHERE p.tenant_id=p_tenant_id
           AND p.monitoring_source_id=v_source_id
           AND p.source_instance_generation=v_generation
           AND p.monitoring_resource_id=p_monitoring_resource_id
           AND p.problem_state='active'
           AND p.severity_class IN ('warning','degraded')
    ) THEN
        v_health := 'degraded';
    ELSIF EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem AS p
         WHERE p.tenant_id=p_tenant_id
           AND p.monitoring_source_id=v_source_id
           AND p.source_instance_generation=v_generation
           AND p.monitoring_resource_id=p_monitoring_resource_id
           AND p.problem_state='active'
           AND p.severity_class='unknown'
    ) THEN
        v_health := 'unknown';
    ELSE
        v_health := 'unknown';
    END IF;

    IF v_source_evidence='current'
       AND v_presence_state='present'
       AND v_presence_evidence='current'
       AND v_scope_state='in_scope'
       AND v_scope_evidence='current'
       AND v_scope_projection_revision=v_scope_revision
       AND v_snapshot_count=1
       AND v_snapshot_complete
       AND v_snapshot_state='current' THEN
        v_evidence := 'current';
        IF v_health='unknown' AND NOT EXISTS (
            SELECT 1 FROM monitoring.monitoring_problem AS p
             WHERE p.tenant_id=p_tenant_id
               AND p.monitoring_source_id=v_source_id
               AND p.source_instance_generation=v_generation
               AND p.monitoring_resource_id=p_monitoring_resource_id
               AND p.problem_state='active'
               AND p.severity_class='unknown'
        ) THEN
            -- No critical/warning/degraded/unknown problem remains; informational-only is healthy.
            v_health := 'healthy';
        END IF;
    ELSE
        v_evidence := CASE
            WHEN v_source_evidence='unavailable' OR v_presence_evidence='unavailable' THEN 'unavailable'
            WHEN v_source_evidence='stale' THEN 'stale'
            WHEN v_source_evidence='incomplete' OR v_presence_evidence='incomplete' THEN 'incomplete'
            ELSE 'reconciliation_required'
        END;
    END IF;

    SELECT * INTO v_existing
      FROM monitoring.health_projection
     WHERE tenant_id=p_tenant_id
       AND monitoring_resource_id=p_monitoring_resource_id
       AND source_instance_generation=v_generation
     FOR UPDATE;

    IF NOT FOUND THEN
        v_revision := 1;
        INSERT INTO monitoring.health_projection(
            tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
            health_class,evidence_state,projection_revision,last_changed_at,last_evidence_at,
            problem_snapshot_evidence_id,reason_refs
        ) VALUES (
            p_tenant_id,p_monitoring_resource_id,v_source_id,v_generation,
            v_health,v_evidence,v_revision,v_now,v_now,v_snapshot_id,v_reason_refs
        );

        INSERT INTO monitoring.health_projection_transition(
            tenant_id,health_transition_id,monitoring_resource_id,monitoring_source_id,
            source_instance_generation,from_health_class,to_health_class,from_evidence_state,
            to_evidence_state,projection_revision,problem_snapshot_evidence_id,reason_refs
        ) VALUES (
            p_tenant_id,p_health_transition_id,p_monitoring_resource_id,v_source_id,
            v_generation,NULL,v_health,NULL,v_evidence,v_revision,v_snapshot_id,v_reason_refs
        );
        RETURN v_revision;
    END IF;

    IF v_existing.health_class=v_health
       AND v_existing.evidence_state=v_evidence
       AND v_existing.problem_snapshot_evidence_id IS NOT DISTINCT FROM v_snapshot_id
       AND v_existing.reason_refs=v_reason_refs THEN
        RETURN v_existing.projection_revision;
    END IF;

    v_revision := v_existing.projection_revision + 1;

    UPDATE monitoring.health_projection
       SET health_class=v_health,
           evidence_state=v_evidence,
           projection_revision=v_revision,
           last_changed_at=CASE WHEN v_existing.health_class IS DISTINCT FROM v_health THEN v_now ELSE v_existing.last_changed_at END,
           last_evidence_at=v_now,
           problem_snapshot_evidence_id=v_snapshot_id,
           reason_refs=v_reason_refs,
           updated_at=v_now
     WHERE tenant_id=p_tenant_id
       AND monitoring_resource_id=p_monitoring_resource_id
       AND source_instance_generation=v_generation;

    INSERT INTO monitoring.health_projection_transition(
        tenant_id,health_transition_id,monitoring_resource_id,monitoring_source_id,
        source_instance_generation,from_health_class,to_health_class,from_evidence_state,
        to_evidence_state,projection_revision,problem_snapshot_evidence_id,reason_refs
    ) VALUES (
        p_tenant_id,p_health_transition_id,p_monitoring_resource_id,v_source_id,
        v_generation,v_existing.health_class,v_health,v_existing.evidence_state,
        v_evidence,v_revision,v_snapshot_id,v_reason_refs
    );

    RETURN v_revision;
END;
$$;

ALTER FUNCTION monitoring.recompute_health_projection(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_health_projection_executor;
REVOKE EXECUTE ON FUNCTION monitoring.recompute_health_projection(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.recompute_health_projection(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_health_projection_invoker;

COMMIT;
