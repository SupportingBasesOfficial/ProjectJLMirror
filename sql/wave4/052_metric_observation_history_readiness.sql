-- Formalises two schema changes that were applied manually to the dev DB on
-- 2026-10-23 and are required for the /current and /history monitoring endpoints.
--
-- 1. has_delta_preprocessing on metric_definition — referenced by monitoring_repo.py
--    (list_resource_current_states). Without it the endpoint returns 500.
-- 2. idx_metric_observation_history — covers the history query pattern
--    (tenant_id, monitoring_source_id, metric_definition_id, observed_at DESC).
--    Without it the query sequential-scans the full metric_observation table.

BEGIN;

ALTER TABLE monitoring.metric_definition
    ADD COLUMN IF NOT EXISTS has_delta_preprocessing BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_metric_observation_history
    ON monitoring.metric_observation (
        tenant_id,
        monitoring_source_id,
        metric_definition_id,
        observed_at DESC,
        observation_id DESC,
        provider_clock
    );

COMMIT;
