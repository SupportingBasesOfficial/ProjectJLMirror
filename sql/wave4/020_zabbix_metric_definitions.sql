-- Wave 4 bounded Zabbix item-definition ingestion.
-- Authority: wave4.monitoring-metric-definitions@1.
-- Scope: item.get metadata -> canonical metric_definition + separate Zabbix binding.
-- No metric current state, history, problems, health, provider write-back or frontend.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_metric_definition_executor') THEN
        CREATE ROLE jlmirror_wave4_metric_definition_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_metric_definition_invoker') THEN
        CREATE ROLE jlmirror_wave4_metric_definition_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA monitoring TO jlmirror_wave4_metric_definition_executor,
    jlmirror_wave4_metric_definition_invoker;
REVOKE CREATE ON SCHEMA monitoring FROM jlmirror_wave4_metric_definition_executor,
    jlmirror_wave4_metric_definition_invoker;

ALTER TABLE monitoring.monitoring_source
    ADD COLUMN item_definition_poll_epoch BIGINT NOT NULL DEFAULT 1
        CHECK (item_definition_poll_epoch > 0),
    ADD COLUMN item_definition_poll_generation BIGINT NOT NULL DEFAULT 0
        CHECK (item_definition_poll_generation >= 0);

ALTER TABLE monitoring.monitoring_sync_operation
    DROP CONSTRAINT monitoring_sync_operation_responsibility_kind_check;
ALTER TABLE monitoring.monitoring_sync_operation
    ADD CONSTRAINT monitoring_sync_operation_responsibility_kind_check
    CHECK (responsibility_kind IN (
        'validation_and_initial_sync', 'host_inventory_sync', 'metric_definition_sync',
        'manual_sync', 'scope_reconciliation', 'replacement_candidate_validation',
        'post_cutover_reconciliation'
    )),
    ADD COLUMN item_definition_poll_epoch BIGINT NULL
        CHECK (item_definition_poll_epoch IS NULL OR item_definition_poll_epoch > 0),
    ADD COLUMN item_definition_poll_generation BIGINT NULL
        CHECK (item_definition_poll_generation IS NULL OR item_definition_poll_generation > 0),
    ADD COLUMN metric_definition_snapshot_evidence_id TEXT NULL;

