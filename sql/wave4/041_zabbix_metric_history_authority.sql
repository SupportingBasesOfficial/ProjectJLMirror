-- Wave 4 Metric History independent recovery-safe authority.
-- Authority: wave4.monitoring-metric-history@1.

BEGIN;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN history_poll_epoch BIGINT NOT NULL DEFAULT 1 CHECK (history_poll_epoch > 0),
    ADD COLUMN history_poll_generation BIGINT NOT NULL DEFAULT 0 CHECK (history_poll_generation >= 0);

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN history_poll_epoch BIGINT NULL CHECK (history_poll_epoch IS NULL OR history_poll_epoch > 0),
    ADD COLUMN history_poll_generation BIGINT NULL CHECK (history_poll_generation IS NULL OR history_poll_generation > 0);

CREATE UNLOGGED TABLE monitoring.monitoring_metric_history_runtime_admission (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    history_poll_epoch BIGINT NOT NULL CHECK (history_poll_epoch > 0),
    placement_version TEXT NOT NULL CHECK (placement_version <> ''),
    recovery_generation TEXT NOT NULL CHECK (recovery_generation <> ''),
    recovery_admission_ref TEXT NOT NULL CHECK (recovery_admission_ref <> ''),
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE monitoring.monitoring_metric_history_runtime_admission IS
'Volatile fail-closed admission for Metric History. Independent from Host Inventory, Metric Definitions and Metric Current State and re-established after recovery/relocation.';

ALTER TABLE monitoring.monitoring_metric_history_runtime_admission ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_history_runtime_admission FORCE ROW LEVEL SECURITY;
CREATE POLICY metric_history_runtime_admission_tenant_policy
ON monitoring.monitoring_metric_history_runtime_admission
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
REVOKE ALL ON monitoring.monitoring_metric_history_runtime_admission FROM PUBLIC;
GRANT SELECT ON monitoring.monitoring_metric_history_runtime_admission
TO jlmirror_wave4_metric_history_executor;
GRANT SELECT,INSERT,UPDATE,DELETE ON monitoring.monitoring_metric_history_runtime_admission
TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_history_source_poll_authority()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NEW.history_poll_epoch IS DISTINCT FROM OLD.history_poll_epoch
       OR NEW.history_poll_generation IS DISTINCT FROM OLD.history_poll_generation THEN
        IF current_user NOT IN ('jlmirror_wave4_metric_history_executor','jlmirror_wave4_recovery_authority') THEN
            RAISE EXCEPTION 'Metric History poll authority requires guarded authority';
        END IF;
    END IF;
    IF NEW.history_poll_epoch < OLD.history_poll_epoch THEN
        RAISE EXCEPTION 'Metric History poll epoch cannot rewind';
    END IF;
    IF NEW.history_poll_epoch = OLD.history_poll_epoch THEN
        IF NEW.history_poll_generation < OLD.history_poll_generation THEN
            RAISE EXCEPTION 'Metric History poll generation cannot rewind';
        END IF;
        IF NEW.history_poll_generation > OLD.history_poll_generation + 1 THEN
            RAISE EXCEPTION 'Metric History poll generation may advance only one generation at a time';
        END IF;
        IF NEW.history_poll_generation > OLD.history_poll_generation
           AND NOT EXISTS (
               SELECT 1
                 FROM monitoring.monitoring_metric_history_runtime_admission AS a
                WHERE a.tenant_id=NEW.tenant_id
                  AND a.monitoring_source_id=NEW.monitoring_source_id
                  AND a.history_poll_epoch=NEW.history_poll_epoch
           ) THEN
            RAISE EXCEPTION 'Metric History polling requires current recovery/placement admission';
        END IF;
    ELSE
        IF current_user <> 'jlmirror_wave4_recovery_authority' THEN
            RAISE EXCEPTION 'Metric History poll epoch may advance only through recovery authority';
        END IF;
        IF NEW.history_poll_generation IS DISTINCT FROM OLD.history_poll_generation THEN
            RAISE EXCEPTION 'Metric History recovery epoch transition must preserve local generation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER metric_history_source_poll_authority_guard
BEFORE UPDATE OF history_poll_epoch,history_poll_generation
ON monitoring.monitoring_source
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_history_source_poll_authority();

CREATE OR REPLACE FUNCTION monitoring.reestablish_metric_history_runtime_admission(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_expected_epoch BIGINT,
    p_placement_version TEXT,
    p_recovery_generation TEXT,
    p_recovery_admission_ref TEXT
) RETURNS BIGINT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_epoch BIGINT;
BEGIN
    IF current_user <> 'jlmirror_wave4_recovery_authority' THEN
        RAISE EXCEPTION 'monitoring.metric_history_recovery_authority_required';
    END IF;
    IF p_expected_epoch IS NULL OR p_expected_epoch <= 0
       OR p_placement_version IS NULL OR p_placement_version=''
       OR p_recovery_generation IS NULL OR p_recovery_generation=''
       OR p_recovery_admission_ref IS NULL OR p_recovery_admission_ref='' THEN
        RAISE EXCEPTION 'monitoring.metric_history_invalid_recovery_admission';
    END IF;

    SELECT history_poll_epoch INTO v_epoch
      FROM monitoring.monitoring_source
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=p_monitoring_source_id
     FOR UPDATE;
    IF NOT FOUND OR v_epoch <> p_expected_epoch THEN
        RAISE EXCEPTION 'monitoring.metric_history_recovery_epoch_mismatch';
    END IF;

    DELETE FROM monitoring.monitoring_metric_history_runtime_admission
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=p_monitoring_source_id;
    INSERT INTO monitoring.monitoring_metric_history_runtime_admission(
        tenant_id,monitoring_source_id,history_poll_epoch,
        placement_version,recovery_generation,recovery_admission_ref
    ) VALUES (
        p_tenant_id,p_monitoring_source_id,p_expected_epoch,
        p_placement_version,p_recovery_generation,p_recovery_admission_ref
    );
    RETURN p_expected_epoch;
END;
$$;
ALTER FUNCTION monitoring.reestablish_metric_history_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_recovery_authority;
REVOKE EXECUTE ON FUNCTION monitoring.reestablish_metric_history_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.reestablish_metric_history_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

COMMIT;
