-- Wave 4 host-inventory claimed revision authority hardening.
-- Once Host Inventory work has been claimed, the source ownership and revision
-- tuple captured by that claim is immutable. Completion must evaluate the exact
-- authority under which the provider read began; callers may not rewrite a
-- running operation onto newer source/configuration/scope authority.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_claim_revision_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, monitoring AS $$
BEGIN
    IF OLD.responsibility_kind = 'host_inventory_sync'
       AND OLD.state = 'running'
       AND (
           NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
           OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
       ) THEN
        RAISE EXCEPTION 'Claimed host inventory source/revision authority is immutable';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_inventory_claim_revision_update_guard
    ON monitoring.monitoring_sync_operation;
CREATE TRIGGER wave4_host_inventory_claim_revision_update_guard
BEFORE UPDATE ON monitoring.monitoring_sync_operation
FOR EACH ROW
EXECUTE FUNCTION monitoring.wave4_guard_host_inventory_claim_revision_update();

COMMIT;
