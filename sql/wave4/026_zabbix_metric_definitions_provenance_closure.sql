-- Wave 4 metric-definition provenance closure hardening.
-- Defense-in-depth guarantees:
-- * binding/provider evidence ownership is storage-enforced against canonical definition;
-- * one authoritative operation owns each item poll epoch/generation;
-- * terminal snapshot closure is checked at transaction commit;
-- * provider evidence fingerprint/membership is checked at insert/commit.

BEGIN;

ALTER TABLE monitoring.metric_definition
    ADD CONSTRAINT metric_definition_owner_tuple_unique
    UNIQUE (tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation);

DO $$
DECLARE v_constraint NAME;
BEGIN
    SELECT c.conname INTO v_constraint
      FROM pg_constraint c
     WHERE c.conrelid='monitoring.metric_definition_provider_binding'::regclass
       AND c.confrelid='monitoring.metric_definition'::regclass
       AND c.contype='f';
    IF v_constraint IS NOT NULL THEN
        EXECUTE format('ALTER TABLE monitoring.metric_definition_provider_binding DROP CONSTRAINT %I',v_constraint);
    END IF;
END;
$$;
ALTER TABLE monitoring.metric_definition_provider_binding
    ADD CONSTRAINT metric_definition_binding_owner_fk
    FOREIGN KEY (tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation)
    REFERENCES monitoring.metric_definition(
        tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation
    );

DO $$
DECLARE v_constraint NAME;
BEGIN
    SELECT c.conname INTO v_constraint
      FROM pg_constraint c
     WHERE c.conrelid='monitoring.monitoring_metric_definition_provider_evidence'::regclass
       AND c.confrelid='monitoring.metric_definition'::regclass
       AND c.contype='f';
    IF v_constraint IS NOT NULL THEN
        EXECUTE format('ALTER TABLE monitoring.monitoring_metric_definition_provider_evidence DROP CONSTRAINT %I',v_constraint);
    END IF;
END;
$$;
ALTER TABLE monitoring.monitoring_metric_definition_provider_evidence
    ADD CONSTRAINT metric_definition_provider_evidence_owner_fk
    FOREIGN KEY (tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation)
    REFERENCES monitoring.metric_definition(
        tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation
    );

CREATE UNIQUE INDEX metric_definition_poll_authority_single_owner
ON monitoring.monitoring_sync_operation(
    tenant_id,monitoring_source_id,item_definition_poll_epoch,item_definition_poll_generation
)
WHERE responsibility_kind='metric_definition_sync'
  AND item_definition_poll_epoch IS NOT NULL
  AND item_definition_poll_generation IS NOT NULL;