CREATE UNLOGGED TABLE monitoring.monitoring_metric_definition_runtime_admission (
    tenant_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    item_definition_poll_epoch BIGINT NOT NULL CHECK (item_definition_poll_epoch > 0),
    placement_version TEXT NOT NULL CHECK (placement_version <> ''),
    recovery_generation TEXT NOT NULL CHECK (recovery_generation <> ''),
    recovery_admission_ref TEXT NOT NULL CHECK (recovery_admission_ref <> ''),
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, monitoring_source_id),
    FOREIGN KEY (tenant_id, monitoring_source_id)
        REFERENCES monitoring.monitoring_source(tenant_id, monitoring_source_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE monitoring.monitoring_metric_definition_runtime_admission IS
'Fail-closed volatile admission for item-definition polling. It intentionally does not reuse host-inventory admission state; recovery authority must re-establish this endpoint-specific stream after recovery/relocation.';

CREATE TABLE monitoring.metric_definition (
    tenant_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    name TEXT NOT NULL,
    value_kind TEXT NOT NULL CHECK (value_kind IN ('number','integer','boolean','string','text','log')),
    unit TEXT NOT NULL DEFAULT '',
    scope_state TEXT NOT NULL CHECK (scope_state IN ('in_scope','out_of_scope')),
    scope_projection_revision BIGINT NOT NULL CHECK (scope_projection_revision > 0),
    scope_evidence_state TEXT NOT NULL CHECK (scope_evidence_state IN ('current','reconciliation_required')),
    definition_state TEXT NOT NULL CHECK (definition_state IN ('active','retired')),
    definition_evidence_state TEXT NOT NULL CHECK (definition_evidence_state IN ('current','incomplete','unavailable','reconciliation_required')),
    last_confirmed_present_poll_epoch BIGINT NOT NULL CHECK (last_confirmed_present_poll_epoch > 0),
    last_confirmed_present_poll_generation BIGINT NOT NULL CHECK (last_confirmed_present_poll_generation > 0),
    retired_poll_epoch BIGINT NULL CHECK (retired_poll_epoch IS NULL OR retired_poll_epoch > 0),
    retired_poll_generation BIGINT NULL CHECK (retired_poll_generation IS NULL OR retired_poll_generation > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, metric_definition_id),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK (metric_definition_id <> '' AND length(metric_definition_id) <= 512),
    CHECK (name <> '' AND length(name) <= 1024),
    CHECK (length(unit) <= 255),
    CHECK ((definition_state='retired') = (retired_poll_epoch IS NOT NULL AND retired_poll_generation IS NOT NULL))
);

CREATE TABLE monitoring.metric_definition_provider_binding (
    tenant_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    provider_profile TEXT NOT NULL CHECK (provider_profile='zabbix'),
    provider_object_kind TEXT NOT NULL CHECK (provider_object_kind='zabbix_item'),
    provider_external_ref TEXT NOT NULL,
    provider_host_ref TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    native_value_type TEXT NOT NULL CHECK (native_value_type IN ('float','unsigned','character','text','log')),
    provider_operational_state TEXT NOT NULL CHECK (provider_operational_state IN ('enabled','disabled','unsupported')),
    evidence_state TEXT NOT NULL CHECK (evidence_state IN ('current','incomplete','unavailable','reconciliation_required')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, metric_definition_id),
    UNIQUE (tenant_id, monitoring_source_id, source_instance_generation, provider_external_ref),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    FOREIGN KEY (tenant_id, monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id, monitoring_resource_id),
    CHECK (provider_external_ref <> '' AND length(provider_external_ref) <= 256),
    CHECK (provider_host_ref <> '' AND length(provider_host_ref) <= 256),
    CHECK (provider_key <> '' AND length(provider_key) <= 2048)
);

CREATE TABLE monitoring.monitoring_metric_definition_snapshot_evidence (
    tenant_id TEXT NOT NULL,
    metric_definition_snapshot_evidence_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    item_definition_poll_epoch BIGINT NOT NULL CHECK (item_definition_poll_epoch > 0),
    item_definition_poll_generation BIGINT NOT NULL CHECK (item_definition_poll_generation > 0),
    snapshot_complete BOOLEAN NOT NULL,
    item_count BIGINT NOT NULL CHECK (item_count >= 0 AND item_count <= 200000),
    operational_evidence_state TEXT NOT NULL CHECK (operational_evidence_state IN ('current','incomplete','unavailable','reconciliation_required')),
    operation_state TEXT NOT NULL CHECK (operation_state IN ('succeeded','reconciliation_required')),
    failure_class TEXT NULL,
    egress_decision_ref TEXT NULL,
    credential_generation_ref TEXT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, metric_definition_snapshot_evidence_id),
    UNIQUE (tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id)
        REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK ((operation_state='succeeded') = snapshot_complete),
    CHECK ((operation_state='succeeded') = (operational_evidence_state='current')),
    CHECK ((operation_state='succeeded') = (failure_class IS NULL))
);

CREATE TABLE monitoring.monitoring_metric_definition_provider_evidence (
    tenant_id TEXT NOT NULL,
    provider_evidence_id TEXT NOT NULL,
    metric_definition_snapshot_evidence_id TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    provider_external_ref TEXT NOT NULL,
    provider_host_ref TEXT NOT NULL,
    evidence_fingerprint TEXT NOT NULL CHECK (evidence_fingerprint ~ '^[0-9a-f]{64}$'),
    normalized_evidence JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, provider_evidence_id),
    UNIQUE (tenant_id, metric_definition_snapshot_evidence_id, provider_external_ref),
    FOREIGN KEY (tenant_id, metric_definition_snapshot_evidence_id)
        REFERENCES monitoring.monitoring_metric_definition_snapshot_evidence(tenant_id, metric_definition_snapshot_evidence_id),
    FOREIGN KEY (tenant_id, metric_definition_id)
        REFERENCES monitoring.metric_definition(tenant_id, metric_definition_id),
    CHECK (jsonb_typeof(normalized_evidence)='object'),
    CHECK (octet_length(normalized_evidence::text) <= 16384)
);

