-- Wave 4 Metric Current State claim/completion.
-- Authority: wave4.monitoring-metric-current-state@1.
-- Durable transition evidence is sufficient for deterministic later publication;
-- this slice does not grant a second outbox/dispatch substrate.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_metric_current_state_operation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='INSERT' AND NEW.responsibility_kind='metric_current_state_sync' THEN
        IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() THEN
            RAISE EXCEPTION 'Metric Current State work creation requires guarded executor authority';
        END IF;
        IF NEW.state <> 'pending' OR NEW.claim_token IS NOT NULL
           OR NEW.current_state_poll_epoch IS NOT NULL
           OR NEW.current_state_poll_generation IS NOT NULL
           OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL
           OR NEW.last_error_class IS NOT NULL OR NEW.attempt_count <> 0 THEN
            RAISE EXCEPTION 'Metric Current State operation must begin as clean pending work';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP='UPDATE' AND OLD.responsibility_kind='metric_current_state_sync' THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.monitoring_sync_operation_id IS DISTINCT FROM OLD.monitoring_sync_operation_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
           OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
           OR NEW.responsibility_kind IS DISTINCT FROM OLD.responsibility_kind THEN
            RAISE EXCEPTION 'Metric Current State work identity/source/revision authority is immutable';
        END IF;
        IF NOT monitoring.wave4_metric_current_state_executor_is_current_user() AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Metric Current State lifecycle requires guarded executor authority';
        END IF;
        IF OLD.state IN ('succeeded','reconciliation_required','failed_terminal') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Terminal Metric Current State operation is immutable';
        END IF;
        IF OLD.current_state_poll_epoch IS NOT NULL
           AND NEW.current_state_poll_epoch IS DISTINCT FROM OLD.current_state_poll_epoch THEN
            RAISE EXCEPTION 'Claimed Metric Current State poll epoch is immutable';
        END IF;
        IF OLD.current_state_poll_generation IS NOT NULL
           AND NEW.current_state_poll_generation IS DISTINCT FROM OLD.current_state_poll_generation THEN
            RAISE EXCEPTION 'Claimed Metric Current State poll generation is immutable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_metric_current_state_operation_guard_insert
BEFORE INSERT ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_current_state_operation();
CREATE TRIGGER wave4_metric_current_state_operation_guard_update
BEFORE UPDATE ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_metric_current_state_operation();

