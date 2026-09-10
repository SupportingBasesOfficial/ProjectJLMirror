-- Ensure resources first observed after a recovery/placement epoch transition carry
-- the current epoch rather than the bootstrap column default.
BEGIN;
CREATE OR REPLACE FUNCTION monitoring.wave4_set_new_resource_poll_epoch()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_epoch BIGINT;
BEGIN
    IF NEW.resource_kind='host' AND NEW.provider_object_kind='zabbix_host' THEN
        IF NOT monitoring.wave4_host_inventory_executor_is_current_user() THEN
            RAISE EXCEPTION 'New Zabbix monitoring resources require guarded host-inventory executor';
        END IF;
        SELECT s.host_inventory_poll_epoch INTO v_epoch
          FROM monitoring.monitoring_source AS s
         WHERE s.tenant_id=NEW.tenant_id
           AND s.monitoring_source_id=NEW.monitoring_source_id;
        IF v_epoch IS NULL THEN
            RAISE EXCEPTION 'New monitoring resource source poll epoch missing';
        END IF;
        NEW.last_confirmed_present_poll_epoch := v_epoch;
        IF NEW.presence_state='removed' THEN
            NEW.removed_poll_epoch := v_epoch;
        ELSE
            NEW.removed_poll_epoch := NULL;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_monitoring_resource_insert_epoch_guard ON monitoring.monitoring_resource;
CREATE TRIGGER wave4_monitoring_resource_insert_epoch_guard
BEFORE INSERT ON monitoring.monitoring_resource
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_set_new_resource_poll_epoch();
COMMIT;