ALTER TABLE monitoring.monitoring_metric_definition_runtime_admission ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_definition_runtime_admission FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_definition ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_definition FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_definition_provider_binding ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.metric_definition_provider_binding FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_definition_snapshot_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_definition_snapshot_evidence FORCE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_definition_provider_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_metric_definition_provider_evidence FORCE ROW LEVEL SECURITY;

CREATE POLICY metric_definition_runtime_admission_tenant_policy
ON monitoring.monitoring_metric_definition_runtime_admission
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_definition_tenant_policy ON monitoring.metric_definition
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_definition_binding_tenant_policy ON monitoring.metric_definition_provider_binding
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_definition_snapshot_tenant_policy ON monitoring.monitoring_metric_definition_snapshot_evidence
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
CREATE POLICY metric_definition_provider_evidence_tenant_policy ON monitoring.monitoring_metric_definition_provider_evidence
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));

REVOKE ALL ON monitoring.monitoring_metric_definition_runtime_admission,
    monitoring.metric_definition,
    monitoring.metric_definition_provider_binding,
    monitoring.monitoring_metric_definition_snapshot_evidence,
    monitoring.monitoring_metric_definition_provider_evidence FROM PUBLIC;

GRANT SELECT ON monitoring.monitoring_source,
    monitoring.monitoring_source_generation,
    monitoring.monitoring_resource,
    monitoring.monitoring_source_validation_evidence,
    monitoring.monitoring_metric_definition_runtime_admission
TO jlmirror_wave4_metric_definition_executor;
GRANT SELECT, INSERT, UPDATE ON monitoring.monitoring_sync_operation,
    monitoring.monitoring_source,
    monitoring.metric_definition,
    monitoring.metric_definition_provider_binding,
    monitoring.monitoring_metric_definition_snapshot_evidence,
    monitoring.monitoring_metric_definition_provider_evidence
TO jlmirror_wave4_metric_definition_executor;
GRANT SELECT, INSERT, UPDATE, DELETE ON monitoring.monitoring_metric_definition_runtime_admission
TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.wave4_metric_definition_executor_is_current_user()
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
    SELECT current_user='jlmirror_wave4_metric_definition_executor'
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_definition_source_poll_authority()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NEW.item_definition_poll_epoch IS DISTINCT FROM OLD.item_definition_poll_epoch
       OR NEW.item_definition_poll_generation IS DISTINCT FROM OLD.item_definition_poll_generation THEN
        IF NOT monitoring.wave4_metric_definition_executor_is_current_user()
           AND current_user <> 'jlmirror_wave4_recovery_authority' THEN
            RAISE EXCEPTION 'Metric definition poll authority requires guarded executor authority';
        END IF;
    END IF;
    IF NEW.item_definition_poll_epoch < OLD.item_definition_poll_epoch THEN
        RAISE EXCEPTION 'Metric definition poll epoch cannot rewind';
    END IF;
    IF NEW.item_definition_poll_epoch = OLD.item_definition_poll_epoch THEN
        IF NEW.item_definition_poll_generation < OLD.item_definition_poll_generation THEN
            RAISE EXCEPTION 'Metric definition poll generation cannot rewind';
        END IF;
        IF NEW.item_definition_poll_generation > OLD.item_definition_poll_generation + 1 THEN
            RAISE EXCEPTION 'Metric definition poll generation may advance only one generation at a time';
        END IF;
    ELSE
        IF current_user <> 'jlmirror_wave4_recovery_authority' THEN
            RAISE EXCEPTION 'Metric definition poll epoch may advance only through recovery authority';
        END IF;
        IF NEW.item_definition_poll_generation IS DISTINCT FROM OLD.item_definition_poll_generation THEN
            RAISE EXCEPTION 'Metric definition recovery epoch transition must preserve local generation';
        END IF;
    END IF;
    IF NEW.item_definition_poll_generation > OLD.item_definition_poll_generation
       AND NOT EXISTS (
           SELECT 1 FROM monitoring.monitoring_metric_definition_runtime_admission a
            WHERE a.tenant_id=NEW.tenant_id
              AND a.monitoring_source_id=NEW.monitoring_source_id
              AND a.item_definition_poll_epoch=NEW.item_definition_poll_epoch
       ) THEN
        RAISE EXCEPTION 'Metric definition polling requires current recovery/placement admission';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_metric_definition_source_poll_authority_guard
