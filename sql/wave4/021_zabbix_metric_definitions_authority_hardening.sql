-- Wave 4 metric-definition authority hardening.
-- Closes first-pass review gaps in migration 020:
-- * provider evidence may be staged before snapshot closure only inside one transaction;
-- * negative retirement requires the owning canonical host to remain present/in-scope/current;
-- * post-recovery item polling requires an explicit trusted re-admission entrypoint.

BEGIN;

ALTER TABLE monitoring.monitoring_metric_definition_provider_evidence
    DROP CONSTRAINT monitoring_metric_definition_provider_evidence_metric_definition_snapshot_evidence_id_fkey;
ALTER TABLE monitoring.monitoring_metric_definition_provider_evidence
    ADD CONSTRAINT monitoring_metric_definition_provider_evidence_snapshot_fk
    FOREIGN KEY (tenant_id, metric_definition_snapshot_evidence_id)
    REFERENCES monitoring.monitoring_metric_definition_snapshot_evidence(tenant_id, metric_definition_snapshot_evidence_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE OR REPLACE FUNCTION monitoring.reestablish_metric_definition_runtime_admission(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_successor_poll_epoch BIGINT,
    p_placement_version TEXT,
    p_recovery_generation TEXT,
    p_recovery_admission_ref TEXT
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,monitoring
AS $$
DECLARE
    v_current_epoch BIGINT;
BEGIN
    IF p_successor_poll_epoch IS NULL OR p_successor_poll_epoch <= 0
       OR p_placement_version IS NULL OR p_placement_version=''
       OR p_recovery_generation IS NULL OR p_recovery_generation=''
       OR p_recovery_admission_ref IS NULL OR p_recovery_admission_ref='' THEN
        RAISE EXCEPTION 'monitoring.metric_definition_invalid_recovery_admission';
    END IF;

    SELECT item_definition_poll_epoch INTO v_current_epoch
      FROM monitoring.monitoring_source
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=p_monitoring_source_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_recovery_source_missing';
    END IF;
    IF p_successor_poll_epoch <= v_current_epoch THEN
        RAISE EXCEPTION 'monitoring.metric_definition_recovery_epoch_must_advance';
    END IF;

    UPDATE monitoring.monitoring_source
       SET item_definition_poll_epoch=p_successor_poll_epoch,
           updated_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=p_monitoring_source_id;

    INSERT INTO monitoring.monitoring_metric_definition_runtime_admission(
        tenant_id,monitoring_source_id,item_definition_poll_epoch,
        placement_version,recovery_generation,recovery_admission_ref
    ) VALUES (
        p_tenant_id,p_monitoring_source_id,p_successor_poll_epoch,
        p_placement_version,p_recovery_generation,p_recovery_admission_ref
    )
    ON CONFLICT (tenant_id,monitoring_source_id) DO UPDATE
       SET item_definition_poll_epoch=EXCLUDED.item_definition_poll_epoch,
           placement_version=EXCLUDED.placement_version,
           recovery_generation=EXCLUDED.recovery_generation,
           recovery_admission_ref=EXCLUDED.recovery_admission_ref,
           admitted_at=transaction_timestamp();
END;
$$;
ALTER FUNCTION monitoring.reestablish_metric_definition_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_recovery_authority;
REVOKE EXECUTE ON FUNCTION monitoring.reestablish_metric_definition_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    FROM PUBLIC, jlmirror_wave4_metric_definition_invoker, jlmirror_wave4_metric_definition_executor;
GRANT EXECUTE ON FUNCTION monitoring.reestablish_metric_definition_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

-- Replace completion so authoritative negative retirement also proves the owning host
-- remains a current, present, in-scope member of the same source/generation/scope domain.
CREATE OR REPLACE FUNCTION monitoring.wave4_retire_missing_metric_definitions(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_source_instance_generation TEXT,
    p_scope_revision BIGINT,
    p_poll_epoch BIGINT,
    p_poll_generation BIGINT,
    p_seen_provider_refs TEXT[]
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,monitoring
AS $$
DECLARE
    v_count BIGINT;
BEGIN
    IF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric definition retirement requires guarded executor authority';
    END IF;

    WITH retired AS (
        UPDATE monitoring.metric_definition d
           SET definition_state='retired',
               definition_evidence_state='current',
               retired_poll_epoch=p_poll_epoch,
               retired_poll_generation=p_poll_generation,
               updated_at=transaction_timestamp()
          FROM monitoring.metric_definition_provider_binding b,
               monitoring.monitoring_resource r
         WHERE d.tenant_id=p_tenant_id
           AND d.monitoring_source_id=p_monitoring_source_id
           AND d.source_instance_generation=p_source_instance_generation
           AND d.definition_state='active'
           AND d.scope_state='in_scope'
           AND d.scope_evidence_state='current'
           AND d.scope_projection_revision=p_scope_revision
           AND b.tenant_id=d.tenant_id
           AND b.metric_definition_id=d.metric_definition_id
           AND r.tenant_id=d.tenant_id
           AND r.monitoring_resource_id=d.monitoring_resource_id
           AND r.monitoring_source_id=p_monitoring_source_id
           AND r.source_instance_generation=p_source_instance_generation
           AND r.presence_state='present'
           AND r.presence_evidence_state='current'
           AND r.scope_state='in_scope'
           AND r.scope_evidence_state='current'
           AND r.scope_projection_revision=p_scope_revision
           AND NOT (b.provider_external_ref=ANY(p_seen_provider_refs))
         RETURNING 1
    ) SELECT count(*) INTO v_count FROM retired;
    RETURN v_count;
END;
$$;
ALTER FUNCTION monitoring.wave4_retire_missing_metric_definitions(TEXT,TEXT,TEXT,BIGINT,BIGINT,BIGINT,TEXT[])
    OWNER TO jlmirror_wave4_metric_definition_executor;
REVOKE EXECUTE ON FUNCTION monitoring.wave4_retire_missing_metric_definitions(TEXT,TEXT,TEXT,BIGINT,BIGINT,BIGINT,TEXT[])
    FROM PUBLIC, jlmirror_wave4_metric_definition_invoker;

COMMIT;
