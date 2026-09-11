-- Narrow Metric Current State executor privileges on monitoring_source to its own poll stream.

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

COMMIT;
