-- Wave 4 Problem State durable snapshot/completeness authority hardening.
-- Complete negative resolution must consume one immutable operation-bound evidence record.

BEGIN;

ALTER TABLE monitoring.monitoring_sync_operation
    ADD COLUMN problem_snapshot_evidence_id TEXT NULL;

CREATE TABLE monitoring.monitoring_problem_snapshot_evidence (
    tenant_id TEXT NOT NULL,
    problem_snapshot_evidence_id TEXT NOT NULL,
    monitoring_sync_operation_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    configuration_revision BIGINT NOT NULL CHECK (configuration_revision > 0),
    scope_revision BIGINT NOT NULL CHECK (scope_revision > 0),
    problem_poll_epoch BIGINT NOT NULL CHECK (problem_poll_epoch > 0),
    problem_poll_generation BIGINT NOT NULL CHECK (problem_poll_generation > 0),
    snapshot_complete BOOLEAN NOT NULL,
    active_problem_count BIGINT NOT NULL CHECK (active_problem_count BETWEEN 0 AND 20000),
    recovery_event_count BIGINT NOT NULL CHECK (recovery_event_count BETWEEN 0 AND 20000),
    operational_evidence_state TEXT NOT NULL
        CHECK (operational_evidence_state IN ('current','incomplete','unavailable','reconciliation_required')),
    operation_state TEXT NOT NULL
        CHECK (operation_state IN ('succeeded','reconciliation_required')),
    egress_decision_ref TEXT NULL,
    credential_generation_ref TEXT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, problem_snapshot_evidence_id),
    UNIQUE (tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_sync_operation_id)
        REFERENCES monitoring.monitoring_sync_operation(tenant_id, monitoring_sync_operation_id),
    FOREIGN KEY (tenant_id, monitoring_source_id, source_instance_generation)
        REFERENCES monitoring.monitoring_source_generation(tenant_id, monitoring_source_id, source_instance_generation),
    CHECK (problem_snapshot_evidence_id <> '' AND length(problem_snapshot_evidence_id) <= 512),
    CHECK ((operation_state='succeeded') = snapshot_complete),
    CHECK ((operation_state='succeeded') = (operational_evidence_state='current'))
);

COMMENT ON TABLE monitoring.monitoring_problem_snapshot_evidence IS
'Immutable Problem State provider-read completeness evidence bound to one claimed operation/poll authority. Authoritative negative resolution may consume only snapshot_complete=true evidence.';

ALTER TABLE monitoring.monitoring_problem_snapshot_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_problem_snapshot_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY problem_snapshot_evidence_tenant_policy
ON monitoring.monitoring_problem_snapshot_evidence
USING (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''))
WITH CHECK (tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), ''));
REVOKE ALL ON monitoring.monitoring_problem_snapshot_evidence FROM PUBLIC;
GRANT SELECT, INSERT ON monitoring.monitoring_problem_snapshot_evidence
TO jlmirror_wave4_problem_state_executor;

CREATE TRIGGER problem_snapshot_evidence_immutable_guard
BEFORE UPDATE OR DELETE ON monitoring.monitoring_problem_snapshot_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_reject_problem_immutable_mutation();

