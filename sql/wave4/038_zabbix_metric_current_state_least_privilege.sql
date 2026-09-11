-- Narrow Metric Current State privileges to the exact Current poll/recovery surfaces.
--
-- The executor may advance only its Current poll generation bookkeeping.
-- Recovery owns Current epoch advancement but receives NO direct DML authority on
-- monitoring_sync_operation.  Superseded-claim retirement crosses a narrowly
-- scoped SECURITY DEFINER helper owned by the Current executor.

BEGIN;

REVOKE INSERT,UPDATE ON monitoring.monitoring_source
    FROM jlmirror_wave4_metric_current_state_executor;
GRANT SELECT ON monitoring.monitoring_source
    TO jlmirror_wave4_metric_current_state_executor;
GRANT UPDATE (current_state_poll_generation,updated_at)
    ON monitoring.monitoring_source
    TO jlmirror_wave4_metric_current_state_executor;

-- Recovery authority alone owns epoch advancement for this stream.
GRANT UPDATE (current_state_poll_epoch,updated_at)
    ON monitoring.monitoring_source
    TO jlmirror_wave4_recovery_authority;

-- Do not allow recovery to mutate arbitrary operation rows merely because the
-- desired Current transition touches only a few lifecycle columns.
REVOKE ALL ON monitoring.monitoring_sync_operation
    FROM jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.wave4_terminalize_superseded_metric_current_state_claims(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_current_poll_epoch BIGINT
) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_count BIGINT;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id=''
       OR p_monitoring_source_id IS NULL OR p_monitoring_source_id=''
       OR p_current_poll_epoch IS NULL OR p_current_poll_epoch<=0 THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_recovery_terminalization_input';
    END IF;

    WITH retired AS (
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',
               completed_at=transaction_timestamp(),
               last_error_class='execution.superseded_current_state_poll_authority',
               claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_source_id=p_monitoring_source_id
           AND o.responsibility_kind='metric_current_state_sync'
           AND o.state='running'
           AND o.current_state_poll_epoch=p_current_poll_epoch
         RETURNING 1
    )
    SELECT count(*) INTO v_count FROM retired;
    RETURN v_count;
END;
$$;
ALTER FUNCTION monitoring.wave4_terminalize_superseded_metric_current_state_claims(TEXT,TEXT,BIGINT)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.wave4_terminalize_superseded_metric_current_state_claims(TEXT,TEXT,BIGINT)
    FROM PUBLIC, jlmirror_wave4_metric_current_state_invoker;
GRANT EXECUTE ON FUNCTION monitoring.wave4_terminalize_superseded_metric_current_state_claims(TEXT,TEXT,BIGINT)
    TO jlmirror_wave4_recovery_authority;

-- Migration-time negative assurance: recovery must not acquire direct operation
-- table/column mutation privileges.  The helper above is the sole lifecycle bridge.
DO $$
BEGIN
    IF has_table_privilege(
        'jlmirror_wave4_recovery_authority',
        'monitoring.monitoring_sync_operation',
        'UPDATE'
    )
       OR has_column_privilege(
        'jlmirror_wave4_recovery_authority',
        'monitoring.monitoring_sync_operation',
        'state',
        'UPDATE'
    )
       OR has_column_privilege(
        'jlmirror_wave4_recovery_authority',
        'monitoring.monitoring_sync_operation',
        'claim_token',
        'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Metric Current State recovery authority must not hold direct monitoring_sync_operation UPDATE';
    END IF;
END;
$$;

COMMIT;
