-- Wave 4 Metric Current State recovery privilege bridge.
--
-- Recovery owns Current poll-epoch advancement, but it must also be able to
-- retire an already-running claim from the superseded epoch.  The semantic
-- transition is already constrained by wave4_guard_metric_current_state_operation
-- (migration 034); this migration grants only the physical columns required by
-- that exact transition.  It deliberately does NOT grant table-wide UPDATE.

BEGIN;

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

-- Prove at migration time that the recovery role did not accidentally acquire
-- table-wide UPDATE authority.  Column privileges plus migration-034's trigger
-- are the intended two-layer boundary.
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
