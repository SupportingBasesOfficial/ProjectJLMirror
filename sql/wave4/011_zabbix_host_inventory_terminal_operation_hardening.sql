-- Wave 4 host-inventory terminal-operation hardening.
-- A terminal host-inventory operation is immutable. Retry/reconciliation must create
-- a new operation rather than reopening authority that already closed a snapshot.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_sync_operation_poll_generation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF OLD.responsibility_kind='host_inventory_sync'
       AND OLD.state IN ('succeeded','reconciliation_required','failed_terminal')
       AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Terminal host inventory operation is immutable';
    END IF;

    IF OLD.responsibility_kind='host_inventory_sync'
       AND NEW.responsibility_kind IS DISTINCT FROM OLD.responsibility_kind THEN
        RAISE EXCEPTION 'Host inventory operation responsibility is immutable';
    END IF;

    IF OLD.responsibility_kind='host_inventory_sync'
       AND OLD.host_inventory_poll_generation IS NOT NULL
       AND NEW.host_inventory_poll_generation IS DISTINCT FROM OLD.host_inventory_poll_generation THEN
        RAISE EXCEPTION 'Host inventory operation poll generation is immutable after claim';
    END IF;

    IF OLD.responsibility_kind='host_inventory_sync'
       AND OLD.host_inventory_poll_generation IS NULL
       AND NEW.host_inventory_poll_generation IS NOT NULL
       AND NOT (OLD.state='pending' AND NEW.state='running' AND NEW.claim_token IS NOT NULL) THEN
        RAISE EXCEPTION 'Host inventory operation poll generation may be assigned only by claim transition';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