-- Seal the weaker completion entrypoint from runtime callers. Only the hardened
-- wrapper below is part of the invoker surface after this migration.
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_problem_state(TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN)
FROM jlmirror_wave4_problem_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_problem_state_with_evidence(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_problem_snapshot_evidence_id TEXT,
    p_active_problems JSONB,
    p_recoveries JSONB,
    p_snapshot_complete BOOLEAN,
    p_egress_decision_ref TEXT,
    p_credential_generation_ref TEXT
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_operation monitoring.monitoring_sync_operation%ROWTYPE;
    v_state TEXT;
BEGIN
    IF p_problem_snapshot_evidence_id IS NULL OR p_problem_snapshot_evidence_id=''
       OR length(p_problem_snapshot_evidence_id)>512 THEN
        RAISE EXCEPTION 'monitoring.problem_state_invalid_snapshot_evidence_id';
    END IF;
    IF p_active_problems IS NULL OR jsonb_typeof(p_active_problems)<>'array'
       OR p_recoveries IS NULL OR jsonb_typeof(p_recoveries)<>'array'
       OR jsonb_array_length(p_active_problems)>20000
       OR jsonb_array_length(p_recoveries)>20000 THEN
        RAISE EXCEPTION 'monitoring.problem_state_invalid_snapshot_evidence_payload';
    END IF;

    SELECT o.* INTO v_operation
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='problem_state_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.problem_state_snapshot_evidence_not_claimed';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_source AS s
         WHERE s.tenant_id=p_tenant_id
           AND s.monitoring_source_id=v_operation.monitoring_source_id
           AND s.active_source_instance_generation=v_operation.source_instance_generation
           AND s.configuration_revision=v_operation.configuration_revision
           AND s.scope_revision=v_operation.scope_revision
           AND s.problem_poll_epoch=v_operation.problem_poll_epoch
           AND s.problem_poll_generation=v_operation.problem_poll_generation
           AND s.operational_evidence_state='current'
    ) OR NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_operation.monitoring_source_id
           AND a.problem_poll_epoch=v_operation.problem_poll_epoch
    ) THEN
        RAISE EXCEPTION 'monitoring.problem_state_snapshot_authority_superseded';
    END IF;

    INSERT INTO monitoring.monitoring_problem_snapshot_evidence(
        tenant_id,problem_snapshot_evidence_id,monitoring_sync_operation_id,
        monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,
        problem_poll_epoch,problem_poll_generation,snapshot_complete,
        active_problem_count,recovery_event_count,operational_evidence_state,operation_state,
        egress_decision_ref,credential_generation_ref
    ) VALUES (
        p_tenant_id,p_problem_snapshot_evidence_id,p_monitoring_sync_operation_id,
        v_operation.monitoring_source_id,v_operation.source_instance_generation,
        v_operation.configuration_revision,v_operation.scope_revision,
        v_operation.problem_poll_epoch,v_operation.problem_poll_generation,p_snapshot_complete,
        jsonb_array_length(p_active_problems),jsonb_array_length(p_recoveries),
        CASE WHEN p_snapshot_complete THEN 'current' ELSE 'reconciliation_required' END,
        CASE WHEN p_snapshot_complete THEN 'succeeded' ELSE 'reconciliation_required' END,
        p_egress_decision_ref,p_credential_generation_ref
    );

    UPDATE monitoring.monitoring_sync_operation AS o
       SET problem_snapshot_evidence_id=p_problem_snapshot_evidence_id
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    v_state:=monitoring.complete_zabbix_problem_state(
        p_tenant_id,p_monitoring_sync_operation_id,p_claim_token,
        p_active_problems,p_recoveries,p_snapshot_complete
    );

    IF p_snapshot_complete AND NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem_snapshot_evidence AS e
         WHERE e.tenant_id=p_tenant_id
           AND e.problem_snapshot_evidence_id=p_problem_snapshot_evidence_id
           AND e.monitoring_sync_operation_id=p_monitoring_sync_operation_id
           AND e.snapshot_complete
           AND e.operation_state='succeeded'
           AND e.operational_evidence_state='current'
           AND e.problem_poll_epoch=v_operation.problem_poll_epoch
           AND e.problem_poll_generation=v_operation.problem_poll_generation
    ) THEN
        RAISE EXCEPTION 'monitoring.problem_state_authoritative_negative_evidence_missing';
    END IF;

    RETURN v_state;
END;
$$;
ALTER FUNCTION monitoring.complete_zabbix_problem_state_with_evidence(TEXT,TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN,TEXT,TEXT)
    OWNER TO jlmirror_wave4_problem_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_problem_state_with_evidence(TEXT,TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_problem_state_with_evidence(TEXT,TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN,TEXT,TEXT)
    TO jlmirror_wave4_problem_state_invoker;

COMMIT;
