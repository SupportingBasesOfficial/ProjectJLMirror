-- Wave 4 Problem State guarded enqueue/claim/completion lifecycle.
-- Authority: wave4.monitoring-problem-state@1.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_problem_state_operation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF TG_OP='INSERT' AND NEW.responsibility_kind IN ('problem_state_sync','problem_state_reconciliation') THEN
        IF NOT monitoring.wave4_problem_state_executor_is_current_user() THEN
            RAISE EXCEPTION 'Problem State work creation requires guarded executor authority';
        END IF;
        IF NEW.state <> 'pending' OR NEW.claim_token IS NOT NULL
           OR NEW.problem_poll_epoch IS NOT NULL OR NEW.problem_poll_generation IS NOT NULL
           OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL
           OR NEW.last_error_class IS NOT NULL OR NEW.attempt_count <> 0 THEN
            RAISE EXCEPTION 'Problem State operation must begin as clean pending work';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP='UPDATE' AND OLD.responsibility_kind IN ('problem_state_sync','problem_state_reconciliation') THEN
        IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.monitoring_sync_operation_id IS DISTINCT FROM OLD.monitoring_sync_operation_id
           OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
           OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
           OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision
           OR NEW.scope_revision IS DISTINCT FROM OLD.scope_revision
           OR NEW.responsibility_kind IS DISTINCT FROM OLD.responsibility_kind THEN
            RAISE EXCEPTION 'Problem State work identity/source/revision authority is immutable';
        END IF;
        IF NOT monitoring.wave4_problem_state_executor_is_current_user() AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Problem State lifecycle requires guarded executor authority';
        END IF;
        IF OLD.state IN ('succeeded','reconciliation_required','failed_terminal') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Terminal Problem State operation is immutable';
        END IF;
        IF OLD.problem_poll_epoch IS NOT NULL
           AND NEW.problem_poll_epoch IS DISTINCT FROM OLD.problem_poll_epoch THEN
            RAISE EXCEPTION 'Claimed Problem State poll epoch is immutable';
        END IF;
        IF OLD.problem_poll_generation IS NOT NULL
           AND NEW.problem_poll_generation IS DISTINCT FROM OLD.problem_poll_generation THEN
            RAISE EXCEPTION 'Claimed Problem State poll generation is immutable';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave4_problem_state_operation_guard_insert
BEFORE INSERT ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_problem_state_operation();
CREATE TRIGGER wave4_problem_state_operation_guard_update
BEFORE UPDATE ON monitoring.monitoring_sync_operation
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_guard_problem_state_operation();

CREATE OR REPLACE FUNCTION monitoring.reestablish_problem_state_runtime_admission(
    p_tenant_id TEXT,
    p_monitoring_source_id TEXT,
    p_problem_poll_epoch BIGINT,
    p_placement_version TEXT,
    p_recovery_generation TEXT,
    p_recovery_admission_ref TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
BEGIN
    IF p_problem_poll_epoch IS NULL OR p_problem_poll_epoch <= 0
       OR p_placement_version IS NULL OR p_placement_version=''
       OR p_recovery_generation IS NULL OR p_recovery_generation=''
       OR p_recovery_admission_ref IS NULL OR p_recovery_admission_ref='' THEN
        RAISE EXCEPTION 'monitoring.problem_state_invalid_recovery_admission';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_source AS s
         WHERE s.tenant_id=p_tenant_id
           AND s.monitoring_source_id=p_monitoring_source_id
           AND s.problem_poll_epoch=p_problem_poll_epoch
           AND s.operational_evidence_state='current'
    ) THEN
        RAISE EXCEPTION 'monitoring.problem_state_recovery_authority_not_current';
    END IF;

    INSERT INTO monitoring.monitoring_problem_state_runtime_admission(
        tenant_id,monitoring_source_id,problem_poll_epoch,
        placement_version,recovery_generation,recovery_admission_ref
    ) VALUES (
        p_tenant_id,p_monitoring_source_id,p_problem_poll_epoch,
        p_placement_version,p_recovery_generation,p_recovery_admission_ref
    )
    ON CONFLICT (tenant_id,monitoring_source_id) DO UPDATE
       SET problem_poll_epoch=EXCLUDED.problem_poll_epoch,
           placement_version=EXCLUDED.placement_version,
           recovery_generation=EXCLUDED.recovery_generation,
           recovery_admission_ref=EXCLUDED.recovery_admission_ref,
           admitted_at=transaction_timestamp();