CREATE OR REPLACE FUNCTION monitoring.enqueue_zabbix_metric_current_state_sync(
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
    IF p_tenant_id IS NULL OR p_tenant_id='' OR length(p_tenant_id)>256
       OR p_monitoring_source_id IS NULL OR p_monitoring_source_id='' OR length(p_monitoring_source_id)>512
       OR p_monitoring_sync_operation_id IS NULL OR p_monitoring_sync_operation_id='' OR length(p_monitoring_sync_operation_id)>512 THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_enqueue_input';
    END IF;

    SELECT s.active_source_instance_generation,s.configuration_revision,s.scope_revision
      INTO v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=p_monitoring_source_id
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_source_not_current';
    END IF;

    INSERT INTO monitoring.monitoring_sync_operation(
        tenant_id,monitoring_sync_operation_id,monitoring_source_id,
        source_instance_generation,configuration_revision,scope_revision,
        responsibility_kind,state
    ) VALUES (
        p_tenant_id,p_monitoring_sync_operation_id,p_monitoring_source_id,
        v_generation,v_configuration_revision,v_scope_revision,
        'metric_current_state_sync','pending'
    );
END;
$$;
ALTER FUNCTION monitoring.enqueue_zabbix_metric_current_state_sync(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.enqueue_zabbix_metric_current_state_sync(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.enqueue_zabbix_metric_current_state_sync(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_current_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.claim_zabbix_metric_current_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    current_state_poll_epoch BIGINT,
    current_state_poll_generation BIGINT
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
    IF p_claim_token IS NULL OR p_claim_token='' OR length(p_claim_token)>512
       OR p_claim_token<>btrim(p_claim_token) OR p_claim_token~'[[:cntrl:]]' THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_claim_token';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='pending'
       AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_not_claimable';
    END IF;

    SELECT s.current_state_poll_epoch,s.current_state_poll_generation+1
      INTO v_poll_epoch,v_poll_generation
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
       AND s.active_source_instance_generation=v_generation
       AND s.configuration_revision=v_configuration_revision
       AND s.scope_revision=v_scope_revision
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_stale_authority';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM monitoring.monitoring_metric_current_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_source_id
           AND a.current_state_poll_epoch=v_poll_epoch
    ) THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_recovery_admission_required';
    END IF;

    UPDATE monitoring.monitoring_source AS s
       SET current_state_poll_generation=v_poll_generation,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='running',claim_token=p_claim_token,started_at=transaction_timestamp(),
           attempt_count=o.attempt_count+1,current_state_poll_epoch=v_poll_epoch,
           current_state_poll_generation=v_poll_generation
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN QUERY SELECT v_source_id,v_generation,v_configuration_revision,v_scope_revision,
                        v_poll_epoch,v_poll_generation;
END;
$$;
ALTER FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_current_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.list_zabbix_metric_current_targets(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_after_metric_definition_id TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
) RETURNS TABLE (
    metric_definition_id TEXT,
    monitoring_resource_id TEXT,
    provider_external_ref TEXT,
    value_kind TEXT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
    v_generation TEXT;
    v_scope_revision BIGINT;
BEGIN
    IF p_limit < 1 OR p_limit > 5000 THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_target_page_limit';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.scope_revision
      INTO v_source_id,v_generation,v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_claim_not_current';
    END IF;

    RETURN QUERY
    SELECT d.metric_definition_id,d.monitoring_resource_id,b.provider_external_ref,d.value_kind
      FROM monitoring.metric_definition AS d
      JOIN monitoring.metric_definition_provider_binding AS b
        ON b.tenant_id=d.tenant_id
       AND b.metric_definition_id=d.metric_definition_id
       AND b.monitoring_source_id=d.monitoring_source_id
       AND b.source_instance_generation=d.source_instance_generation
       AND b.monitoring_resource_id=d.monitoring_resource_id
     WHERE d.tenant_id=p_tenant_id
       AND d.monitoring_source_id=v_source_id
       AND d.source_instance_generation=v_generation
       AND d.definition_state='active'
       AND d.definition_evidence_state='current'
       AND d.scope_state='in_scope'
       AND d.scope_evidence_state='current'
       AND d.scope_projection_revision=v_scope_revision
       AND b.evidence_state='current'
       AND b.provider_operational_state='enabled'
       AND (p_after_metric_definition_id IS NULL OR d.metric_definition_id>p_after_metric_definition_id)
     ORDER BY d.metric_definition_id
     LIMIT p_limit;
END;
$$;
ALTER FUNCTION monitoring.list_zabbix_metric_current_targets(TEXT,TEXT,TEXT,TEXT,INTEGER)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.list_zabbix_metric_current_targets(TEXT,TEXT,TEXT,TEXT,INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.list_zabbix_metric_current_targets(TEXT,TEXT,TEXT,TEXT,INTEGER)
    TO jlmirror_wave4_metric_current_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_metric_current_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_observations JSONB
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_operation monitoring.monitoring_sync_operation%ROWTYPE;
    v_source monitoring.monitoring_source%ROWTYPE;
    v_item JSONB;
    v_count BIGINT;
    v_metric_id TEXT;
    v_resource_id TEXT;
    v_provider_ref TEXT;
    v_observation_id TEXT;
    v_value_kind TEXT;
    v_canonical_value JSONB;
    v_provider_clock BIGINT;
    v_provider_ns INTEGER;
    v_observed_at TIMESTAMPTZ;
    v_existing monitoring.monitoring_metric_observation_acceptance%ROWTYPE;
    v_current monitoring.metric_current_state%ROWTYPE;
    v_semantic_change BOOLEAN;
    v_projection_revision BIGINT;
    v_transition_id TEXT;
BEGIN
    IF p_observations IS NULL OR jsonb_typeof(p_observations)<>'array' THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_invalid_observation_batch';
    END IF;
    v_count:=jsonb_array_length(p_observations);
    IF v_count>200000 THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_observation_batch_overbound';
    END IF;

    SELECT o.* INTO v_operation
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_completion_not_claimed';
    END IF;

    SELECT s.* INTO v_source
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_operation.monitoring_source_id
       AND s.active_source_instance_generation=v_operation.source_instance_generation
       AND s.configuration_revision=v_operation.configuration_revision
       AND s.scope_revision=v_operation.scope_revision
       AND s.current_state_poll_epoch=v_operation.current_state_poll_epoch
       AND s.current_state_poll_generation=v_operation.current_state_poll_generation
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND OR NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_metric_current_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_operation.monitoring_source_id
           AND a.current_state_poll_epoch=v_operation.current_state_poll_epoch
    ) THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',completed_at=transaction_timestamp(),
               last_error_class='monitoring.current_state_stale_authority',claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN 'reconciliation_required';
    END IF;

    -- Full preflight: shape, duplicate provider observation identity and canonical target authority.
    IF EXISTS (
        SELECT 1
          FROM jsonb_array_elements(p_observations) AS e(value)
         WHERE jsonb_typeof(e.value)<>'object'
            OR NOT (e.value ?& ARRAY['metric_definition_id','provider_external_ref','observation_id','provider_clock','provider_ns','value_kind','canonical_value'])
    ) THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',completed_at=transaction_timestamp(),
               last_error_class='provider.protocol_invalid',claim_token=NULL
         WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN 'reconciliation_required';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM (
            SELECT e.value->>'provider_external_ref' AS provider_ref,
                   (e.value->>'provider_clock') AS provider_clock,
                   (e.value->>'provider_ns') AS provider_ns,
                   count(*) AS n
              FROM jsonb_array_elements(p_observations) AS e(value)
             GROUP BY 1,2,3
          ) AS q WHERE q.n>1
    ) THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',completed_at=transaction_timestamp(),
               last_error_class='provider.protocol_invalid',claim_token=NULL
         WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN 'reconciliation_required';
    END IF;

    FOR v_item IN SELECT value FROM jsonb_array_elements(p_observations) AS e(value)
    LOOP
        BEGIN
            v_metric_id:=v_item->>'metric_definition_id';
            v_provider_ref:=v_item->>'provider_external_ref';
            v_observation_id:=v_item->>'observation_id';
            v_provider_clock:=(v_item->>'provider_clock')::BIGINT;
            v_provider_ns:=(v_item->>'provider_ns')::INTEGER;
            v_value_kind:=v_item->>'value_kind';
            v_canonical_value:=v_item->'canonical_value';
        EXCEPTION WHEN OTHERS THEN
            UPDATE monitoring.monitoring_sync_operation AS o
               SET state='reconciliation_required',completed_at=transaction_timestamp(),
                   last_error_class='provider.protocol_invalid',claim_token=NULL
             WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
            RETURN 'reconciliation_required';
        END;

        IF v_metric_id IS NULL OR v_metric_id='' OR length(v_metric_id)>512
           OR v_provider_ref IS NULL OR v_provider_ref='' OR length(v_provider_ref)>256
           OR v_observation_id IS NULL OR v_observation_id='' OR length(v_observation_id)>512
           OR v_provider_clock<=0 OR v_provider_ns<0 OR v_provider_ns>999999999
           OR v_value_kind NOT IN ('number','integer','boolean','string','text','log')
           OR v_canonical_value IS NULL
           OR octet_length(v_canonical_value::text)>131072 THEN
            UPDATE monitoring.monitoring_sync_operation AS o
               SET state='reconciliation_required',completed_at=transaction_timestamp(),
                   last_error_class='provider.protocol_invalid',claim_token=NULL
             WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
            RETURN 'reconciliation_required';
        END IF;

        SELECT d.monitoring_resource_id INTO v_resource_id
          FROM monitoring.metric_definition AS d
          JOIN monitoring.metric_definition_provider_binding AS b
            ON b.tenant_id=d.tenant_id AND b.metric_definition_id=d.metric_definition_id
           AND b.monitoring_source_id=d.monitoring_source_id
           AND b.source_instance_generation=d.source_instance_generation
           AND b.monitoring_resource_id=d.monitoring_resource_id
         WHERE d.tenant_id=p_tenant_id
           AND d.metric_definition_id=v_metric_id
           AND d.monitoring_source_id=v_operation.monitoring_source_id
           AND d.source_instance_generation=v_operation.source_instance_generation
           AND d.definition_state='active'
           AND d.definition_evidence_state='current'
           AND d.scope_state='in_scope'
           AND d.scope_evidence_state='current'
           AND d.scope_projection_revision=v_operation.scope_revision
           AND d.value_kind=v_value_kind
           AND b.provider_external_ref=v_provider_ref
           AND b.evidence_state='current'
           AND b.provider_operational_state='enabled';
        IF NOT FOUND THEN
            UPDATE monitoring.monitoring_sync_operation AS o
               SET state='reconciliation_required',completed_at=transaction_timestamp(),
                   last_error_class='monitoring.current_state_target_not_current',claim_token=NULL
             WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
            RETURN 'reconciliation_required';
        END IF;

        SELECT a.* INTO v_existing
          FROM monitoring.monitoring_metric_observation_acceptance AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_operation.monitoring_source_id
           AND a.source_instance_generation=v_operation.source_instance_generation
           AND a.provider_external_ref=v_provider_ref
           AND a.provider_clock=v_provider_clock
           AND a.provider_ns=v_provider_ns;
        IF FOUND AND (
            v_existing.metric_definition_id IS DISTINCT FROM v_metric_id
            OR v_existing.monitoring_resource_id IS DISTINCT FROM v_resource_id
            OR v_existing.value_kind IS DISTINCT FROM v_value_kind
            OR v_existing.canonical_value IS DISTINCT FROM v_canonical_value
        ) THEN
            UPDATE monitoring.monitoring_sync_operation AS o
               SET state='reconciliation_required',completed_at=transaction_timestamp(),
                   last_error_class='monitoring.current_state_observation_identity_conflict',claim_token=NULL
             WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
            RETURN 'reconciliation_required';
        END IF;
    END LOOP;

    -- Mutation phase. All preflight checks above must pass before any durable acceptance occurs.
    FOR v_item IN SELECT value FROM jsonb_array_elements(p_observations) AS e(value)
    LOOP
        v_metric_id:=v_item->>'metric_definition_id';
        v_provider_ref:=v_item->>'provider_external_ref';
        v_observation_id:=v_item->>'observation_id';
        v_provider_clock:=(v_item->>'provider_clock')::BIGINT;
        v_provider_ns:=(v_item->>'provider_ns')::INTEGER;
        v_value_kind:=v_item->>'value_kind';
        v_canonical_value:=v_item->'canonical_value';
        SELECT d.monitoring_resource_id INTO STRICT v_resource_id
          FROM monitoring.metric_definition AS d
         WHERE d.tenant_id=p_tenant_id AND d.metric_definition_id=v_metric_id;

        SELECT a.* INTO v_existing
          FROM monitoring.monitoring_metric_observation_acceptance AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_operation.monitoring_source_id
           AND a.source_instance_generation=v_operation.source_instance_generation
           AND a.provider_external_ref=v_provider_ref
           AND a.provider_clock=v_provider_clock
           AND a.provider_ns=v_provider_ns;

        IF FOUND THEN
            -- Exact accepted-observation replay is idempotent and never regresses Current.
            CONTINUE;
        END IF;

        v_observed_at:=to_timestamp(v_provider_clock) + (v_provider_ns::DOUBLE PRECISION / 1000000000.0) * interval '1 second';

        INSERT INTO monitoring.monitoring_metric_observation_acceptance(
            tenant_id,observation_id,monitoring_sync_operation_id,monitoring_source_id,
            source_instance_generation,monitoring_resource_id,metric_definition_id,
            provider_profile,provider_external_ref,provider_clock,provider_ns,observed_at,
            value_kind,canonical_value,configuration_revision,scope_revision,
            current_state_poll_epoch,current_state_poll_generation,history_projection_state
        ) VALUES (
            p_tenant_id,v_observation_id,p_monitoring_sync_operation_id,v_operation.monitoring_source_id,
            v_operation.source_instance_generation,v_resource_id,v_metric_id,'zabbix',v_provider_ref,
            v_provider_clock,v_provider_ns,v_observed_at,v_value_kind,v_canonical_value,
            v_operation.configuration_revision,v_operation.scope_revision,
            v_operation.current_state_poll_epoch,v_operation.current_state_poll_generation,'pending'
        );

        SELECT c.* INTO v_current
          FROM monitoring.metric_current_state AS c
         WHERE c.tenant_id=p_tenant_id AND c.metric_definition_id=v_metric_id
         FOR UPDATE;

        IF NOT FOUND THEN
            v_semantic_change:=TRUE;
            v_projection_revision:=1;
            INSERT INTO monitoring.metric_current_state(
                tenant_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,
                source_instance_generation,current_observation_id,observed_at,accepted_at,
                value_kind,canonical_value,evidence_state,projection_revision,
                current_state_poll_epoch,current_state_poll_generation,last_changed_at
            ) VALUES (
                p_tenant_id,v_metric_id,v_resource_id,v_operation.monitoring_source_id,
                v_operation.source_instance_generation,v_observation_id,v_observed_at,transaction_timestamp(),
                v_value_kind,v_canonical_value,'current',v_projection_revision,
                v_operation.current_state_poll_epoch,v_operation.current_state_poll_generation,transaction_timestamp()
            );
        ELSE
            v_semantic_change:=v_current.canonical_value IS DISTINCT FROM v_canonical_value;
            v_projection_revision:=v_current.projection_revision+1;
            UPDATE monitoring.metric_current_state AS c
               SET current_observation_id=v_observation_id,
                   observed_at=v_observed_at,
                   accepted_at=transaction_timestamp(),
                   canonical_value=v_canonical_value,
                   evidence_state='current',
                   projection_revision=v_projection_revision,
                   current_state_poll_epoch=v_operation.current_state_poll_epoch,
                   current_state_poll_generation=v_operation.current_state_poll_generation,
                   last_changed_at=CASE WHEN v_semantic_change THEN transaction_timestamp() ELSE c.last_changed_at END,
                   updated_at=transaction_timestamp()
             WHERE c.tenant_id=p_tenant_id AND c.metric_definition_id=v_metric_id;
        END IF;

        IF v_semantic_change THEN
            v_transition_id:=v_observation_id || ':current-state-transition';
            INSERT INTO monitoring.monitoring_metric_current_state_transition(
                tenant_id,current_state_transition_id,metric_definition_id,monitoring_resource_id,
                monitoring_source_id,source_instance_generation,from_observation_id,to_observation_id,
                projection_revision,evidence_state,occurred_at
            ) VALUES (
                p_tenant_id,v_transition_id,v_metric_id,v_resource_id,v_operation.monitoring_source_id,
                v_operation.source_instance_generation,
                CASE WHEN v_current.metric_definition_id IS NULL THEN NULL ELSE v_current.current_observation_id END,
                v_observation_id,v_projection_revision,'current',transaction_timestamp()
            );
        END IF;
    END LOOP;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='succeeded',completed_at=transaction_timestamp(),last_error_class=NULL,claim_token=NULL
     WHERE o.tenant_id=p_tenant_id AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
    RETURN 'succeeded';
END;
$$;
ALTER FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    TO jlmirror_wave4_metric_current_state_invoker;

COMMIT;
