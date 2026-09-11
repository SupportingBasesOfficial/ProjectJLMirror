-- Narrow Metric Current State privileges to the exact Current poll/recovery surfaces.
--
-- The executor may advance only its Current poll generation bookkeeping.
-- Recovery owns Current epoch advancement and may physically touch only the four
-- lifecycle columns required to retire a superseded running Current claim.  The
-- semantic shape of that transition remains enforced by migration 034's trigger;
-- table-wide monitoring_sync_operation UPDATE is intentionally never granted.

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

-- Physical privilege bridge for the exact recovery-owned terminalization from
-- migration 034.  SELECT is limited to columns needed by the bounded predicate;
-- UPDATE is limited to the four lifecycle columns that the trigger permits.
GRANT SELECT (
    tenant_id,
    monitoring_sync_operation_id,
    monitoring_source_id,
    responsibility_kind,
    state,
    current_state_poll_epoch
)
ON monitoring.monitoring_sync_operation
TO jlmirror_wave4_recovery_authority;

GRANT UPDATE (
    state,
    completed_at,
    last_error_class,
    claim_token
)
ON monitoring.monitoring_sync_operation
TO jlmirror_wave4_recovery_authority;

DO $$
BEGIN
    IF has_table_privilege(
        'jlmirror_wave4_recovery_authority',
        'monitoring.monitoring_sync_operation',
        'UPDATE'
    ) THEN
        RAISE EXCEPTION 'Metric Current State recovery authority must not hold table-wide monitoring_sync_operation UPDATE';
    END IF;
END;
$$;

COMMIT;
