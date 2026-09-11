-- Wave 4 Metric Current State owner-tuple and lock-order hardening.
--
-- Guarantees added by this final hardening layer:
-- * accepted observations, Current projection and transition evidence are storage-bound
--   to the canonical metric_definition owner tuple;
-- * accepted Zabbix evidence is storage-bound to the exact provider binding/ref;
-- * claim/completion acquire the monitoring_source row before operation rows, matching
--   recovery and removing the source<->operation lock-order cycle during supersession.

BEGIN;

-- The provider binding already has one row per metric_definition.  Expose the complete
-- owner+provider tuple as a referenced key so accepted Current evidence cannot splice a
-- legitimate metric id together with another resource/source/generation/provider ref.
ALTER TABLE monitoring.metric_definition_provider_binding
    ADD CONSTRAINT metric_definition_binding_current_owner_ref_unique
    UNIQUE (
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation,
        provider_external_ref
    );

ALTER TABLE monitoring.monitoring_metric_observation_acceptance
    ADD CONSTRAINT metric_current_acceptance_definition_owner_fk
    FOREIGN KEY (
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ) REFERENCES monitoring.metric_definition(
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ),
    ADD CONSTRAINT metric_current_acceptance_binding_owner_fk
    FOREIGN KEY (
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation,
        provider_external_ref
    ) REFERENCES monitoring.metric_definition_provider_binding(
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation,
        provider_external_ref
    ),
    ADD CONSTRAINT metric_current_acceptance_owner_tuple_unique
    UNIQUE (
        tenant_id,
        observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    );

ALTER TABLE monitoring.metric_current_state
    ADD CONSTRAINT metric_current_state_definition_owner_fk
    FOREIGN KEY (
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ) REFERENCES monitoring.metric_definition(
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ),
    ADD CONSTRAINT metric_current_state_observation_owner_fk
    FOREIGN KEY (
        tenant_id,
        current_observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ) REFERENCES monitoring.monitoring_metric_observation_acceptance(
        tenant_id,
        observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    );

ALTER TABLE monitoring.monitoring_metric_current_state_transition
    ADD CONSTRAINT metric_current_transition_definition_owner_fk
    FOREIGN KEY (
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ) REFERENCES monitoring.metric_definition(
        tenant_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ),
    ADD CONSTRAINT metric_current_transition_to_observation_owner_fk
    FOREIGN KEY (
        tenant_id,
        to_observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ) REFERENCES monitoring.monitoring_metric_observation_acceptance(
        tenant_id,
        observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ),
    ADD CONSTRAINT metric_current_transition_from_observation_owner_fk
    FOREIGN KEY (
        tenant_id,
        from_observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    ) REFERENCES monitoring.monitoring_metric_observation_acceptance(
        tenant_id,
        observation_id,
        metric_definition_id,
        monitoring_resource_id,
        monitoring_source_id,
        source_instance_generation
    );

-- Preserve the already-accepted claim implementation behind a non-public inner surface.
-- The new public entrypoint acquires the source row first; the inner claim can then lock
-- its operation row without creating the old completion(source wait) <-> claim(op wait)
-- cycle.  All business/fencing semantics remain owned by the accepted v037 body.
ALTER FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    RENAME TO claim_zabbix_metric_current_state_v037_internal;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state_v037_internal(TEXT,TEXT,TEXT)
    FROM PUBLIC, jlmirror_wave4_metric_current_state_invoker;

CREATE FUNCTION monitoring.claim_zabbix_metric_current_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT
) RETURNS TABLE (
    monitoring_source_id TEXT,
    source_instance_generation TEXT,
    configuration_revision BIGINT,
    scope_revision BIGINT,
    current_state_poll_epoch BIGINT,
    current_state_poll_generation BIGINT,
    provider_instance_ref TEXT,
    provider_base_url TEXT,
    credential_binding_ref TEXT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
BEGIN
    -- Discovery is intentionally non-locking.  Authority is revalidated by the inner
    -- claim after the source serialization lock has been acquired.
    SELECT o.monitoring_source_id INTO v_source_id
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='pending'
       AND o.claim_token IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_not_claimable';
    END IF;

    PERFORM 1
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_stale_authority';
    END IF;

    RETURN QUERY
    SELECT *
      FROM monitoring.claim_zabbix_metric_current_state_v037_internal(
          p_tenant_id,
          p_monitoring_sync_operation_id,
          p_claim_token
      );
END;
$$;
ALTER FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.claim_zabbix_metric_current_state(TEXT,TEXT,TEXT)
    TO jlmirror_wave4_metric_current_state_invoker;

-- Do the same for completion.  The v036 totalizer remains the only implementation of
-- malformed-input terminalization; this wrapper adds only deterministic source-first
-- serialization before that implementation locks/revalidates the claimed operation.
ALTER FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    RENAME TO complete_zabbix_metric_current_state_v036_internal;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state_v036_internal(TEXT,TEXT,TEXT,JSONB)
    FROM PUBLIC, jlmirror_wave4_metric_current_state_invoker;

CREATE FUNCTION monitoring.complete_zabbix_metric_current_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_observations JSONB
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_source_id TEXT;
BEGIN
    SELECT o.monitoring_source_id INTO v_source_id
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_completion_not_claimed';
    END IF;

    PERFORM 1
      FROM monitoring.monitoring_source AS s
     WHERE s.tenant_id=p_tenant_id
       AND s.monitoring_source_id=v_source_id
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_completion_not_claimed';
    END IF;

    RETURN monitoring.complete_zabbix_metric_current_state_v036_internal(
        p_tenant_id,
        p_monitoring_sync_operation_id,
        p_claim_token,
        p_observations
    );
END;
$$;
ALTER FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    TO jlmirror_wave4_metric_current_state_invoker;

COMMIT;
