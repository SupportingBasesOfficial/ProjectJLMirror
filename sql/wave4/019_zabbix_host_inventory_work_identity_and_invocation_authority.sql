-- Wave 4 host-inventory work-identity and invocation-authority hardening.
-- Independent panoramic review findings:
-- 1. pending host-inventory work could be retargeted to another valid source/revision
--    before claim and then legitimized by the guarded claim path; and
-- 2. SECURITY DEFINER host-inventory entrypoints were executable by PUBLIC, allowing
--    an unrelated same-tenant runtime to enter the privileged executor path directly.
--
-- Final rule: host-inventory work identity is immutable from enqueue onward, and only
-- the dedicated provider-integration invoker capability may invoke enqueue/claim/complete.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_host_inventory_invoker') THEN
        CREATE ROLE jlmirror_wave4_host_inventory_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO jlmirror_wave4_host_inventory_invoker;
REVOKE CREATE ON SCHEMA monitoring FROM jlmirror_wave4_host_inventory_invoker;

-- A host-inventory work item's ownership/revision identity is fixed at enqueue.
-- Claim and completion may mutate lifecycle/authority fields, but may never redirect
-- the work to another source or reinterpret it under another revision tuple.
CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_claim_revision_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring AS $$
BEGIN
    IF OLD.responsibility_kind = 'host_inventory_sync'
       AND (
           NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.monitoring_sync_operation_id IS DISTINCT FROM OLD.monitoring_sync_operation_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
           OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
       ) THEN
        RAISE EXCEPTION 'Host inventory work identity and source/revision authority are immutable from enqueue';
    END IF;

    RETURN NEW;
END;
$$;

-- Keep inserted pending work lifecycle-clean. This closes non-authoritative lifecycle
-- residue that could otherwise be injected before the guarded claim transition.
CREATE OR REPLACE FUNCTION monitoring.wave4_guard_host_inventory_operation_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring AS $$
BEGIN
    IF NEW.responsibility_kind = 'host_inventory_sync' THEN
        IF NEW.state IS DISTINCT FROM 'pending'
           OR NEW.claim_token IS NOT NULL
           OR NEW.host_inventory_poll_generation IS NOT NULL
           OR NEW.host_inventory_poll_epoch IS NOT NULL
           OR NEW.host_inventory_snapshot_evidence_id IS NOT NULL
           OR NEW.started_at IS NOT NULL
           OR NEW.completed_at IS NOT NULL
           OR NEW.last_error_class IS NOT NULL
           OR NEW.attempt_count IS DISTINCT FROM 0 THEN
            RAISE EXCEPTION 'Host inventory operation insert must be lifecycle-clean unclaimed pending work';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- SECURITY DEFINER is retained so the implementation can use the narrow executor
-- role without granting table authority to the caller. Invocation itself is no longer
-- public: it is a distinct provider-integration worker capability.
REVOKE EXECUTE ON FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(TEXT,TEXT,TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_host_inventory(TEXT,TEXT,TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_host_inventory(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_host_inventory_invoker;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_host_inventory(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_host_inventory_invoker;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_host_inventory(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT)
    TO jlmirror_wave4_host_inventory_invoker;

COMMIT;