BEFORE UPDATE ON monitoring.monitoring_source
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_source_poll_authority();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_definition_operation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='INSERT' AND NEW.responsibility_kind='metric_definition_sync' THEN
        IF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
            RAISE EXCEPTION 'Metric definition work creation requires guarded executor authority';
        END IF;
        IF NEW.state <> 'pending' OR NEW.claim_token IS NOT NULL
           OR NEW.item_definition_poll_epoch IS NOT NULL
           OR NEW.item_definition_poll_generation IS NOT NULL
           OR NEW.metric_definition_snapshot_evidence_id IS NOT NULL
           OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL
           OR NEW.last_error_class IS NOT NULL OR NEW.attempt_count <> 0 THEN
            RAISE EXCEPTION 'Metric definition operation must begin as clean pending work';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP='UPDATE' AND OLD.responsibility_kind='metric_definition_sync' THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.monitoring_sync_operation_id IS DISTINCT FROM OLD.monitoring_sync_operation_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
           OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
           OR NEW.responsibility_kind IS DISTINCT FROM OLD.responsibility_kind THEN
            RAISE EXCEPTION 'Metric definition work identity/source/revision authority is immutable';
        END IF;
        IF NOT monitoring.wave4_metric_definition_executor_is_current_user() AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Metric definition operation lifecycle requires guarded executor authority';
        END IF;
        IF OLD.state IN ('succeeded','reconciliation_required','failed_terminal') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Terminal metric definition operation is immutable';
        END IF;
        IF OLD.item_definition_poll_epoch IS NOT NULL
           AND NEW.item_definition_poll_epoch IS DISTINCT FROM OLD.item_definition_poll_epoch THEN
            RAISE EXCEPTION 'Claimed metric definition poll epoch is immutable';
        END IF;
        IF OLD.item_definition_poll_generation IS NOT NULL
           AND NEW.item_definition_poll_generation IS DISTINCT FROM OLD.item_definition_poll_generation THEN
            RAISE EXCEPTION 'Claimed metric definition poll generation is immutable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_metric_definition_operation_guard_insert
BEFORE INSERT ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_operation();
CREATE TRIGGER wave4_metric_definition_operation_guard_update
BEFORE UPDATE ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_operation();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_definition_identity()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='UPDATE' THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.metric_definition_id IS DISTINCT FROM OLD.metric_definition_id
           OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.value_kind IS DISTINCT FROM OLD.value_kind THEN
            RAISE EXCEPTION 'Canonical metric definition identity/value kind is immutable under this authorization';
        END IF;
        IF NOT monitoring.wave4_metric_definition_executor_is_current_user()
           AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Metric definition mutation requires guarded executor authority';
        END IF;
    ELSIF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric definition creation requires guarded executor authority';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_metric_definition_identity_guard
BEFORE INSERT OR UPDATE ON monitoring.metric_definition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_identity();

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_definition_binding()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='UPDATE' THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.metric_definition_id IS DISTINCT FROM OLD.metric_definition_id
           OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.provider_profile IS DISTINCT FROM OLD.provider_profile
           OR NEW.provider_object_kind IS DISTINCT FROM OLD.provider_object_kind
           OR NEW.provider_external_ref IS DISTINCT FROM OLD.provider_external_ref
           OR NEW.provider_host_ref IS DISTINCT FROM OLD.provider_host_ref
           OR NEW.native_value_type IS DISTINCT FROM OLD.native_value_type THEN
            RAISE EXCEPTION 'Metric provider binding identity/native type is immutable';
        END IF;
        IF NOT monitoring.wave4_metric_definition_executor_is_current_user()
           AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Metric provider binding mutation requires guarded executor authority';
        END IF;
    ELSIF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric provider binding creation requires guarded executor authority';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_metric_definition_binding_guard
