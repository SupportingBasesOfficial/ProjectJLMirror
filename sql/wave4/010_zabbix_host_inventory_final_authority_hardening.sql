-- Wave 4 host-inventory final authority hardening.
-- Closes PR #135 findings around poll-fence rewinds, superseded snapshot insertion,
-- snapshot cardinality closure, and mutation of claimed poll authority.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_monitoring_source_poll_generation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.host_inventory_poll_generation < OLD.host_inventory_poll_generation THEN
        RAISE EXCEPTION 'Monitoring source host inventory poll generation cannot rewind';
    END IF;
    IF NEW.host_inventory_poll_generation > OLD.host_inventory_poll_generation + 1 THEN
        RAISE EXCEPTION 'Monitoring source host inventory poll generation may advance only one generation at a time';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_monitoring_source_poll_generation_guard ON monitoring.monitoring_source;
CREATE TRIGGER wave4_monitoring_source_poll_generation_guard
BEFORE UPDATE ON monitoring.monitoring_source
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_monitoring_source_poll_generation_update();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_sync_operation_poll_generation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
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

DROP TRIGGER IF EXISTS wave4_sync_operation_poll_generation_guard ON monitoring.monitoring_sync_operation;
CREATE TRIGGER wave4_sync_operation_poll_generation_guard
BEFORE UPDATE ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_sync_operation_poll_generation_update();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_snapshot_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_sync_operation AS o
          JOIN monitoring.monitoring_source AS s
            ON s.tenant_id=o.tenant_id
           AND s.monitoring_source_id=o.monitoring_source_id
          JOIN monitoring.monitoring_source_generation AS g
            ON g.tenant_id=o.tenant_id
           AND g.monitoring_source_id=o.monitoring_source_id
           AND g.source_instance_generation=o.source_instance_generation
         WHERE o.tenant_id=NEW.tenant_id
           AND o.monitoring_sync_operation_id=NEW.monitoring_sync_operation_id
           AND o.responsibility_kind='host_inventory_sync'
           AND o.state='running'
           AND o.claim_token IS NOT NULL
           AND o.monitoring_source_id=NEW.monitoring_source_id
           AND o.source_instance_generation=NEW.source_instance_generation
           AND o.configuration_revision=NEW.configuration_revision
           AND o.scope_revision=NEW.scope_revision
           AND o.host_inventory_poll_generation=NEW.host_inventory_poll_generation
           AND s.host_inventory_poll_generation=NEW.host_inventory_poll_generation
           AND s.active_source_instance_generation=NEW.source_instance_generation
           AND s.configuration_revision=NEW.configuration_revision
           AND s.scope_revision=NEW.scope_revision
           AND s.provider_scope_tenant_binding_id=NEW.provider_scope_tenant_binding_id
           AND g.provider_instance_ref=NEW.provider_instance_ref
    ) THEN
        RAISE EXCEPTION 'host inventory snapshot evidence requires current claimed poll authority';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_deferred_host_inventory_snapshot_closure()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_snapshot monitoring.monitoring_host_inventory_snapshot_evidence%ROWTYPE;
    v_members BIGINT;
BEGIN
    SELECT * INTO v_snapshot
      FROM monitoring.monitoring_host_inventory_snapshot_evidence AS e
     WHERE e.tenant_id=NEW.tenant_id
       AND e.host_inventory_snapshot_evidence_id=NEW.host_inventory_snapshot_evidence_id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT count(*) INTO v_members
      FROM monitoring.monitoring_resource_provider_evidence AS pe
     WHERE pe.tenant_id=v_snapshot.tenant_id
       AND pe.host_inventory_snapshot_evidence_id=v_snapshot.host_inventory_snapshot_evidence_id;

    IF v_members IS DISTINCT FROM v_snapshot.host_count THEN
        RAISE EXCEPTION 'Host inventory snapshot host_count must equal final provider evidence membership';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_sync_operation AS o
         WHERE o.tenant_id=v_snapshot.tenant_id
           AND o.monitoring_sync_operation_id=v_snapshot.monitoring_sync_operation_id
           AND o.responsibility_kind='host_inventory_sync'
           AND o.state=v_snapshot.operation_state
           AND o.state IN ('succeeded','reconciliation_required')
           AND o.host_inventory_snapshot_evidence_id=v_snapshot.host_inventory_snapshot_evidence_id
           AND o.host_inventory_poll_generation=v_snapshot.host_inventory_poll_generation
           AND o.monitoring_source_id=v_snapshot.monitoring_source_id
           AND o.source_instance_generation=v_snapshot.source_instance_generation
           AND o.configuration_revision=v_snapshot.configuration_revision
           AND o.scope_revision=v_snapshot.scope_revision
    ) THEN
        RAISE EXCEPTION 'Host inventory snapshot must close with its owning terminal operation';
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_inventory_snapshot_closure_deferred ON monitoring.monitoring_host_inventory_snapshot_evidence;
CREATE CONSTRAINT TRIGGER wave4_host_inventory_snapshot_closure_deferred
AFTER INSERT ON monitoring.monitoring_host_inventory_snapshot_evidence
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_deferred_host_inventory_snapshot_closure();

COMMIT;
