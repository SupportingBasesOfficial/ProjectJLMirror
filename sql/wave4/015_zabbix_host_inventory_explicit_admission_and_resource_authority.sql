-- Wave 4 host-inventory explicit-admission and resource-authority hardening.
-- Closes PR #135 review findings that showed:
-- 1. an INSERT/COPY of monitoring_source could implicitly bootstrap polling authority; and
-- 2. provider-derived resource timestamps remained directly caller-writable.
--
-- New rule: source creation/recreation never grants current-state poll authority as a
-- side effect. Admission is an explicit trusted recovery/placement action. All
-- host-inventory-derived mutable projection fields are owned by the guarded executor.

BEGIN;

-- A restored/copied/reintroduced source row must not self-admit merely because INSERT
-- fired. Existing live admission rows created by migration 012 remain valid for the
-- deployment in which 012 ran; after loss of the UNLOGGED admission surface the
-- trusted recovery authority must explicitly establish a successor epoch.
DROP TRIGGER IF EXISTS wave4_host_inventory_runtime_admission_bootstrap
    ON monitoring.monitoring_source;
DROP FUNCTION IF EXISTS monitoring.wave4_bootstrap_host_inventory_runtime_admission();

-- Protect the entire mutable provider-derived host-inventory projection, rather than
-- only the particular timestamp named by the review. This makes direct same-tenant
-- UPDATE incapable of laundering freshness, scope, presence, provider identity
-- evidence, or display metadata.
CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_resource_projection_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF (
        NEW.display_name IS DISTINCT FROM OLD.display_name
        OR NEW.scope_state IS DISTINCT FROM OLD.scope_state
        OR NEW.scope_projection_revision IS DISTINCT FROM OLD.scope_projection_revision
        OR NEW.scope_evidence_state IS DISTINCT FROM OLD.scope_evidence_state
        OR NEW.presence_state IS DISTINCT FROM OLD.presence_state
        OR NEW.presence_evidence_state IS DISTINCT FROM OLD.presence_evidence_state
        OR NEW.last_observed_at IS DISTINCT FROM OLD.last_observed_at
        OR NEW.last_confirmed_present_at IS DISTINCT FROM OLD.last_confirmed_present_at
        OR NEW.removed_at IS DISTINCT FROM OLD.removed_at
        OR NEW.last_confirmed_present_poll_generation IS DISTINCT FROM OLD.last_confirmed_present_poll_generation
        OR NEW.last_confirmed_present_poll_epoch IS DISTINCT FROM OLD.last_confirmed_present_poll_epoch
        OR NEW.removed_poll_generation IS DISTINCT FROM OLD.removed_poll_generation
        OR NEW.removed_poll_epoch IS DISTINCT FROM OLD.removed_poll_epoch
        OR NEW.latest_provider_evidence_id IS DISTINCT FROM OLD.latest_provider_evidence_id
    ) AND NOT monitoring.wave4_host_inventory_executor_is_current_user() THEN
        RAISE EXCEPTION 'Monitoring resource authority fields require guarded host-inventory executor';
    END IF;

    -- Keep the temporal facts monotonic even on the trusted executor path.
    IF NEW.last_observed_at < OLD.last_observed_at
       OR NEW.last_confirmed_present_at < OLD.last_confirmed_present_at THEN
        RAISE EXCEPTION 'Monitoring resource observation timestamps cannot regress';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_inventory_resource_projection_update_guard
    ON monitoring.monitoring_resource;
CREATE TRIGGER wave4_host_inventory_resource_projection_update_guard
BEFORE UPDATE ON monitoring.monitoring_resource
FOR EACH ROW
EXECUTE FUNCTION monitoring.wave4_guard_host_inventory_resource_projection_update();

REVOKE ALL ON FUNCTION monitoring.wave4_guard_host_inventory_resource_projection_update() FROM PUBLIC;

COMMIT;