END;
$$;
ALTER FUNCTION monitoring.reestablish_problem_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_recovery_authority;
REVOKE EXECUTE ON FUNCTION monitoring.reestablish_problem_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.reestablish_problem_state_runtime_admission(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.enqueue_zabbix_problem_state_sync(
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
        RAISE EXCEPTION 'monitoring.problem_state_invalid_enqueue_input';
    END IF;

    SELECT s.active_source_instance_generation,s.configuration_revision,s.scope_revision
      INTO v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=p_monitoring_source_id
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.problem_state_source_not_current';
    END IF;

    INSERT INTO monitoring.monitoring_sync_operation(
        tenant_id,monitoring_sync_operation_id,monitoring_source_id,
        source_instance_generation,configuration_revision,scope_revision,
        responsibility_kind,state
    ) VALUES (
        p_tenant_id,p_monitoring_sync_operation_id,p_monitoring_source_id,
        v_generation,v_configuration_revision,v_scope_revision,
        'problem_state_sync','pending'
    );
END;
$$;
ALTER FUNCTION monitoring.enqueue_zabbix_problem_state_sync(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_problem_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.enqueue_zabbix_problem_state_sync(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.enqueue_zabbix_problem_state_sync(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_problem_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.claim_zabbix_problem_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    problem_poll_epoch BIGINT,
    problem_poll_generation BIGINT
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
        RAISE EXCEPTION 'monitoring.problem_state_invalid_claim_token';
    END IF;

    SELECT o.monitoring_source_id,o.source_instance_generation,o.configuration_revision,o.scope_revision
      INTO v_source_id,v_generation,v_configuration_revision,v_scope_revision
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='problem_state_sync'
       AND o.state='pending'
       AND o.claim_token IS NULL
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.problem_state_not_claimable';
    END IF;

    SELECT s.problem_poll_epoch,s.problem_poll_generation+1
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
        RAISE EXCEPTION 'monitoring.problem_state_stale_authority';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_source_id
           AND a.problem_poll_epoch=v_poll_epoch
    ) THEN
        RAISE EXCEPTION 'monitoring.problem_state_recovery_admission_required';
    END IF;

    UPDATE monitoring.monitoring_source AS s
       SET problem_poll_generation=v_poll_generation,
           updated_at=transaction_timestamp()
     WHERE s.tenant_id=p_tenant_id AND s.monitoring_source_id=v_source_id;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state='running',claim_token=p_claim_token,started_at=transaction_timestamp(),
           attempt_count=o.attempt_count+1,problem_poll_epoch=v_poll_epoch,
           problem_poll_generation=v_poll_generation
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN QUERY SELECT v_source_id,v_generation,v_configuration_revision,v_scope_revision,
                        v_poll_epoch,v_poll_generation;
END;
$$;
ALTER FUNCTION monitoring.claim_zabbix_problem_state(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_problem_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_problem_state(TEXT,TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_problem_state(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_problem_state_invoker;

CREATE OR REPLACE FUNCTION monitoring.complete_zabbix_problem_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_active_problems JSONB,
    p_recoveries JSONB,
    p_complete_snapshot BOOLEAN
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_operation monitoring.monitoring_sync_operation%ROWTYPE;
    v_source monitoring.monitoring_source%ROWTYPE;
    v_item JSONB;
    v_problem_id TEXT;
    v_eventid TEXT;
    v_triggerid TEXT;
    v_resource_id TEXT;
    v_severity TEXT;
    v_summary TEXT;
    v_opened_at TIMESTAMPTZ;
    v_resolved_at TIMESTAMPTZ;
    v_existing monitoring.monitoring_problem%ROWTYPE;
    v_binding monitoring.monitoring_problem_provider_binding%ROWTYPE;
    v_transition_id TEXT;
    v_revision BIGINT;
    v_seen_eventids TEXT[] := ARRAY[]::TEXT[];
BEGIN
    IF p_active_problems IS NULL OR jsonb_typeof(p_active_problems)<>'array'
       OR p_recoveries IS NULL OR jsonb_typeof(p_recoveries)<>'array' THEN
        RAISE EXCEPTION 'monitoring.problem_state_invalid_completion_payload';
    END IF;
    IF jsonb_array_length(p_active_problems)>20000 OR jsonb_array_length(p_recoveries)>20000 THEN
        RAISE EXCEPTION 'monitoring.problem_state_completion_overbound';
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
        RAISE EXCEPTION 'monitoring.problem_state_completion_not_claimed';
    END IF;

    SELECT s.* INTO v_source
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_operation.monitoring_source_id
       AND s.active_source_instance_generation=v_operation.source_instance_generation
       AND s.configuration_revision=v_operation.configuration_revision
       AND s.scope_revision=v_operation.scope_revision
       AND s.problem_poll_epoch=v_operation.problem_poll_epoch
       AND s.problem_poll_generation=v_operation.problem_poll_generation
       AND s.operational_evidence_state='current'
     FOR UPDATE;
    IF NOT FOUND OR NOT EXISTS (
        SELECT 1 FROM monitoring.monitoring_problem_state_runtime_admission AS a
         WHERE a.tenant_id=p_tenant_id
           AND a.monitoring_source_id=v_operation.monitoring_source_id
           AND a.problem_poll_epoch=v_operation.problem_poll_epoch
    ) THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',completed_at=transaction_timestamp(),
               last_error_class='execution.superseded_problem_state_poll_authority',claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN 'reconciliation_required';
    END IF;

    FOR v_item IN SELECT value FROM jsonb_array_elements(p_active_problems) LOOP
        v_problem_id:=v_item->>'problem_id';
        v_eventid:=v_item->>'provider_eventid';
        v_triggerid:=v_item->>'provider_trigger_ref';
        v_resource_id:=v_item->>'monitoring_resource_id';
        v_severity:=v_item->>'severity_class';
        v_summary:=v_item->>'summary';
        BEGIN
            v_opened_at:=to_timestamp((v_item->>'opened_at_epoch_seconds')::BIGINT);
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'monitoring.problem_state_invalid_provider_time';
        END;

        IF v_problem_id IS NULL OR v_problem_id='' OR length(v_problem_id)>512
           OR v_eventid IS NULL OR v_eventid='' OR length(v_eventid)>256
           OR v_triggerid IS NULL OR v_triggerid='' OR length(v_triggerid)>256
           OR v_resource_id IS NULL OR v_resource_id=''
           OR v_severity NOT IN ('unknown','informational','warning','degraded','critical')
           OR v_summary IS NULL OR v_summary='' OR length(v_summary)>8192 THEN
            RAISE EXCEPTION 'monitoring.problem_state_invalid_problem_payload';
        END IF;
        IF v_eventid=ANY(v_seen_eventids) THEN
            RAISE EXCEPTION 'monitoring.problem_state_duplicate_provider_event';
        END IF;
        v_seen_eventids:=array_append(v_seen_eventids,v_eventid);

        IF NOT EXISTS (
            SELECT 1 FROM monitoring.monitoring_resource AS r
             WHERE r.tenant_id=p_tenant_id
               AND r.monitoring_resource_id=v_resource_id
               AND r.monitoring_source_id=v_operation.monitoring_source_id
               AND r.source_instance_generation=v_operation.source_instance_generation
               AND r.scope_state='in_scope'
               AND r.scope_evidence_state='current'
               AND r.scope_projection_revision=v_operation.scope_revision
        ) THEN
            RAISE EXCEPTION 'monitoring.problem_state_resource_association_not_current';
        END IF;

        INSERT INTO monitoring.monitoring_problem_provider_binding(
            tenant_id,problem_id,monitoring_source_id,source_instance_generation,
            monitoring_resource_id,provider_profile,provider_external_ref,provider_trigger_ref
        ) VALUES (
            p_tenant_id,v_problem_id,v_operation.monitoring_source_id,v_operation.source_instance_generation,
            v_resource_id,'zabbix',v_eventid,v_triggerid
        ) ON CONFLICT DO NOTHING;

        SELECT b.* INTO v_binding
          FROM monitoring.monitoring_problem_provider_binding AS b
         WHERE b.tenant_id=p_tenant_id
           AND b.monitoring_source_id=v_operation.monitoring_source_id
           AND b.source_instance_generation=v_operation.source_instance_generation
           AND b.provider_profile='zabbix'
           AND b.provider_external_ref=v_eventid
         FOR KEY SHARE;
        IF NOT FOUND OR v_binding.problem_id<>v_problem_id
           OR v_binding.monitoring_resource_id<>v_resource_id
           OR v_binding.provider_trigger_ref<>v_triggerid THEN
            RAISE EXCEPTION 'monitoring.problem_state_provider_identity_collision';
        END IF;

        SELECT p.* INTO v_existing
          FROM monitoring.monitoring_problem AS p
         WHERE p.tenant_id=p_tenant_id AND p.problem_id=v_problem_id
         FOR UPDATE;

        IF NOT FOUND THEN
            INSERT INTO monitoring.monitoring_problem(
                tenant_id,problem_id,monitoring_source_id,source_instance_generation,
                monitoring_resource_id,problem_state,severity_class,summary,
                opened_at,resolved_at,last_confirmed_at,evidence_state,projection_revision,
                problem_poll_epoch,problem_poll_generation,provider_acknowledged,provider_metadata
            ) VALUES (
                p_tenant_id,v_problem_id,v_operation.monitoring_source_id,v_operation.source_instance_generation,
                v_resource_id,'active',v_severity,v_summary,v_opened_at,NULL,v_opened_at,'current',1,
                v_operation.problem_poll_epoch,v_operation.problem_poll_generation,
                COALESCE((v_item->>'provider_acknowledged')::BOOLEAN,FALSE),
                COALESCE(v_item->'provider_metadata','{}'::jsonb)
            );
            v_transition_id:='problem-transition:'||v_problem_id||':1';
            INSERT INTO monitoring.monitoring_problem_transition(
                tenant_id,problem_transition_id,problem_id,monitoring_source_id,
                source_instance_generation,monitoring_resource_id,from_problem_state,to_problem_state,
                from_severity_class,to_severity_class,transition_reason,provider_evidence_ref,projection_revision
            ) VALUES (
                p_tenant_id,v_transition_id,v_problem_id,v_operation.monitoring_source_id,
                v_operation.source_instance_generation,v_resource_id,NULL,'active',NULL,v_severity,
                'provider_positive','zabbix-problem:'||v_eventid,1
            );
        ELSE
            IF v_existing.problem_state='resolved' THEN
                RAISE EXCEPTION 'monitoring.problem_state_resolved_event_reappeared';
            END IF;
            IF v_existing.severity_class<>v_severity
               OR v_existing.summary<>v_summary
               OR v_existing.provider_acknowledged<>COALESCE((v_item->>'provider_acknowledged')::BOOLEAN,FALSE)
               OR v_existing.provider_metadata<>COALESCE(v_item->'provider_metadata','{}'::jsonb) THEN
                v_revision:=v_existing.projection_revision+1;
                UPDATE monitoring.monitoring_problem AS p
                   SET severity_class=v_severity,summary=v_summary,last_confirmed_at=v_opened_at,
                       evidence_state='current',projection_revision=v_revision,
                       problem_poll_epoch=v_operation.problem_poll_epoch,
                       problem_poll_generation=v_operation.problem_poll_generation,
                       provider_acknowledged=COALESCE((v_item->>'provider_acknowledged')::BOOLEAN,FALSE),
                       provider_metadata=COALESCE(v_item->'provider_metadata','{}'::jsonb),
                       updated_at=transaction_timestamp()
                 WHERE p.tenant_id=p_tenant_id AND p.problem_id=v_problem_id;
                IF v_existing.severity_class<>v_severity THEN
                    v_transition_id:='problem-transition:'||v_problem_id||':'||v_revision::TEXT;
                    INSERT INTO monitoring.monitoring_problem_transition(
                        tenant_id,problem_transition_id,problem_id,monitoring_source_id,
                        source_instance_generation,monitoring_resource_id,from_problem_state,to_problem_state,
                        from_severity_class,to_severity_class,transition_reason,provider_evidence_ref,projection_revision
                    ) VALUES (
                        p_tenant_id,v_transition_id,v_problem_id,v_operation.monitoring_source_id,
                        v_operation.source_instance_generation,v_resource_id,'active','active',
                        v_existing.severity_class,v_severity,'severity_change','zabbix-problem:'||v_eventid,v_revision
                    );
                END IF;
            ELSE
                UPDATE monitoring.monitoring_problem AS p
                   SET last_confirmed_at=GREATEST(p.last_confirmed_at,v_opened_at),evidence_state='current',
                       problem_poll_epoch=v_operation.problem_poll_epoch,
                       problem_poll_generation=v_operation.problem_poll_generation,
                       updated_at=transaction_timestamp()
                 WHERE p.tenant_id=p_tenant_id AND p.problem_id=v_problem_id;
            END IF;
        END IF;
    END LOOP;

    FOR v_item IN SELECT value FROM jsonb_array_elements(p_recoveries) LOOP
        v_eventid:=v_item->>'provider_eventid';
        IF v_eventid IS NULL OR v_eventid='' OR length(v_eventid)>256
           OR v_item->>'recovery_eventid' IS NULL OR v_item->>'recovery_eventid'='' THEN
            RAISE EXCEPTION 'monitoring.problem_state_invalid_recovery_payload';
        END IF;
        BEGIN
            v_resolved_at:=to_timestamp((v_item->>'resolved_at_epoch_seconds')::BIGINT);
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'monitoring.problem_state_invalid_recovery_time';
        END;

        SELECT p.* INTO v_existing
          FROM monitoring.monitoring_problem_provider_binding AS b
          JOIN monitoring.monitoring_problem AS p
            ON p.tenant_id=b.tenant_id AND p.problem_id=b.problem_id
         WHERE b.tenant_id=p_tenant_id
           AND b.monitoring_source_id=v_operation.monitoring_source_id
           AND b.source_instance_generation=v_operation.source_instance_generation
           AND b.provider_profile='zabbix'
           AND b.provider_external_ref=v_eventid
         FOR UPDATE OF p;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'monitoring.problem_state_recovery_without_known_problem';
        END IF;
        IF v_existing.problem_state='active' THEN
            v_revision:=v_existing.projection_revision+1;
            UPDATE monitoring.monitoring_problem AS p
               SET problem_state='resolved',resolved_at=v_resolved_at,last_confirmed_at=v_resolved_at,
                   evidence_state='current',projection_revision=v_revision,
                   problem_poll_epoch=v_operation.problem_poll_epoch,
                   problem_poll_generation=v_operation.problem_poll_generation,
                   updated_at=transaction_timestamp()
             WHERE p.tenant_id=p_tenant_id AND p.problem_id=v_existing.problem_id;
            v_transition_id:='problem-transition:'||v_existing.problem_id||':'||v_revision::TEXT;
            INSERT INTO monitoring.monitoring_problem_transition(
                tenant_id,problem_transition_id,problem_id,monitoring_source_id,
                source_instance_generation,monitoring_resource_id,from_problem_state,to_problem_state,
                from_severity_class,to_severity_class,transition_reason,provider_evidence_ref,projection_revision
            ) VALUES (
                p_tenant_id,v_transition_id,v_existing.problem_id,v_operation.monitoring_source_id,
                v_operation.source_instance_generation,v_existing.monitoring_resource_id,'active','resolved',
                v_existing.severity_class,v_existing.severity_class,'provider_recovery',
                'zabbix-recovery:'||(v_item->>'recovery_eventid'),v_revision
            );
        ELSIF v_existing.resolved_at IS DISTINCT FROM v_resolved_at THEN
            RAISE EXCEPTION 'monitoring.problem_state_conflicting_recovery_evidence';
        END IF;
    END LOOP;

    IF p_complete_snapshot THEN
        FOR v_existing IN
            SELECT p.*
              FROM monitoring.monitoring_problem AS p
              JOIN monitoring.monitoring_problem_provider_binding AS b
                ON b.tenant_id=p.tenant_id AND b.problem_id=p.problem_id
             WHERE p.tenant_id=p_tenant_id
               AND p.monitoring_source_id=v_operation.monitoring_source_id
               AND p.source_instance_generation=v_operation.source_instance_generation
               AND p.problem_state='active'
               AND NOT (b.provider_external_ref=ANY(v_seen_eventids))
             FOR UPDATE OF p
        LOOP
            v_revision:=v_existing.projection_revision+1;
            v_resolved_at:=transaction_timestamp();
            UPDATE monitoring.monitoring_problem AS p
               SET problem_state='resolved',resolved_at=v_resolved_at,last_confirmed_at=v_resolved_at,
                   evidence_state='current',projection_revision=v_revision,
                   problem_poll_epoch=v_operation.problem_poll_epoch,
                   problem_poll_generation=v_operation.problem_poll_generation,
                   updated_at=transaction_timestamp()
             WHERE p.tenant_id=p_tenant_id AND p.problem_id=v_existing.problem_id;
            v_transition_id:='problem-transition:'||v_existing.problem_id||':'||v_revision::TEXT;
            INSERT INTO monitoring.monitoring_problem_transition(
                tenant_id,problem_transition_id,problem_id,monitoring_source_id,
                source_instance_generation,monitoring_resource_id,from_problem_state,to_problem_state,
                from_severity_class,to_severity_class,transition_reason,provider_evidence_ref,projection_revision
            ) VALUES (
                p_tenant_id,v_transition_id,v_existing.problem_id,v_operation.monitoring_source_id,
                v_operation.source_instance_generation,v_existing.monitoring_resource_id,'active','resolved',
                v_existing.severity_class,v_existing.severity_class,'authoritative_negative',
                'problem.get:complete:'||p_monitoring_sync_operation_id,v_revision
            );
        END LOOP;
    ELSE
        UPDATE monitoring.monitoring_problem AS p
           SET evidence_state='reconciliation_required',updated_at=transaction_timestamp()
         WHERE p.tenant_id=p_tenant_id
           AND p.monitoring_source_id=v_operation.monitoring_source_id
           AND p.source_instance_generation=v_operation.source_instance_generation
           AND p.problem_state='active'
           AND NOT EXISTS (
               SELECT 1 FROM monitoring.monitoring_problem_provider_binding AS b
                WHERE b.tenant_id=p.tenant_id AND b.problem_id=p.problem_id
                  AND b.provider_external_ref=ANY(v_seen_eventids)
           );
    END IF;

    UPDATE monitoring.monitoring_sync_operation AS o
       SET state=CASE WHEN p_complete_snapshot THEN 'succeeded' ELSE 'reconciliation_required' END,
           completed_at=transaction_timestamp(),claim_token=NULL,
           last_error_class=CASE WHEN p_complete_snapshot THEN NULL ELSE 'monitoring.problem_snapshot_incomplete' END
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;

    RETURN CASE WHEN p_complete_snapshot THEN 'succeeded' ELSE 'reconciliation_required' END;
END;
$$;
ALTER FUNCTION monitoring.complete_zabbix_problem_state(TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN)
    OWNER TO jlmirror_wave4_problem_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_problem_state(TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_problem_state(TEXT,TEXT,TEXT,JSONB,JSONB,BOOLEAN)
    TO jlmirror_wave4_problem_state_invoker;

COMMIT;