CREATE OR REPLACE FUNCTION monitoring.wave4_mark_metric_binding_reconciliation(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_source_instance_generation TEXT,
    p_provider_external_ref TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE v_metric_definition_id TEXT;
BEGIN
    IF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric binding reconciliation marking requires guarded executor authority';
    END IF;
    SELECT b.metric_definition_id INTO v_metric_definition_id
      FROM monitoring.metric_definition_provider_binding AS b
     WHERE b.tenant_id=p_tenant_id
       AND b.monitoring_source_id=p_monitoring_source_id
       AND b.source_instance_generation=p_source_instance_generation
       AND b.provider_external_ref=p_provider_external_ref
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_definition_reconciliation_binding_missing';
    END IF;
    UPDATE monitoring.metric_definition AS d
       SET definition_evidence_state='reconciliation_required',updated_at=transaction_timestamp()
     WHERE d.tenant_id=p_tenant_id AND d.metric_definition_id=v_metric_definition_id;
    UPDATE monitoring.metric_definition_provider_binding AS b
       SET evidence_state='reconciliation_required',updated_at=transaction_timestamp()
     WHERE b.tenant_id=p_tenant_id AND b.metric_definition_id=v_metric_definition_id;
END;
$$;
ALTER FUNCTION monitoring.wave4_mark_metric_binding_reconciliation(TEXT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_definition_executor;
REVOKE EXECUTE ON FUNCTION monitoring.wave4_mark_metric_binding_reconciliation(TEXT,TEXT,TEXT,TEXT)
    FROM PUBLIC,jlmirror_wave4_metric_definition_invoker;

CREATE OR REPLACE FUNCTION monitoring.wave4_verify_metric_provider_evidence_insert()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_expected_fingerprint TEXT;
BEGIN
    IF NOT monitoring.wave4_metric_definition_executor_is_current_user() THEN
        RAISE EXCEPTION 'Metric definition evidence creation requires guarded executor authority';
    END IF;
    IF NEW.normalized_evidence->>'itemid' IS DISTINCT FROM NEW.provider_external_ref
       OR NEW.normalized_evidence->>'hostid' IS DISTINCT FROM NEW.provider_host_ref THEN
        RAISE EXCEPTION 'Metric provider evidence membership does not match normalized evidence';
    END IF;
    v_expected_fingerprint := encode(sha256(convert_to(NEW.normalized_evidence::text,'UTF8')),'hex');
    IF NEW.evidence_fingerprint IS DISTINCT FROM v_expected_fingerprint THEN
        RAISE EXCEPTION 'Metric provider evidence fingerprint mismatch';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER wave4_metric_definition_provider_evidence_insert_authority
ON monitoring.monitoring_metric_definition_provider_evidence;
CREATE TRIGGER wave4_metric_definition_provider_evidence_insert_authority
BEFORE INSERT ON monitoring.monitoring_metric_definition_provider_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_verify_metric_provider_evidence_insert();

CREATE OR REPLACE FUNCTION monitoring.wave4_verify_metric_snapshot_closure()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_members BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_sync_operation AS o
         WHERE o.tenant_id=NEW.tenant_id
           AND o.monitoring_sync_operation_id=NEW.monitoring_sync_operation_id
           AND o.responsibility_kind='metric_definition_sync'
           AND o.monitoring_source_id=NEW.monitoring_source_id
           AND o.source_instance_generation=NEW.source_instance_generation
           AND o.configuration_revision=NEW.configuration_revision
           AND o.scope_revision=NEW.scope_revision
           AND o.item_definition_poll_epoch=NEW.item_definition_poll_epoch
           AND o.item_definition_poll_generation=NEW.item_definition_poll_generation
           AND o.state=NEW.operation_state
           AND o.metric_definition_snapshot_evidence_id=NEW.metric_definition_snapshot_evidence_id
           AND o.claim_token IS NULL
           AND o.completed_at IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Metric definition snapshot is not closed by its terminal operation';
    END IF;
    IF NEW.operation_state='succeeded' THEN
        SELECT count(*) INTO v_members
          FROM monitoring.monitoring_metric_definition_provider_evidence AS e
         WHERE e.tenant_id=NEW.tenant_id
           AND e.metric_definition_snapshot_evidence_id=NEW.metric_definition_snapshot_evidence_id;
        IF v_members IS DISTINCT FROM NEW.item_count THEN
            RAISE EXCEPTION 'Metric definition snapshot item_count does not match closed provider evidence membership';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER wave4_metric_definition_snapshot_closure_deferred
AFTER INSERT ON monitoring.monitoring_metric_definition_snapshot_evidence
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_verify_metric_snapshot_closure();

CREATE OR REPLACE FUNCTION monitoring.wave4_verify_metric_provider_evidence_closure()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_metric_definition_snapshot_evidence AS s
         WHERE s.tenant_id=NEW.tenant_id
           AND s.metric_definition_snapshot_evidence_id=NEW.metric_definition_snapshot_evidence_id
           AND s.operation_state='succeeded'
           AND s.snapshot_complete
           AND s.operational_evidence_state='current'
           AND s.monitoring_source_id=NEW.monitoring_source_id
           AND s.source_instance_generation=NEW.source_instance_generation
    ) THEN
        RAISE EXCEPTION 'Metric provider evidence is not a member of a successful closed snapshot';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.metric_definition_provider_binding AS b
         WHERE b.tenant_id=NEW.tenant_id
           AND b.metric_definition_id=NEW.metric_definition_id
           AND b.monitoring_resource_id=NEW.monitoring_resource_id
           AND b.monitoring_source_id=NEW.monitoring_source_id
           AND b.source_instance_generation=NEW.source_instance_generation
           AND b.provider_external_ref=NEW.provider_external_ref
           AND b.provider_host_ref=NEW.provider_host_ref
    ) THEN
        RAISE EXCEPTION 'Metric provider evidence is not bound to the accepted provider mapping';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER wave4_metric_definition_provider_evidence_closure_deferred
AFTER INSERT ON monitoring.monitoring_metric_definition_provider_evidence
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_verify_metric_provider_evidence_closure();

COMMIT;
