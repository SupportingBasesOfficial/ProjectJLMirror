-- Wave 4 host-inventory recovery/authority hardening.
-- Closes PR #135 findings around recovery-safe poll epochs and direct mutation of
-- poll/source/resource authority by same-tenant runtime writers.
--
-- Design:
-- * host inventory current-state authority is the tuple
--   (source_instance_generation, host_inventory_poll_epoch, host_inventory_poll_generation);
-- * the poll epoch is re-established through an owner-only recovery authority path;
-- * the runtime admission row is UNLOGGED so crash recovery/PITR/failover cannot
--   silently reuse a restored admission image; polling fails closed until re-admitted;
-- * ordinary runtime code may call the guarded host-inventory functions but direct
--   mutation of authority-bearing source/operation/resource fields is rejected.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_host_inventory_executor') THEN
        CREATE ROLE jlmirror_wave4_host_inventory_executor NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_recovery_authority') THEN
        CREATE ROLE jlmirror_wave4_recovery_authority NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO jlmirror_wave4_host_inventory_executor, jlmirror_wave4_recovery_authority;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN host_inventory_poll_epoch BIGINT NOT NULL DEFAULT 1
        CHECK (host_inventory_poll_epoch > 0);

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN host_inventory_poll_epoch BIGINT NULL
        CHECK (host_inventory_poll_epoch IS NULL OR host_inventory_poll_epoch > 0);

ALTER TABLE monitoring.monitoring_host_inventory_snapshot_evidence
    ADD COLUMN host_inventory_poll_epoch BIGINT NOT NULL DEFAULT 1
        CHECK (host_inventory_poll_epoch > 0);

ALTER TABLE monitoring.monitoring_resource
    ADD COLUMN last_confirmed_present_poll_epoch BIGINT NOT NULL DEFAULT 1
        CHECK (last_confirmed_present_poll_epoch > 0),
    ADD COLUMN removed_poll_epoch BIGINT NULL
        CHECK (removed_poll_epoch IS NULL OR removed_poll_epoch > 0),
    ADD CONSTRAINT monitoring_resource_removed_poll_epoch_state
        CHECK ((presence_state='removed') = (removed_poll_epoch IS NOT NULL));

