-- Wave 4 Problem State final semantic hardening.
-- Preserve provider event time as immutable evidence while making platform
-- confirmation time reflect the accepted poll that actually reconfirmed activity.

BEGIN;

ALTER TABLE monitoring.monitoring_problem_snapshot_evidence
    ADD CONSTRAINT problem_snapshot_complete_below_provider_ceiling_check
    CHECK (NOT snapshot_complete OR active_problem_count < 20000);

ALTER TABLE monitoring.monitoring_problem
    ADD CONSTRAINT monitoring_problem_provider_metadata_object_check
    CHECK (jsonb_typeof(provider_metadata)='object'),
    ADD CONSTRAINT monitoring_problem_resolution_not_before_open_check
    CHECK (resolved_at IS NULL OR resolved_at >= opened_at);

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_problem_confirmation_semantics()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='UPDATE' AND NEW.opened_at IS DISTINCT FROM OLD.opened_at THEN
        RAISE EXCEPTION 'Problem opened_at provider evidence is immutable';
    END IF;

    -- last_confirmed_at is platform acceptance/confirmation time, not a copy of
    -- provider opened_at.  Any accepted active projection written by a newly
    -- authoritative Problem poll is reconfirmed at this transaction boundary.
    IF NEW.problem_state='active'
       AND (
           TG_OP='INSERT'
           OR NEW.problem_poll_epoch IS DISTINCT FROM OLD.problem_poll_epoch
           OR NEW.problem_poll_generation IS DISTINCT FROM OLD.problem_poll_generation
       ) THEN
        NEW.last_confirmed_at:=transaction_timestamp();
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER problem_confirmation_semantics_guard
BEFORE INSERT OR UPDATE ON monitoring.monitoring_problem
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_problem_confirmation_semantics();

COMMIT;
