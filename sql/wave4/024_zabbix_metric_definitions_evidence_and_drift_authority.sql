-- Wave 4 metric-definition evidence and drift authority hardening.
-- * Snapshot/provider evidence can be inserted only by the guarded executor.
-- * Value-kind drift makes the affected accepted definition/binding visibly
--   reconciliation_required without accepting unrelated metadata from that snapshot.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_definition_evidence_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=pg_catalog,monitoring
AS $$
BEGIN
    IF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric definition evidence creation requires guarded executor authority';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_metric_definition_snapshot_insert_authority
BEFORE INSERT ON monitoring.monitoring_metric_definition_snapshot_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_evidence_insert();

CREATE TRIGGER wave4_metric_definition_provider_evidence_insert_authority
BEFORE INSERT ON monitoring.monitoring_metric_definition_provider_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_definition_evidence_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_mark_metric_value_kind_drift(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_source_instance_generation TEXT,
    p_provider_external_ref TEXT
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,monitoring
AS $$
DECLARE
    v_metric_definition_id TEXT;
BEGIN
    IF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric value-kind drift marking requires guarded executor authority';
    END IF;

    SELECT b.metric_definition_id
      INTO v_metric_definition_id
      FROM monitoring.metric_definition_provider_binding AS b
     WHERE b.tenant_id=p_tenant_id
       AND b.monitoring_source_id=p_monitoring_source_id
       AND b.source_instance_generation=p_source_instance_generation
       AND b.provider_external_ref=p_provider_external_ref
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_drift_binding_missing';
    END IF;

    UPDATE monitoring.metric_definition AS d
       SET definition_evidence_state='reconciliation_required',
           updated_at=transaction_timestamp()
     WHERE d.tenant_id=p_tenant_id
       AND d.metric_definition_id=v_metric_definition_id;

    UPDATE monitoring.metric_definition_provider_binding AS b
       SET evidence_state='reconciliation_required',
           updated_at=transaction_timestamp()
     WHERE b.tenant_id=p_tenant_id
       AND b.metric_definition_id=v_metric_definition_id;
END;
$$;
ALTER FUNCTION monitoring.wave4_mark_metric_value_kind_drift(TEXT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_definition_executor;
REVOKE EXECUTE ON FUNCTION monitoring.wave4_mark_metric_value_kind_drift(TEXT,TEXT,TEXT,TEXT)
    FROM PUBLIC, jlmirror_wave4_metric_definition_invoker;

COMMIT;
