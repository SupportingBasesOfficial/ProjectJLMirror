-- Wave 4 Problem State recovery-safe epoch advancement and stale-claim fencing.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_terminalize_superseded_problem_state_claims(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_superseded_poll_epoch BIGINT
) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_count BIGINT;
BEGIN
    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='reconciliation_required',completed_at=transaction_timestamp(),
           last_error_class='execution.superseded_problem_state_poll_authority',
           claim_token=NULL
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_source_id=p_monitoring_source_id
       AND o.responsibility_kind IN ('problem_state_sync','problem_state_reconciliation')
       AND o.state='running'
       AND o.problem_poll_epoch=p_superseded_poll_epoch;
    GET DIAGNOSTICS v_count=ROW_COUNT;
    RETURN v_count;
END;
$$;
ALTER FUNCTION monitoring.wave4_terminalize_superseded_problem_state_claims(TEXT,TEXT,BIGINT)
    OWNER TO jlmirror_wave4_problem_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.wave4_terminalize_superseded_problem_state_claims(TEXT,TEXT,BIGINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.wave4_terminalize_superseded_problem_state_claims(TEXT,TEXT,BIGINT)
    TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.reestablish_problem_state_runtime_admission(
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
        RAISE EXCEPTION 'monitoring.problem_state_invalid_recovery_admission';
    END IF;

    SELECT s.problem_poll_epoch INTO v_current_epoch
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=p_monitoring_source_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.problem_state_recovery_source_missing';
    END IF;
    IF p_successor_poll_epoch<=v_current_epoch THEN
        RAISE EXCEPTION 'monitoring.problem_state_recovery_epoch_must_advance';
    END IF;

    PERFORM monitoring.wave4_terminalize_superseded_problem_state_claims(
        p_tenant_id,p_monitoring_source_id,v_current_epoch
    );

    UPDATE monitoring.monitoring_source AS s
       SET problem_poll_epoch=p_successor_poll_epoch,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=p_monitoring_source_id;

    INSERT INTO monitoring.monitoring_problem_state_runtime_admission(
        tenant_id,monitoring_source_id,problem_poll_epoch,
        placement_version,recovery_generation,recovery_admission_ref
    ) VALUES (
        p_tenant_id,p_monitoring_source_id,p_successor_poll_epoch,
        p_placement_version,p_recovery_generation,p_recovery_admission_ref
    )
    ON CONFLICT (tenant_id,monitoring_source_id) DO UPDATE
       SET problem_poll_epoch=EXCLUDED.problem_poll_epoch,
           placement_version=EXCLUDED.placement_version,
           recovery_generation=EXCLUDED.recovery_generation,
           recovery_admission_ref=EXCLUDED.recovery_admission_ref,
           admitted_at=transaction_timestamp();
END;
$$;
ALTER FUNCTION monitoring.reestablish_problem_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_recovery_authority;
REVOKE EXECUTE ON FUNCTION monitoring.reestablish_problem_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    FROM PUBLIC,jlmirror_wave4_problem_state_invoker,jlmirror_wave4_problem_state_executor;
GRANT EXECUTE ON FUNCTION monitoring.reestablish_problem_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

-- Recovery owns epoch advancement; ordinary Problem executor may advance only the
-- within-epoch poll generation through its sealed claim function.
REVOKE UPDATE ON monitoring.monitoring_source FROM jlmirror_wave4_problem_state_executor;
GRANT UPDATE (problem_poll_generation,updated_at) ON monitoring.monitoring_source
TO jlmirror_wave4_problem_state_executor;
GRANT UPDATE (problem_poll_epoch,updated_at) ON monitoring.monitoring_source
TO jlmirror_wave4_recovery_authority;

COMMIT;
