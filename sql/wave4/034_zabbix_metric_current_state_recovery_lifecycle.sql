-- Permit only the exact recovery-owned terminalization required when a Current poll epoch advances.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_current_state_operation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='INSERT' AND NEW.responsibility_kind='metric_current_state_sync' THEN
        IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() THEN
            RAISE EXCEPTION 'Metric Current State work creation requires guarded executor authority';
        END IF;
        IF NEW.state <> 'pending' OR NEW.claim_token IS NOT NULL
           OR NEW.current_state_poll_epoch IS NOT NULL
           OR NEW.current_state_poll_generation IS NOT NULL
           OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL
           OR NEW.last_error_class IS NOT NULL OR NEW.attempt_count <> 0 THEN
            RAISE EXCEPTION 'Metric Current State operation must begin as clean pending work';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP='UPDATE' AND OLD.responsibility_kind='metric_current_state_sync' THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.monitoring_sync_operation_id IS DISTINCT FROM OLD.monitoring_sync_operation_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
           OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
           OR NEW.responsibility_kind IS DISTINCT FROM OLD.responsibility_kind THEN
            RAISE EXCEPTION 'Metric Current State work identity/source/revision authority is immutable';
        END IF;
        IF OLD.state IN ('succeeded','reconciliation_required','failed_terminal') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Terminal Metric Current State operation is immutable';
        END IF;
        IF OLD.current_state_poll_epoch IS NOT NULL
           AND NEW.current_state_poll_epoch IS DISTINCT FROM OLD.current_state_poll_epoch THEN
            RAISE EXCEPTION 'Claimed Metric Current State poll epoch is immutable';
        END IF;
        IF OLD.current_state_poll_generation IS NOT NULL
           AND NEW.current_state_poll_generation IS DISTINCT FROM OLD.current_state_poll_generation THEN
            RAISE EXCEPTION 'Claimed Metric Current State poll generation is immutable';
        END IF;

        IF current_user='jlmirror_wave4_recovery_authority' THEN
            IF NOT (
                OLD.state='running'
                AND NEW.state='reconciliation_required'
                AND NEW.claim_token IS NULL
                AND NEW.completed_at IS NOT NULL
                AND NEW.last_error_class='execution.superseded_current_state_poll_authority'
                AND NEW.started_at IS NOT DISTINCT FROM OLD.started_at
                AND NEW.attempt_count IS NOT DISTINCT FROM OLD.attempt_count
            ) THEN
                RAISE EXCEPTION 'Recovery authority may only terminalize superseded Metric Current State claims';
            END IF;
            RETURN NEW;
        END IF;

        IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Metric Current State lifecycle requires guarded executor authority';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
