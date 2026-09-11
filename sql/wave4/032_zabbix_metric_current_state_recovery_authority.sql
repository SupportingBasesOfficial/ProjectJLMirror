-- Wave 4 Metric Current State recovery/readmission authority.
-- Concrete mutable authority remains stream-local; only the accepted recovery laws are reused.
-- The lifecycle mutation itself is delegated to a narrowly-scoped SECURITY DEFINER
-- helper installed by the final least-privilege migration; recovery receives no
-- direct monitoring_sync_operation DML authority.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.reestablish_metric_current_state_runtime_admission(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_successor_poll_epoch BIGINT,
    p_placement_version TEXT,
    p_recovery_generation TEXT,
    p_recovery_admission_ref TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_current_epoch BIGINT;
BEGIN
    IF p_successor_poll_epoch IS NULL OR p_successor_poll_epoch<=0
       OR p_placement_version IS NULL OR p_placement_version=''
       OR p_recovery_generation IS NULL OR p_recovery_generation=''
       OR p_recovery_admission_ref IS NULL OR p_recovery_admission_ref='' THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_recovery_admission';
    END IF;

    SELECT s.current_state_poll_epoch INTO v_current_epoch
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=p_monitoring_source_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_recovery_source_missing';
    END IF;
    IF p_successor_poll_epoch<=v_current_epoch THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_recovery_epoch_must_advance';
    END IF;

    -- The final schema installs this helper with executor ownership and grants
    -- EXECUTE only to recovery authority.  Recovery never receives generic DML
    -- privileges on monitoring_sync_operation.
    PERFORM monitoring.wave4_terminalize_superseded_metric_current_state_claims(
        p_tenant_id,p_monitoring_source_id,v_current_epoch
    );

    UPDATE monitoring.monitoring_source AS s
       SET current_state_poll_epoch=p_successor_poll_epoch,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=p_monitoring_source_id;

    INSERT INTO monitoring.monitoring_metric_current_state_runtime_admission(
        tenant_id,monitoring_source_id,current_state_poll_epoch,
        placement_version,recovery_generation,recovery_admission_ref
    ) VALUES (
        p_tenant_id,p_monitoring_source_id,p_successor_poll_epoch,
        p_placement_version,p_recovery_generation,p_recovery_admission_ref
    )
    ON CONFLICT (tenant_id,monitoring_source_id) DO UPDATE
       SET current_state_poll_epoch=EXCLUDED.current_state_poll_epoch,
           placement_version=EXCLUDED.placement_version,
           recovery_generation=EXCLUDED.recovery_generation,
           recovery_admission_ref=EXCLUDED.recovery_admission_ref,
           admitted_at=transaction_timestamp();
END;
$$;
ALTER FUNCTION monitoring.reestablish_metric_current_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_recovery_authority;
REVOKE EXECUTE ON FUNCTION monitoring.reestablish_metric_current_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    FROM PUBLIC, jlmirror_wave4_metric_current_state_invoker, jlmirror_wave4_metric_current_state_executor;
GRANT EXECUTE ON FUNCTION monitoring.reestablish_metric_current_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

COMMIT;
