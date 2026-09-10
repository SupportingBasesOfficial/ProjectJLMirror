-- Wave 4 host-inventory operation-insert authority hardening.
-- Closes PR #135 finding LEARN-PR135-021: same-tenant runtime writers must not
-- manufacture already-claimed host_inventory_sync rows or reuse an authoritative
-- source/epoch/generation tuple.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_operation_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.responsibility_kind = 'host_inventory_sync' THEN
        -- Enqueue may create work, but authority is assigned only by the guarded
        -- pending -> running claim transition. INSERT can never mint claimed work.
        IF NEW.state IS DISTINCT FROM 'pending'
           OR NEW.claim_token IS NOT NULL
           OR NEW.host_inventory_poll_generation IS NOT NULL
           OR NEW.host_inventory_poll_epoch IS NOT NULL
           OR NEW.host_inventory_snapshot_evidence_id IS NOT NULL THEN
            RAISE EXCEPTION 'Host inventory operation insert must be unclaimed pending work';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_inventory_operation_insert_guard
    ON monitoring.monitoring_sync_operation;
CREATE TRIGGER wave4_host_inventory_operation_insert_guard
BEFORE INSERT ON monitoring.monitoring_sync_operation
FOR EACH ROW
EXECUTE FUNCTION monitoring.wave4_guard_host_inventory_operation_insert();

REVOKE ALL ON FUNCTION monitoring.wave4_guard_host_inventory_operation_insert() FROM PUBLIC;

-- Poll authority is single-owner. Pending rows have NULL epoch/generation and are
-- intentionally outside this uniqueness domain; claim atomically assigns the tuple.
CREATE UNIQUE INDEX monitoring_sync_operation_host_inventory_poll_authority_uniq
    ON monitoring.monitoring_sync_operation(
        tenant_id,
        monitoring_source_id,
        host_inventory_poll_epoch,
        host_inventory_poll_generation
    )
    WHERE responsibility_kind = 'host_inventory_sync'
      AND host_inventory_poll_epoch IS NOT NULL
      AND host_inventory_poll_generation IS NOT NULL;

COMMIT;