CREATE UNLOGGED TABLE monitoring.monitoring_host_inventory_runtime_admission (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    host_inventory_poll_epoch BIGINT NOT NULL CHECK (host_inventory_poll_epoch > 0),
    placement_version TEXT NOT NULL CHECK (placement_version <> ''),
    recovery_generation TEXT NOT NULL CHECK (recovery_generation <> ''),
    recovery_admission_ref TEXT NOT NULL CHECK (recovery_admission_ref <> ''),
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE monitoring.monitoring_host_inventory_runtime_admission IS
'Fail-closed volatile admission for host-inventory current-state polling. UNLOGGED by design: after crash recovery/PITR/failover/relocation, restored durable source state cannot self-certify prior poll-epoch continuity; trusted recovery authority must re-establish admission and a successor epoch.';

ALTER TABLE monitoring.monitoring_host_inventory_runtime_admission ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_host_inventory_runtime_admission FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_host_inventory_runtime_admission_tenant_isolation
ON monitoring.monitoring_host_inventory_runtime_admission
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

REVOKE ALL ON monitoring.monitoring_host_inventory_runtime_admission FROM PUBLIC;
GRANT SELECT ON monitoring.monitoring_host_inventory_runtime_admission TO jlmirror_wave4_host_inventory_executor;
GRANT SELECT, INSERT, UPDATE, DELETE ON monitoring.monitoring_host_inventory_runtime_admission TO jlmirror_wave4_recovery_authority;

GRANT SELECT, INSERT, UPDATE ON monitoring.monitoring_source,
    monitoring.monitoring_sync_operation,
    monitoring.monitoring_host_inventory_snapshot_evidence,
    monitoring.monitoring_resource,
    monitoring.monitoring_resource_provider_evidence
TO jlmirror_wave4_host_inventory_executor;

-- Existing live sources receive a bootstrap admission for the current deployment.
-- The admission itself is volatile and will not silently survive recovery.
INSERT INTO monitoring.monitoring_host_inventory_runtime_admission(
    tenant_id, monitoring_source_id, host_inventory_poll_epoch,
    placement_version, recovery_generation, recovery_admission_ref
)
SELECT tenant_id, monitoring_source_id, host_inventory_poll_epoch,
       'bootstrap-placement', 'bootstrap-recovery', 'bootstrap-source-migration'
  FROM monitoring.monitoring_source;

CREATE OR REPLACE FUNCTION monitoring.wave4_host_inventory_executor_is_current_user()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
    SELECT current_user = 'jlmirror_wave4_host_inventory_executor'
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_monitoring_source_poll_generation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.host_inventory_poll_epoch IS DISTINCT FROM OLD.host_inventory_poll_epoch
       OR NEW.host_inventory_poll_generation IS DISTINCT FROM OLD.host_inventory_poll_generation THEN
        IF NOT monitoring.wave4_host_inventory_executor_is_current_user()
           AND current_user <> 'jlmirror_wave4_recovery_authority' THEN
            RAISE EXCEPTION 'Host inventory poll authority requires guarded executor authority';
        END IF;
    END IF;

    IF NEW.host_inventory_poll_epoch < OLD.host_inventory_poll_epoch THEN
        RAISE EXCEPTION 'Monitoring source host inventory poll epoch cannot rewind';
    END IF;

    IF NEW.host_inventory_poll_epoch = OLD.host_inventory_poll_epoch THEN
        IF NEW.host_inventory_poll_generation < OLD.host_inventory_poll_generation THEN
            RAISE EXCEPTION 'Monitoring source host inventory poll generation cannot rewind';
        END IF;
        IF NEW.host_inventory_poll_generation > OLD.host_inventory_poll_generation + 1 THEN
            RAISE EXCEPTION 'Monitoring source host inventory poll generation may advance only one generation at a time';
        END IF;
    ELSE
        IF current_user <> 'jlmirror_wave4_recovery_authority' THEN
            RAISE EXCEPTION 'Host inventory poll epoch may advance only through recovery authority';
        END IF;
        IF NEW.host_inventory_poll_epoch <= OLD.host_inventory_poll_epoch THEN
            RAISE EXCEPTION 'Host inventory recovery requires a successor poll epoch';
        END IF;
        IF NEW.host_inventory_poll_generation IS DISTINCT FROM OLD.host_inventory_poll_generation THEN
            RAISE EXCEPTION 'Recovery epoch transition must preserve durable local poll generation';
        END IF;
    END IF;

    IF NEW.host_inventory_poll_generation > OLD.host_inventory_poll_generation THEN
        IF NOT EXISTS (
            SELECT 1
              FROM monitoring.monitoring_host_inventory_runtime_admission AS a
             WHERE a.tenant_id=NEW.tenant_id
               AND a.monitoring_source_id=NEW.monitoring_source_id
               AND a.host_inventory_poll_epoch=NEW.host_inventory_poll_epoch
        ) THEN
            RAISE EXCEPTION 'Host inventory current-state polling requires current recovery/placement admission';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_sync_operation_poll_generation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_epoch BIGINT;
BEGIN
    IF (OLD.responsibility_kind='host_inventory_sync' OR NEW.responsibility_kind='host_inventory_sync')
       AND (
           NEW.state IS DISTINCT FROM OLD.state
           OR NEW.claim_token IS DISTINCT FROM OLD.claim_token
           OR NEW.responsibility_kind IS DISTINCT FROM OLD.responsibility_kind
           OR NEW.host_inventory_poll_generation IS DISTINCT FROM OLD.host_inventory_poll_generation
           OR NEW.host_inventory_poll_epoch IS DISTINCT FROM OLD.host_inventory_poll_epoch
           OR NEW.host_inventory_snapshot_evidence_id IS DISTINCT FROM OLD.host_inventory_snapshot_evidence_id
       )
       AND NOT monitoring.wave4_host_inventory_executor_is_current_user() THEN
        RAISE EXCEPTION 'Host inventory operation authority requires guarded executor authority';
    END IF;

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
       AND OLD.host_inventory_poll_epoch IS NOT NULL
       AND NEW.host_inventory_poll_epoch IS DISTINCT FROM OLD.host_inventory_poll_epoch THEN
        RAISE EXCEPTION 'Host inventory operation poll epoch is immutable after claim';
    END IF;

    IF OLD.responsibility_kind='host_inventory_sync'
       AND OLD.host_inventory_poll_generation IS NULL
       AND NEW.host_inventory_poll_generation IS NOT NULL THEN
        IF NOT (OLD.state='pending' AND NEW.state='running' AND NEW.claim_token IS NOT NULL) THEN
            RAISE EXCEPTION 'Host inventory operation poll authority may be assigned only by claim transition';
        END IF;
        SELECT s.host_inventory_poll_epoch INTO v_epoch
          FROM monitoring.monitoring_source AS s
         WHERE s.tenant_id=NEW.tenant_id
           AND s.monitoring_source_id=NEW.monitoring_source_id;
        IF v_epoch IS NULL THEN
            RAISE EXCEPTION 'Host inventory claim source authority missing';
        END IF;
        NEW.host_inventory_poll_epoch := v_epoch;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_monitoring_resource_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_current_epoch BIGINT;
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
       OR NEW.resource_kind IS DISTINCT FROM OLD.resource_kind
       OR NEW.provider_object_kind IS DISTINCT FROM OLD.provider_object_kind
       OR NEW.provider_external_ref IS DISTINCT FROM OLD.provider_external_ref THEN
        RAISE EXCEPTION 'Monitoring resource canonical/provider identity is immutable';
    END IF;

    IF (
        NEW.scope_state IS DISTINCT FROM OLD.scope_state
        OR NEW.scope_projection_revision IS DISTINCT FROM OLD.scope_projection_revision
        OR NEW.scope_evidence_state IS DISTINCT FROM OLD.scope_evidence_state
        OR NEW.presence_state IS DISTINCT FROM OLD.presence_state
        OR NEW.presence_evidence_state IS DISTINCT FROM OLD.presence_evidence_state
        OR NEW.last_confirmed_present_poll_generation IS DISTINCT FROM OLD.last_confirmed_present_poll_generation
        OR NEW.last_confirmed_present_poll_epoch IS DISTINCT FROM OLD.last_confirmed_present_poll_epoch
        OR NEW.removed_poll_generation IS DISTINCT FROM OLD.removed_poll_generation
        OR NEW.removed_poll_epoch IS DISTINCT FROM OLD.removed_poll_epoch
        OR NEW.latest_provider_evidence_id IS DISTINCT FROM OLD.latest_provider_evidence_id
    ) AND NOT monitoring.wave4_host_inventory_executor_is_current_user() THEN
        RAISE EXCEPTION 'Monitoring resource authority fields require guarded host-inventory executor';
    END IF;

    IF NEW.scope_projection_revision < OLD.scope_projection_revision THEN
        RAISE EXCEPTION 'Monitoring resource scope projection revision cannot regress';
    END IF;

    SELECT s.host_inventory_poll_epoch INTO v_current_epoch
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=NEW.tenant_id
       AND s.monitoring_source_id=NEW.monitoring_source_id;

    IF monitoring.wave4_host_inventory_executor_is_current_user() THEN
        IF NEW.last_confirmed_present_poll_generation IS DISTINCT FROM OLD.last_confirmed_present_poll_generation
           AND NEW.presence_state='present' THEN
            NEW.last_confirmed_present_poll_epoch := v_current_epoch;
        END IF;
        IF NEW.removed_poll_generation IS DISTINCT FROM OLD.removed_poll_generation
           AND NEW.presence_state='removed' THEN
            NEW.removed_poll_epoch := v_current_epoch;
        ELSIF NEW.presence_state <> 'removed' THEN
            NEW.removed_poll_epoch := NULL;
        END IF;
    END IF;

    IF (NEW.last_confirmed_present_poll_epoch, NEW.last_confirmed_present_poll_generation)
       < (OLD.last_confirmed_present_poll_epoch, OLD.last_confirmed_present_poll_generation) THEN
        RAISE EXCEPTION 'Monitoring resource observation authority cannot regress';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_monitoring_resource_update_guard ON monitoring.monitoring_resource;
CREATE TRIGGER wave4_monitoring_resource_update_guard
BEFORE UPDATE ON monitoring.monitoring_resource
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_monitoring_resource_update();

CREATE OR REPLACE FUNCTION monitoring.wave4_set_host_inventory_snapshot_poll_epoch()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_operation_epoch BIGINT;
    v_source_epoch BIGINT;
BEGIN
    SELECT o.host_inventory_poll_epoch, s.host_inventory_poll_epoch
      INTO v_operation_epoch, v_source_epoch
      FROM monitoring.monitoring_sync_operation AS o
      JOIN monitoring.monitoring_source AS s
        ON s.tenant_id=o.tenant_id
       AND s.monitoring_source_id=o.monitoring_source_id
     WHERE o.tenant_id=NEW.tenant_id
       AND o.monitoring_sync_operation_id=NEW.monitoring_sync_operation_id;

    IF v_operation_epoch IS NULL
       OR v_operation_epoch <> v_source_epoch
       OR NOT EXISTS (
           SELECT 1
             FROM monitoring.monitoring_host_inventory_runtime_admission AS a
            WHERE a.tenant_id=NEW.tenant_id
              AND a.monitoring_source_id=NEW.monitoring_source_id
              AND a.host_inventory_poll_epoch=v_source_epoch
       ) THEN
        RAISE EXCEPTION 'Host inventory snapshot requires current recovery-safe poll epoch authority';
    END IF;

    NEW.host_inventory_poll_epoch := v_operation_epoch;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS wave4_host_inventory_snapshot_epoch_guard ON monitoring.monitoring_host_inventory_snapshot_evidence;
CREATE TRIGGER wave4_host_inventory_snapshot_epoch_guard
BEFORE INSERT ON monitoring.monitoring_host_inventory_snapshot_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_set_host_inventory_snapshot_poll_epoch();

CREATE OR REPLACE FUNCTION monitoring.reestablish_zabbix_host_inventory_poll_epoch(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_expected_current_epoch BIGINT,
    p_successor_epoch BIGINT,
    p_placement_version TEXT,
    p_recovery_generation TEXT,
    p_recovery_admission_ref TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    v_epoch BIGINT;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id=''
       OR p_monitoring_source_id IS NULL OR p_monitoring_source_id=''
       OR p_expected_current_epoch IS NULL OR p_expected_current_epoch < 1
       OR p_successor_epoch IS NULL OR p_successor_epoch <= p_expected_current_epoch
       OR p_placement_version IS NULL OR p_placement_version=''
       OR p_recovery_generation IS NULL OR p_recovery_generation=''
       OR p_recovery_admission_ref IS NULL OR p_recovery_admission_ref='' THEN
        RAISE EXCEPTION 'invalid host inventory recovery admission';
    END IF;

    SELECT s.host_inventory_poll_epoch INTO v_epoch
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=p_monitoring_source_id
     FOR UPDATE;

    IF NOT FOUND OR v_epoch <> p_expected_current_epoch THEN
        RAISE EXCEPTION 'host inventory recovery epoch compare-and-swap failed';
    END IF;

    DELETE FROM monitoring.monitoring_host_inventory_runtime_admission AS a
     WHERE a.tenant_id=p_tenant_id
       AND a.monitoring_source_id=p_monitoring_source_id;

    UPDATE monitoring.monitoring_source AS s
       SET host_inventory_poll_epoch=p_successor_epoch,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=p_monitoring_source_id;

    INSERT INTO monitoring.monitoring_host_inventory_runtime_admission(
        tenant_id, monitoring_source_id, host_inventory_poll_epoch,
        placement_version, recovery_generation, recovery_admission_ref
    ) VALUES (
        p_tenant_id, p_monitoring_source_id, p_successor_epoch,
        p_placement_version, p_recovery_generation, p_recovery_admission_ref
    );

    RETURN p_successor_epoch;
END;
$$;

ALTER FUNCTION monitoring.reestablish_zabbix_host_inventory_poll_epoch(TEXT,TEXT,BIGINT,BIGINT,TEXT,TEXT,TEXT)
OWNER TO jlmirror_wave4_recovery_authority;
REVOKE ALL ON FUNCTION monitoring.reestablish_zabbix_host_inventory_poll_epoch(TEXT,TEXT,BIGINT,BIGINT,TEXT,TEXT,TEXT) FROM PUBLIC;

-- Host-inventory runtime mutations execute as a dedicated NOLOGIN/NOBYPASSRLS role.
ALTER FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(TEXT,TEXT,TEXT)
OWNER TO jlmirror_wave4_host_inventory_executor;
ALTER FUNCTION monitoring.claim_zabbix_host_inventory(TEXT,TEXT,TEXT)
OWNER TO jlmirror_wave4_host_inventory_executor;
ALTER FUNCTION monitoring.complete_zabbix_host_inventory(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT)
OWNER TO jlmirror_wave4_host_inventory_executor;

ALTER FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(TEXT,TEXT,TEXT) SECURITY DEFINER;
ALTER FUNCTION monitoring.claim_zabbix_host_inventory(TEXT,TEXT,TEXT) SECURITY DEFINER;
ALTER FUNCTION monitoring.complete_zabbix_host_inventory(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT) SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION monitoring.enqueue_zabbix_host_inventory_sync(TEXT,TEXT,TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_host_inventory(TEXT,TEXT,TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_host_inventory(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB,TEXT,TEXT) TO PUBLIC;

-- Bootstrap admission for Monitoring sources created after this migration. Restored
-- rows do not fire INSERT triggers, so recovery still fails closed.
CREATE OR REPLACE FUNCTION monitoring.wave4_bootstrap_host_inventory_runtime_admission()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    INSERT INTO monitoring.monitoring_host_inventory_runtime_admission(
        tenant_id, monitoring_source_id, host_inventory_poll_epoch,
        placement_version, recovery_generation, recovery_admission_ref
    ) VALUES (
        NEW.tenant_id, NEW.monitoring_source_id, NEW.host_inventory_poll_epoch,
        'bootstrap-placement', 'bootstrap-recovery', 'bootstrap-source-create'
    ) ON CONFLICT (tenant_id,monitoring_source_id) DO NOTHING;
    RETURN NEW;
END;
$$;
ALTER FUNCTION monitoring.wave4_bootstrap_host_inventory_runtime_admission()
OWNER TO jlmirror_wave4_recovery_authority;

DROP TRIGGER IF EXISTS wave4_host_inventory_runtime_admission_bootstrap ON monitoring.monitoring_source;
CREATE TRIGGER wave4_host_inventory_runtime_admission_bootstrap
AFTER INSERT ON monitoring.monitoring_source
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_bootstrap_host_inventory_runtime_admission();

COMMIT;