BEFORE INSERT OR UPDATE ON monitoring.metric_definition_provider_binding
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_binding();

CREATE OR REPLACE FUNCTION monitoring.wave4_reject_metric_definition_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    RAISE EXCEPTION 'Metric definition evidence is immutable';
END;
$$;
CREATE TRIGGER wave4_metric_definition_snapshot_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_metric_definition_snapshot_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_metric_definition_evidence_mutation();
CREATE TRIGGER wave4_metric_definition_provider_evidence_immutable
BEFORE UPDATE OR DELETE ON monitoring.monitoring_metric_definition_provider_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_metric_definition_evidence_mutation();

CREATE OR REPLACE FUNCTION monitoring.enqueue_zabbix_metric_definition_sync(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_monitoring_sync_operation_id TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
BEGIN
    IF session_user=current_user THEN
        -- No semantic effect; keeps the privilege boundary explicit in source review.
        NULL;
    END IF;
    SELECT active_source_instance_generation,configuration_revision,scope_revision
      INTO v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_source
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=p_monitoring_source_id
       AND operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.metric_definition_source_not_current'; END IF;
    INSERT INTO monitoring.monitoring_sync_operation(
        tenant_id,monitoring_sync_operation_id,monitoring_source_id,
        source_instance_generation,configuration_revision,scope_revision,
        responsibility_kind,state
    ) VALUES (
        p_tenant_id,p_monitoring_sync_operation_id,p_monitoring_source_id,
        v_generation,v_configuration_revision,v_scope_revision,
        'metric_definition_sync','pending'
    );
END;
$$;
ALTER FUNCTION monitoring.enqueue_zabbix_metric_definition_sync(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_definition_executor;

CREATE OR REPLACE FUNCTION monitoring.claim_zabbix_metric_definitions(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    provider_scope_tenant_binding_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    item_definition_poll_epoch BIGINT,
    item_definition_poll_generation BIGINT,
    provider_instance_ref TEXT,
    provider_base_url TEXT,
    credential_binding_ref TEXT,
    configured_provider_scope JSONB
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_epoch BIGINT;
    v_poll_generation BIGINT;
BEGIN
    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation o
     WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_definition_sync' AND o.state='pending' AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.metric_definition_not_claimable'; END IF;

    SELECT s.item_definition_poll_epoch,s.item_definition_poll_generation+1
      INTO v_poll_epoch,v_poll_generation
      FROM monitoring.monitoring_source s
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=v_source_id
       AND s.active_source_instance_generation=v_generation
       AND s.configuration_revision=v_configuration_revision
       AND s.scope_revision=v_scope_revision
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.metric_definition_stale_authority'; END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_metric_definition_runtime_admission a
         WHERE a.tenant_id=p_tenant_id AND a.monitoring_source_id=v_source_id
           AND a.item_definition_poll_epoch=v_poll_epoch
    ) THEN RAISE EXCEPTION 'monitoring.metric_definition_recovery_admission_required'; END IF;

    UPDATE monitoring.monitoring_source
       SET item_definition_poll_generation=v_poll_generation,updated_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND monitoring_source_id=v_source_id;

    UPDATE monitoring.monitoring_sync_operation
       SET state='running',claim_token=p_claim_token,started_at=transaction_timestamp(),
           attempt_count=attempt_count+1,item_definition_poll_epoch=v_poll_epoch,
           item_definition_poll_generation=v_poll_generation
     WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN QUERY
    SELECT s.monitoring_source_id,s.provider_scope_tenant_binding_id,
           s.active_source_instance_generation,s.configuration_revision,s.scope_revision,
           s.item_definition_poll_epoch,s.item_definition_poll_generation,
           g.provider_instance_ref,s.provider_base_url,s.credential_binding_ref,s.configured_provider_scope
      FROM monitoring.monitoring_source s
      JOIN monitoring.monitoring_source_generation g
        ON g.tenant_id=s.tenant_id AND g.monitoring_source_id=s.monitoring_source_id
       AND g.source_instance_generation=s.active_source_instance_generation
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=v_source_id;
END;
$$;
ALTER FUNCTION monitoring.claim_zabbix_metric_definitions(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_definition_executor;

-- Completion accepts normalized bounded item metadata only. It performs host mapping,
-- type-drift fencing and negative reconciliation inside the authoritative transaction.
CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_metric_definitions(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_metric_definition_snapshot_evidence_id TEXT,
    p_operational_evidence_state TEXT,
    p_operation_state TEXT,
    p_failure_class TEXT,
    p_egress_decision_ref TEXT,
    p_credential_generation_ref TEXT,
    p_snapshot_complete BOOLEAN,
    p_items JSONB
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_configuration_revision BIGINT;
    v_scope_revision BIGINT;
    v_poll_epoch BIGINT;
    v_poll_generation BIGINT;
    v_source_epoch BIGINT;
    v_source_poll BIGINT;
    v_item JSONB;
    v_resource_id TEXT;
    v_metric_id TEXT;
    v_existing_kind TEXT;
    v_kind TEXT;
    v_native_type TEXT;
    v_itemid TEXT;
    v_hostid TEXT;
    v_name TEXT;
    v_key TEXT;
    v_unit TEXT;
    v_provider_state TEXT;
    v_seen TEXT[] := ARRAY[]::TEXT[];
BEGIN
    IF jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) > 200000 THEN
        RAISE EXCEPTION 'monitoring.metric_definition_invalid_item_payload';
    END IF;
    IF (p_operation_state='succeeded') IS DISTINCT FROM p_snapshot_complete
       OR (p_operation_state='succeeded') IS DISTINCT FROM (p_operational_evidence_state='current') THEN
        RAISE EXCEPTION 'monitoring.metric_definition_invalid_completion_shape';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision,
           o.item_definition_poll_epoch,o.item_definition_poll_generation,
           s.item_definition_poll_epoch,s.item_definition_poll_generation
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision,
           v_poll_epoch,v_poll_generation,v_source_epoch,v_source_poll
      FROM monitoring.monitoring_sync_operation o
      JOIN monitoring.monitoring_source s
        ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id
     WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_definition_sync' AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE OF o,s;
    IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.metric_definition_completion_not_claimed'; END IF;

    IF v_source_epoch IS DISTINCT FROM v_poll_epoch OR v_source_poll IS DISTINCT FROM v_poll_generation THEN
        p_operation_state := 'reconciliation_required';
        p_operational_evidence_state := 'reconciliation_required';
        p_failure_class := 'execution.superseded_item_poll_authority';
        p_snapshot_complete := FALSE;
    END IF;

    IF p_operation_state='succeeded' THEN
        FOR v_item IN SELECT value FROM jsonb_array_elements(p_items)
        LOOP
            v_itemid := v_item->>'itemid';
            v_hostid := v_item->>'hostid';
            v_name := v_item->>'name';
            v_key := v_item->>'key';
            v_unit := COALESCE(v_item->>'unit','');
            v_native_type := v_item->>'native_value_type';
            v_provider_state := v_item->>'operational_state';
            IF v_itemid IS NULL OR v_itemid='' OR length(v_itemid)>256
               OR v_hostid IS NULL OR v_hostid='' OR length(v_hostid)>256
               OR v_name IS NULL OR v_name='' OR length(v_name)>1024
               OR v_key IS NULL OR v_key='' OR length(v_key)>2048
               OR length(v_unit)>255
               OR v_native_type NOT IN ('float','unsigned','character','text','log')
               OR v_provider_state NOT IN ('enabled','disabled','unsupported') THEN
                RAISE EXCEPTION 'monitoring.metric_definition_invalid_item_evidence';
            END IF;
            IF v_itemid=ANY(v_seen) THEN RAISE EXCEPTION 'monitoring.metric_definition_duplicate_itemid'; END IF;
            v_seen := array_append(v_seen,v_itemid);

            SELECT r.monitoring_resource_id INTO v_resource_id
              FROM monitoring.monitoring_resource r
             WHERE r.tenant_id=p_tenant_id AND r.monitoring_source_id=v_source_id
               AND r.source_instance_generation=v_generation
               AND r.provider_external_ref=v_hostid AND r.resource_kind='host'
               AND r.presence_state='present' AND r.scope_state='in_scope'
               AND r.scope_evidence_state='current' AND r.scope_projection_revision=v_scope_revision;
            IF NOT FOUND THEN RAISE EXCEPTION 'monitoring.metric_definition_host_association_invalid'; END IF;

            v_kind := CASE v_native_type
                WHEN 'float' THEN 'number'
                WHEN 'unsigned' THEN 'integer'
                WHEN 'character' THEN 'string'
                WHEN 'text' THEN 'text'
                WHEN 'log' THEN 'log'
            END;

            SELECT b.metric_definition_id,d.value_kind
              INTO v_metric_id,v_existing_kind
              FROM monitoring.metric_definition_provider_binding b
              JOIN monitoring.metric_definition d
                ON d.tenant_id=b.tenant_id AND d.metric_definition_id=b.metric_definition_id
             WHERE b.tenant_id=p_tenant_id AND b.monitoring_source_id=v_source_id
               AND b.source_instance_generation=v_generation
               AND b.provider_external_ref=v_itemid;

            IF FOUND AND v_existing_kind IS DISTINCT FROM v_kind THEN
                UPDATE monitoring.metric_definition
                   SET definition_evidence_state='reconciliation_required',updated_at=transaction_timestamp()
                 WHERE tenant_id=p_tenant_id AND metric_definition_id=v_metric_id;
                UPDATE monitoring.metric_definition_provider_binding
                   SET evidence_state='reconciliation_required',updated_at=transaction_timestamp()
                 WHERE tenant_id=p_tenant_id AND metric_definition_id=v_metric_id;
                p_operation_state := 'reconciliation_required';
                p_operational_evidence_state := 'reconciliation_required';
                p_failure_class := 'provider.value_kind_drift';
                p_snapshot_complete := FALSE;
                EXIT;
            END IF;

            IF NOT FOUND THEN
                v_metric_id := 'mon-metric-' || encode(sha256(convert_to(
                    p_tenant_id || ':' || v_source_id || ':' || v_generation || ':' || v_itemid,'UTF8'
                )),'hex');
                INSERT INTO monitoring.metric_definition(
                    tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,
                    source_instance_generation,name,value_kind,unit,scope_state,
                    scope_projection_revision,scope_evidence_state,definition_state,
                    definition_evidence_state,last_confirmed_present_poll_epoch,
                    last_confirmed_present_poll_generation
                ) VALUES (
                    p_tenant_id,v_metric_id,v_resource_id,v_source_id,v_generation,v_name,v_kind,v_unit,
                    'in_scope',v_scope_revision,'current','active','current',v_poll_epoch,v_poll_generation
                );
                INSERT INTO monitoring.metric_definition_provider_binding(
                    tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,
                    source_instance_generation,provider_profile,provider_object_kind,provider_external_ref,
                    provider_host_ref,provider_key,native_value_type,provider_operational_state,evidence_state
                ) VALUES (
                    p_tenant_id,v_metric_id,v_resource_id,v_source_id,v_generation,'zabbix','zabbix_item',
                    v_itemid,v_hostid,v_key,v_native_type,v_provider_state,'current'
                );
            ELSE
                UPDATE monitoring.metric_definition
                   SET name=v_name,unit=v_unit,scope_state='in_scope',scope_projection_revision=v_scope_revision,
                       scope_evidence_state='current',definition_state='active',definition_evidence_state='current',
                       retired_poll_epoch=NULL,retired_poll_generation=NULL,
                       last_confirmed_present_poll_epoch=v_poll_epoch,
                       last_confirmed_present_poll_generation=v_poll_generation,
                       updated_at=transaction_timestamp()
                 WHERE tenant_id=p_tenant_id AND metric_definition_id=v_metric_id;
                UPDATE monitoring.metric_definition_provider_binding
                   SET provider_key=v_key,provider_operational_state=v_provider_state,evidence_state='current',
                       updated_at=transaction_timestamp()
                 WHERE tenant_id=p_tenant_id AND metric_definition_id=v_metric_id;
            END IF;

            INSERT INTO monitoring.monitoring_metric_definition_provider_evidence(
                tenant_id,provider_evidence_id,metric_definition_snapshot_evidence_id,
                metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
                provider_external_ref,provider_host_ref,evidence_fingerprint,normalized_evidence
            ) VALUES (
                p_tenant_id,
                p_metric_definition_snapshot_evidence_id || ':' || v_itemid,
                p_metric_definition_snapshot_evidence_id,v_metric_id,v_resource_id,v_source_id,v_generation,
                v_itemid,v_hostid,
                encode(sha256(convert_to(v_item::text,'UTF8')),'hex'),v_item
            );
        END LOOP;
    END IF;

    INSERT INTO monitoring.monitoring_metric_definition_snapshot_evidence(
        tenant_id,metric_definition_snapshot_evidence_id,monitoring_sync_operation_id,
        monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,
        item_definition_poll_epoch,item_definition_poll_generation,snapshot_complete,item_count,
        operational_evidence_state,operation_state,failure_class,egress_decision_ref,credential_generation_ref
    ) VALUES (
        p_tenant_id,p_metric_definition_snapshot_evidence_id,p_monitoring_sync_operation_id,
        v_source_id,v_generation,v_configuration_revision,v_scope_revision,v_poll_epoch,v_poll_generation,
        p_snapshot_complete,jsonb_array_length(p_items),p_operational_evidence_state,p_operation_state,
        p_failure_class,p_egress_decision_ref,p_credential_generation_ref
    );

    IF p_operation_state='succeeded' THEN
        UPDATE monitoring.metric_definition d
           SET definition_state='retired',definition_evidence_state='current',
               retired_poll_epoch=v_poll_epoch,retired_poll_generation=v_poll_generation,
               updated_at=transaction_timestamp()
         WHERE d.tenant_id=p_tenant_id AND d.monitoring_source_id=v_source_id
           AND d.source_instance_generation=v_generation AND d.definition_state='active'
           AND d.scope_state='in_scope' AND d.scope_evidence_state='current'
           AND d.scope_projection_revision=v_scope_revision
           AND NOT EXISTS (
               SELECT 1 FROM monitoring.metric_definition_provider_binding b
                WHERE b.tenant_id=d.tenant_id AND b.metric_definition_id=d.metric_definition_id
                  AND b.provider_external_ref=ANY(v_seen)
           );
    END IF;

    UPDATE monitoring.monitoring_sync_operation
       SET state=p_operation_state,completed_at=transaction_timestamp(),last_error_class=p_failure_class,
           metric_definition_snapshot_evidence_id=p_metric_definition_snapshot_evidence_id,
           claim_token=NULL
     WHERE tenant_id=p_tenant_id AND monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN p_operation_state;
END;
$$;
ALTER FUNCTION monitoring.complete_zabbix_metric_definitions(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB)
    OWNER TO jlmirror_wave4_metric_definition_executor;

REVOKE EXECUTE ON FUNCTION monitoring.enqueue_zabbix_metric_definition_sync(TEXT,TEXT,TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_definitions(TEXT,TEXT,TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.enqueue_zabbix_metric_definition_sync(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_definition_invoker;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_definitions(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_definition_invoker;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_definitions(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,BOOLEAN,JSONB)
    TO jlmirror_wave4_metric_definition_invoker;

-- Bootstrap current deployment only. Because the table is UNLOGGED, this state does
-- not become durable recovery authority and must be re-established after recovery.
INSERT INTO monitoring.monitoring_metric_definition_runtime_admission(
    tenant_id,monitoring_source_id,item_definition_poll_epoch,
    placement_version,recovery_generation,recovery_admission_ref
)
SELECT tenant_id,monitoring_source_id,item_definition_poll_epoch,
       'bootstrap-placement','bootstrap-recovery','bootstrap-metric-definition-migration'
  FROM monitoring.monitoring_source;

COMMIT;
